# record-demo-video

A Claude Code skill that records narrated demo videos of any web app.

You tell Claude what to show. It writes the steps, then records your own Chrome tab while a cursor moves around and clicks things, and a natural voice explains what's happening. You get an MP4 with captions on screen, a subtitle track, and an `.srt` file.

It's handy for feature demos, test evidence for a ticket, bug reports, and "here's how this works" videos for your team.

## What you need

- A Mac with Google Chrome
- Python 3 and ffmpeg: `brew install ffmpeg`
- edge-tts for the natural voice: `pip3 install --user edge-tts`
- In Chrome: **View > Developer > Allow JavaScript from Apple Events**

The first time, macOS will ask if your terminal or editor can control Chrome. Say yes.

## Install

Copy this folder into your Claude skills folder:

```
git clone <this repo> /tmp/record-demo-video
cp -r /tmp/record-demo-video ~/.claude/skills/record-demo-video
```

Or put it in one project only, at `<project>/.claude/skills/record-demo-video`.

## Use it

Open your app in Chrome, then ask Claude something like:

> Record a demo video of the invite flow on localhost:3000/settings/team. Show inviting a new admin and the pending row that appears.

Claude will:

1. Look at the page and write the steps and the narration.
2. Make the voice clips.
3. Do a practice run to check every step works and every number it says is right.
4. Ask you to click an orange "start recording" button in the tab and press Allow. Chrome only lets a page record itself after a real click.
5. Put the voice and subtitles together and check a few frames.

Don't touch Chrome while it records. It usually takes a minute or two.

## Good to know

- **Privacy:** the default voice (edge-tts) sends the narration text to Microsoft's online voice service. Claude asks before using it. To stay fully offline, ask for the macOS voice (`--engine say`). It sounds more robotic.
- **Mac and Chrome only.** It drives Chrome through AppleScript.
- **One page load per video.** The recorder lives inside the page, so a full page reload stops it. Moving around inside a single-page app is fine.
- **Some native controls can't be opened** by the fake clicks: native dropdowns, date pickers and file dialogs. The skill sets those values directly instead.

## Run it by hand

```
python3 scripts/inspect_page.py              # what's on the open page
python3 scripts/voice.py  ./my-demo          # voice clips from steps.js
python3 scripts/run_steps.py ./my-demo       # practice run, no recording
python3 scripts/record.py ./my-demo --name "My demo"
```

`./my-demo/steps.js` starts as a copy of `templates/steps.example.js`.
