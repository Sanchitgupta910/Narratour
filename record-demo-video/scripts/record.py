"""Record the steps as a narrated video.

usage: record.py WORK_DIR [--name NAME] [--port 8765] [--gap 0.35] [--url URL] [--wait 300]
       record.py WORK_DIR --mux-only [--raw FILE] [--name NAME]

1. Opens the start page fresh and runs setup() (not filmed).
2. Shows an orange button in the page. The person clicks it and allows tab
   sharing; Chrome then records its own tab.
3. Runs every step, waiting for each narration clip to finish.
4. The page sends the video to a small receiver on 127.0.0.1:PORT.
5. ffmpeg adds the voice clips at the moment each step started, plus a
   subtitle track, and writes WORK_DIR/NAME.mp4 and NAME.srt.

--mux-only redoes step 5 from raw.webm + marks.json (for example after the page
blocked the upload and the video was saved to Downloads instead).
"""
import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome  # noqa: E402
from chrome import log  # noqa: E402

HERE = Path(__file__).resolve().parent

p = argparse.ArgumentParser()
p.add_argument("work", type=Path)
p.add_argument("--name", help="output file name without .mp4 (default: the work folder's name)")
p.add_argument("--port", type=int, default=8765)
p.add_argument("--gap", type=float, default=0.35, help="pause after each narration clip, in seconds")
p.add_argument("--url", help="start page (default: startUrl in steps.js)")
p.add_argument("--wait", type=int, default=300, help="seconds to wait for the record button click")
p.add_argument("--mux-only", action="store_true")
p.add_argument("--raw", type=Path, help="with --mux-only: the raw .webm (default WORK_DIR/raw.webm)")
a = p.parse_args()
work = a.work.resolve()
name = a.name or work.name
raw = work / "raw.webm"

for tool in ("ffmpeg", "ffprobe"):
    if not shutil.which(tool):
        raise SystemExit(f"{tool} not found. Install ffmpeg (brew install ffmpeg).")
if not (work / "durations.json").exists() or not (work / "captions.json").exists():
    raise SystemExit("Run voice.py first: no durations.json / captions.json in " + str(work))
durations = json.loads((work / "durations.json").read_text())


def ts(s):
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def mux(raw_file: Path, marks: list, partial: bool):
    if not marks:
        raise SystemExit("No step marks: nothing was recorded.")
    stem = f"{name} (partial)" if partial else name
    final, srt = work / f"{stem}.mp4", work / f"{stem}.srt"

    # Subtitles: each caption from its step's start to the next step's start.
    lines = []
    for k, mk in enumerate(marks):
        end = marks[k + 1]["t"] - 0.05 if k + 1 < len(marks) else mk["t"] + durations[str(mk["i"])] + 0.8
        lines.append(f"{k + 1}\n{ts(mk['t'])} --> {ts(end)}\n{mk['text']}\n")
    srt.write_text("\n".join(lines))

    # Voice: each clip delayed to the moment its step started.
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_file)]
    for mk in marks:
        clip = next((work / "clips").glob(f"{mk['i']:03d}.*"), None)
        if clip is None:
            raise SystemExit(f"Missing voice clip for step {mk['i']}: run voice.py again")
        cmd += ["-i", str(clip)]
    cmd += ["-i", str(srt)]
    filt = []
    for k, mk in enumerate(marks):
        ms = max(0, int(mk["t"] * 1000) + 150)
        filt.append(f"[{k + 1}:a]adelay={ms}|{ms}[a{k}]")
    filt.append("".join(f"[a{k}]" for k in range(len(marks)))
                + f"amix=inputs={len(marks)}:normalize=0:dropout_transition=0[aout]")
    # Even width/height for H.264, constant 30 fps (tab capture is variable).
    filt.append("[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30[vout]")
    cmd += ["-filter_complex", ";".join(filt), "-map", "[vout]", "-map", "[aout]", "-map", f"{len(marks) + 1}:s",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
            "-movflags", "+faststart", str(final)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n" + r.stderr[-1500:])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)],
                       capture_output=True, text=True).stdout.strip()
    log(f"VIDEO {final}  ({float(d):.1f}s, {final.stat().st_size / 1e6:.1f} MB)")
    log(f"SUBTITLES {srt}")


if a.mux_only:
    src = (a.raw or raw).expanduser().resolve()
    if not src.exists() or not (work / "marks.json").exists():
        raise SystemExit(f"--mux-only needs {src} and {work / 'marks.json'}")
    meta = json.loads((work / "marks.json").read_text())
    mux(src, meta["marks"], meta.get("partial", False))
    sys.exit(0)


# ---- Receiver for the recorded video ------------------------------------------
class Upload(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        # Lets pages on other origins (staging, https) reach this local port.
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw.write_bytes(self.rfile.read(n))
        self.send_response(200)
        self._cors()
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


try:
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Upload)
except OSError:
    raise SystemExit(f"Port {a.port} is busy. Try --port 8777.")
threading.Thread(target=server.serve_forever, daemon=True).start()
raw.unlink(missing_ok=True)

total = chrome.open_fresh(work, a.url)
log(f"page ready, {total} steps")

# The clips must match the captions, or the voice says old lines.
saved = json.loads((work / "captions.json").read_text())
now = chrome.script_lines()
if now["captions"] != saved["captions"] or now["spoken"] != saved["spoken"]:
    raise SystemExit("steps.js narration changed since voice.py ran. Run voice.py again first.")

chrome.js((HERE / "recorder.js").read_text().replace("__PORT__", str(a.port)))
chrome.activate()
log("WAITING: click the orange button in Chrome, then press Allow (Share this tab)")
deadline = time.time() + a.wait
while time.time() < deadline:
    if chrome.js("String(!!(window.__rec && window.__rec.startedAt))") == "true":
        break
    time.sleep(0.5)
else:
    raise SystemExit(f"No click within {a.wait}s, stopped.")
log("recording")
time.sleep(1.2)

results, partial = [], False
for i in range(total):
    t0 = time.time()
    res = chrome.run_step(i)
    left = durations[str(i)] + a.gap - (time.time() - t0)
    if left > 0:
        time.sleep(left)
    results.append({"step": i, **res})
    log(i, res.get("status"), res.get("error", ""))
    if res.get("status") != "done":
        log(f"STEP {i} FAILED, stopping. Fix it with run_steps.py, then record again.")
        partial = True
        break
    if chrome.js("String(window.__rec.stoppedEarly)") == "true":
        log("Sharing was stopped in Chrome, stopping.")
        partial = True
        break

time.sleep(1.0)
chrome.js("window.__T.caption('')")
marks = json.loads(chrome.js("JSON.stringify(window.__rec.marks)"))
(work / "marks.json").write_text(json.dumps({"marks": marks, "partial": partial}, indent=1))
(work / "results_record.json").write_text(json.dumps(results, indent=1))
chrome.js("window.__stopAndUpload()")
up = "null"
for _ in range(240):
    up = chrome.js("String(window.__rec.uploaded)")
    if up and up != "null":
        break
    time.sleep(0.5)
server.shutdown()

if up.startswith("download"):
    log("The page blocked the upload, so Chrome saved the video to Downloads as demo-raw.webm.")
    log(f"Finish with: python3 {HERE / 'record.py'} \"{work}\" --mux-only --raw ~/Downloads/demo-raw.webm")
    sys.exit(2)
if not raw.exists() or raw.stat().st_size == 0:
    raise SystemExit(f"No video arrived (upload said: {up}).")
log(f"raw video {raw.stat().st_size / 1e6:.1f} MB")
mux(raw, marks, partial)
