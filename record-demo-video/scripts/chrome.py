"""Shared helpers: run JavaScript in Chrome's active tab (macOS, AppleScript),
open the start page fresh, load the engine + steps.js, run steps."""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ChromeError(RuntimeError):
    pass


def _osascript(*lines, timeout=90):
    args = ["osascript"]
    for line in lines:
        args += ["-e", line]
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "JavaScript through AppleScript is turned off" in err:
            raise ChromeError("Chrome blocks this. In Chrome: View > Developer > Allow JavaScript from Apple Events.")
        if "-1743" in err or "Not authorized" in err:
            raise ChromeError("macOS blocked control of Chrome. Allow it in System Settings > "
                              "Privacy & Security > Automation, then try again.")
        if "-1719" in err or "-1728" in err:
            raise ChromeError("No Chrome window found. Open Chrome with the app tab in front.")
        raise ChromeError(err or f"osascript failed ({r.returncode})")
    return r.stdout.strip()


def js(code: str) -> str:
    """Run code in the active tab of Chrome's front window; returns the last value as text."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        return _osascript(f'set js to read POSIX file "{path}" as «class utf8»',
                          'tell application "Google Chrome" to execute active tab of front window javascript js')
    finally:
        Path(path).unlink(missing_ok=True)


def activate():
    _osascript('tell application "Google Chrome" to activate')


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---- steps.js ---------------------------------------------------------------

def steps_file(work: Path) -> Path:
    f = work / "steps.js"
    if not f.exists():
        raise SystemExit(f"No steps.js in {work}. Copy templates/steps.example.js there first.")
    return f


def start_url(work: Path):
    m = re.search(r"""startUrl\s*:\s*["'`]([^"'`]+)["'`]""", steps_file(work).read_text())
    return m.group(1) if m else None


def navigate(url: str, timeout=60):
    """Open url in the active tab and wait until the new page has loaded."""
    try:
        js("window.__navMarker = 1; 'ok'")  # gone once the new page loads
    except ChromeError:
        pass  # pages like chrome://newtab do not run scripts; that is fine
    safe = url.replace("\\", "\\\\").replace('"', '\\"')
    _osascript(f'tell application "Google Chrome" to set URL of active tab of front window to "{safe}"')
    time.sleep(1.0)
    end = time.time() + timeout
    while time.time() < end:
        try:
            if js("String(window.__navMarker === undefined && document.readyState === 'complete')") == "true":
                return
        except ChromeError:
            pass
        time.sleep(0.5)
    raise ChromeError(f"page did not load within {timeout}s: {url}")


def load(work: Path) -> int:
    """Inject the engine, then steps.js. Returns the number of steps."""
    js((HERE / "engine.js").read_text())
    src = steps_file(work).read_text()
    # The extra block keeps steps.js variables out of the wrapper's way, and
    # lets the file be loaded again after edits without "already declared" errors.
    wrapped = (
        "(() => {\ntry {\n{\n" + src + "\n}\n} catch (e) { return 'error: ' + (e && e.message || e); }\n"
        "const d = window.__DEMO;\n"
        "if (!d || !Array.isArray(d.steps)) return 'error: steps.js must set window.__DEMO = { steps: [...] }';\n"
        "const bad = d.steps.findIndex((s) => !s || typeof s.say !== 'string' || typeof s.run !== 'function');\n"
        "if (bad >= 0) return 'error: step ' + bad + ' needs a say text and a run function';\n"
        "return 'ok ' + d.steps.length;\n})()"
    )
    out = js(wrapped)
    if not out.startswith("ok "):
        if out in ("", "missing value"):
            out = "steps.js did not run. It probably has a syntax error: check it with `node --check steps.js`."
        raise ChromeError(out)
    return int(out.split()[1])


def wait_ready(timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        r = js("(() => { try { const d = window.__DEMO; return String(!d.ready || !!d.ready()); } "
               "catch (e) { return 'false'; } })()")
        if r == "true":
            return
        time.sleep(0.5)
    raise ChromeError(f"ready() in steps.js did not turn true within {timeout}s")


def run_setup(timeout=60):
    js("window.__runSetup()")
    end = time.time() + timeout
    while time.time() < end:
        state = js("String(window.__setupState)")
        if state == "done":
            return
        if state.startswith("error"):
            raise ChromeError(f"setup() failed: {state}")
        time.sleep(0.4)
    raise ChromeError("setup() did not finish in time")


def open_fresh(work: Path, url=None, reset=True) -> int:
    """Start page, engine, steps, ready(), setup(). Returns the number of steps."""
    url = url or start_url(work)
    if reset and url:
        navigate(url)
    elif reset:
        log("no startUrl in steps.js: using the page that is open now")
    n = load(work)
    wait_ready()
    run_setup()
    return n


def step_timeout(i) -> float:
    return float(js(f"String(window.__DEMO.steps[{i}].timeout || 30)"))


def run_step(i, timeout=None) -> dict:
    timeout = timeout or step_timeout(i)
    js(f"window.__runStep({i})")
    end = time.time() + timeout
    while time.time() < end:
        try:
            res = json.loads(js(f"JSON.stringify(window.__stepResults[{i}] || null)") or "null")
        except (ValueError, ChromeError):
            res = None
        if res and res.get("status") != "running":
            return res
        time.sleep(0.3)
    return {"status": "timeout", "error": f"step took longer than {timeout:.0f}s"}


# ---- narration ----------------------------------------------------------------

def script_lines() -> dict:
    """What the loaded steps.js will show and say: captions and spoken text."""
    d = json.loads(js(
        "JSON.stringify({ say: window.__DEMO.steps.map((s) => s.say), "
        "speak: window.__DEMO.steps.map((s) => s.speak || null), "
        "pronounce: window.__DEMO.pronounce || {} })"))
    swaps = sorted(d["pronounce"].items(), key=lambda kv: -len(kv[0]))
    spoken = []
    for say, speak in zip(d["say"], d["speak"]):
        t = speak or say
        for a, b in swaps:
            t = t.replace(a, b)
        spoken.append(t)
    return {"captions": d["say"], "spoken": spoken}
