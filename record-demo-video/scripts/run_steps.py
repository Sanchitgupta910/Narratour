"""Practice run: every step in Chrome, no recording. Prints what each step
returned and what check() saw, so you can confirm the app did the right thing.

usage: run_steps.py WORK_DIR [--from N] [--to N] [--no-reset] [--url URL] [--paced]

--from/--to   run part of the list (with --no-reset to keep the current state)
--paced       wait for each narration clip, to preview the real timing
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("work", type=Path)
p.add_argument("--from", dest="start", type=int, default=0)
p.add_argument("--to", dest="end", type=int)
p.add_argument("--no-reset", action="store_true", help="do not reopen the start page or run setup()")
p.add_argument("--url", help="start page (default: startUrl in steps.js)")
p.add_argument("--paced", action="store_true")
a = p.parse_args()
work = a.work.resolve()

if a.no_reset:
    total = chrome.load(work)
else:
    total = chrome.open_fresh(work, a.url)
end = total - 1 if a.end is None else min(a.end, total - 1)
durations = {}
if a.paced:
    f = work / "durations.json"
    if not f.exists():
        raise SystemExit("--paced needs durations.json: run voice.py first")
    durations = json.loads(f.read_text())

say = json.loads(chrome.js("JSON.stringify(window.__DEMO.steps.map((s) => s.say))"))
results, failed = [], False
for i in range(a.start, end + 1):
    t0 = time.time()
    res = chrome.run_step(i)
    left = (durations.get(str(i), 0) + 0.35) - (time.time() - t0) if a.paced else 0.3
    if left > 0:
        time.sleep(left)
    res["step"], res["say"], res["seconds"] = i, say[i], round(time.time() - t0, 1)
    results.append(res)
    extra = {k: res[k] for k in ("value", "check", "error") if res.get(k) is not None}
    print(f"{i:3d} {res['status']:7s} {res['seconds']:5.1f}s  {say[i][:70]}")
    if extra:
        print("              ", json.dumps(extra)[:400])
    if res["status"] != "done":
        print(f"STOPPED at step {i}")
        failed = True
        break

chrome.js("window.__T.caption('')")
(work / "results_dry.json").write_text(json.dumps(results, indent=1))
print("FAILED" if failed else f"OK: steps {a.start}-{end} done")
sys.exit(1 if failed else 0)
