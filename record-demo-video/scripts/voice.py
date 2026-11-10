"""Make one narration clip per step from the captions in steps.js.

usage: voice.py WORK_DIR [--engine edge|say] [--voice NAME] [--rate=+8%] [--url URL]

edge (default): Microsoft neural voices through edge-tts. Natural sounding, but
  the narration text is sent to Microsoft's online service.
say: the built-in macOS voice. Fully offline, sounds more robotic.

Writes WORK_DIR/clips/NNN.(mp3|aiff), durations.json and captions.json.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("work", type=Path)
p.add_argument("--engine", choices=["edge", "say"], default="edge")
p.add_argument("--voice", help="edge default en-US-AvaMultilingualNeural, say default Samantha")
p.add_argument("--rate", default="+8%", help="speed change, e.g. --rate=+8%% or --rate=-5%%")
p.add_argument("--url", help="page to read steps.js on if the open tab cannot run scripts (default: startUrl)")
a = p.parse_args()
work = a.work.resolve()

if not shutil.which("ffprobe"):
    raise SystemExit("ffprobe not found. Install ffmpeg (brew install ffmpeg).")
if a.engine == "edge":
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        raise SystemExit("edge-tts is not installed. Run: pip3 install --user edge-tts  (or use --engine say)")
m = re.fullmatch(r"([+-]?)(\d+)%", a.rate)
if not m:
    raise SystemExit("--rate looks like +8% or -5% (write it as --rate=-5%)")
pct = int(m.group(2)) * (-1 if m.group(1) == "-" else 1)

# Only the captions are needed here, so load steps.js on the open page (no
# setup). Pages like chrome://newtab cannot run scripts: open the start page.
try:
    chrome.load(work)
except chrome.ChromeError:
    url = a.url or chrome.start_url(work)
    if not url:
        raise
    chrome.navigate(url)
    chrome.load(work)
lines = chrome.script_lines()

clips = work / "clips"
clips.mkdir(exist_ok=True)
for old in clips.glob("*"):
    old.unlink()

voice = a.voice or ("en-US-AvaMultilingualNeural" if a.engine == "edge" else "Samantha")
durations = {}
for i, text in enumerate(lines["spoken"]):
    if a.engine == "edge":
        out = clips / f"{i:03d}.mp3"
        cmd = [sys.executable, "-m", "edge_tts", "--voice", voice, f"--rate={'+' if pct >= 0 else '-'}{abs(pct)}%",
               f"--text={text}", "--write-media", str(out)]
    else:
        out = clips / f"{i:03d}.aiff"
        cmd = ["say", "-v", voice, "-r", str(round(185 * (1 + pct / 100))), "-o", str(out), text]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise SystemExit(f"voice failed on step {i}: {r.stderr.strip()[-400:]}")
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True).stdout.strip()
    durations[str(i)] = float(d)
    print(f"{i:3d}  {float(d):5.1f}s  {text}")

(work / "durations.json").write_text(json.dumps(durations, indent=1))
(work / "captions.json").write_text(json.dumps({**lines, "engine": a.engine, "voice": voice, "rate": a.rate}, indent=1))
print(f"{len(durations)} clips, {voice}, total {sum(durations.values()):.1f}s of speech")
