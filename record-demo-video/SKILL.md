---
name: record-demo-video
description: Record a narrated demo or test video of a web app in the user's own logged-in Chrome on macOS. A drawn cursor glides to each control and really clicks it, a natural AI voice explains each step, and the result is an MP4 with on-screen captions, a subtitle track and an .srt file. Use this whenever the user wants a screen recording, walkthrough, demo video, test or QA evidence video, feature tour, bug reproduction video, or a "show the team how this works" clip of a web page or local app, even if they don't mention voice-over or this skill by name.
compatibility: macOS with Google Chrome, Python 3, ffmpeg. edge-tts for the neural voice (optional; the macOS `say` voice works offline).
---

# Record a narrated demo video

Makes a video like a person screen-sharing: a cursor moves to each button and clicks it, a voice says what is happening, captions show the same words. It runs in the user's real Chrome tab, so their login, data and local dev server just work.

## How it works

Knowing the moving parts makes problems easy to place.

- **`scripts/chrome.py`** runs JavaScript in the active tab of Chrome's front window through AppleScript. Every other script uses it.
- **`scripts/engine.js`** is injected into the page. Chrome's tab capture does not record the system pointer, so it draws its own cursor, eases it along a slight arc to each target, and fires real pointer and mouse events at whatever sits under the tip. It also types, shows captions and runs steps.
- **`steps.js`** (you write this, one per video) holds the narration and the actions.
- **`scripts/recorder.js`** shows an orange button. Chrome only lets a page record itself after a real click, so the user clicks it once and presses Allow. The tab records itself and posts the video to a local receiver.
- **`scripts/voice.py`** turns each caption into a voice clip. **`scripts/record.py`** runs the steps, waits for each clip's length, then uses ffmpeg to place every clip where its step began and add subtitles.

## One-time setup

Check these before the first run. Each one fails with a clear message if it's missing.

1. Chrome menu: **View > Developer > Allow JavaScript from Apple Events**.
2. The first time, macOS asks whether the terminal or editor may control Chrome. Allow it.
3. `brew install ffmpeg` and `pip3 install --user edge-tts`.
4. In Claude Code with the sandbox on, `osascript` and the local port are usually blocked. Run the script commands with the sandbox turned off.

Quick test: `osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "document.title"'` should print the tab's title.

## Workflow

`<skill>` below means this skill's folder. Run every script with `python3`.

### 1. Agree on the story

Find out what feature to show, which page it starts on, and who will watch it. If the user already described the flow, draft the narration yourself. If parts are guesses, show the lines in chat before building.

### 2. Make a work folder and write steps.js

Create a folder for this video (for example `./demo-invite-flow/`) and copy `<skill>/templates/steps.example.js` into it as `steps.js`. The template shows every option.

Open the start page in Chrome and run `<skill>/scripts/inspect_page.py` to see the real button texts, labels, placeholders, dialogs and tables. Find elements by the words people see, not by CSS classes. See "Writing steps.js" below.

### 3. Make the voice clips

edge-tts sends the narration text to Microsoft's online voice service. **Ask the user once before using it**, especially for internal or client data. If they'd rather stay offline, add `--engine say`.

```
python3 <skill>/scripts/voice.py ./demo-invite-flow
```

Run it again whenever a caption changes. `record.py` refuses to run with clips that don't match the captions.

### 4. Practice run (no recording)

```
python3 <skill>/scripts/run_steps.py ./demo-invite-flow
```

It opens the start page fresh, runs `setup()`, then every step. It prints each step's status, what the step returned, and the `check()` snapshot. Read this closely. The narration has to be true: if a line says "ten rows", the check should show 10. Fix and rerun until every step is `done` and the numbers match. Use `--from N --no-reset` to retry one step without starting over, and `--paced` to preview real timing.

### 5. Record

Start `record.py` in the background, because it waits up to 5 minutes for the click:

```
python3 <skill>/scripts/record.py ./demo-invite-flow --name "Invite flow demo"
```

Then tell the user plainly: click the orange button at the top of the Chrome tab, press Allow, and don't touch Chrome until it finishes. Give them a time estimate: the total in `durations.json` plus about 0.4 seconds per step. Switching tabs pauses the cursor animation and spoils the video.

### 6. Check the result before handing it over

Grab a few frames and look at them, to confirm the page is visible, the cursor shows and the captions sit in the right place:

```
ffmpeg -v error -ss 4 -i "demo-invite-flow/Invite flow demo.mp4" -frames:v 1 /tmp/frame-4s.png
```

Then give the user the paths to the `.mp4` and `.srt`.

## Writing steps.js

```js
window.__DEMO = {
  startUrl: "http://localhost:3000/settings/team",   // opened fresh before each run
  ready: () => !!document.querySelector("table tbody tr"),   // optional
  setup: async (T) => { /* optional, not filmed */ },
  pronounce: { "SSO": "S S O" },                    // optional, voice only
  check: (T) => ({ rows: T.$$("tbody tr").length }), // optional, printed each step
  captionBar: true,                                  // false hides on-screen captions
  steps: [
    { say: "I'll click Invite member and type their email.",
      run: async (T) => {
        await T.click("Invite member");
        await T.type("Email address", "sam@example.com");
      } },
  ],
};
```

A step can also have `speak` (different words for the voice than the caption) and `timeout` in seconds (default 30). Whatever `run` returns is printed in the practice run.

### Helpers on `T`

Where a helper takes a target, it accepts an element, visible text (exact match after trimming), a RegExp, or a function that returns an element. Text and functions are waited for up to 6 seconds.

| Helper | What it does |
|---|---|
| `click(target)` | Moves the cursor there, scrolls into view if needed, clicks what's under the tip |
| `hover(target)` | Moves there and fires hover events (opens tooltips and hover menus) |
| `type(target, text, {clear, delay})` | Clicks a field and types one key at a time. Text targets match placeholder, aria-label, name or `<label>` |
| `setValue(target, value)` | Clicks, then sets a `<select>`, date or similar input in one go |
| `press(key, target?)` | Sends a key such as `"Enter"`, `"Escape"`, `"ArrowDown"` |
| `scroll(yOrTarget)` | Smooth scroll, waits until it stops |
| `waitFor(selectorOrFn, ms)` | Waits until something appears and returns it |
| `byText(text, selector?, root?)` | Finds a visible element by text, falling back to aria-label, title, placeholder |
| `button(text)`, `field(text)` | Shortcuts for buttons and form fields |
| `$`, `$$`, `text(el)`, `sleep(ms)` | Small DOM helpers |

### What makes a good video

- **Talk like a person showing a colleague.** First person, short sentences, plain words: "I'll filter to last month. Six invoices left." Say what to notice, not every click. Avoid "Step 3:" and reading out labels robotically.
- **Every filmed action goes through `T`.** A plain `el.click()` changes the page while the cursor sits still, which looks fake. Plain DOM calls are fine in `setup()`. Don't add highlight boxes: the moving cursor and its click ripple already point, and boxes drift out of line when the page moves.
- **Give the data time to load before talking about it.** After Search or Apply, `await T.waitFor(...)` for the result, so the next line isn't spoken over a spinner.
- **Fit the actions to the words.** A step's actions play while its line is spoken. If a step does a lot, give it more words or split it.
- **Point next to numbers, not at them.** The cursor tip covers what it points at, so hover the label beside a number.
- **Keep to one page load.** The recorder lives inside the page, so a full page load (a plain link, `location.href`, a non-JS form submit) ends the recording. Moving between pages inside a single-page app is fine. For a flow across full page loads, record one video per page.
- **Know what synthetic events can't do.** The browser marks them as not from a real user, so native `<select>` lists, date pickers and file dialogs won't open, and pressing Enter won't submit a plain HTML form. Use `setValue` for selects and dates, click the submit button, and do file uploads in `setup()` or before recording.
- **Main page only.** The finders don't look inside iframes or closed shadow DOM.

## Voices

Default: `en-US-AvaMultilingualNeural` at `--rate=+8%` (a touch quicker than normal, which keeps demos lively). Others that sound natural: `en-US-AndrewMultilingualNeural`, `en-GB-SoniaNeural`, `en-AU-NatashaNeural`, `en-IN-NeerjaNeural`. List them all with `python3 -m edge_tts --list-voices`. Offline: `--engine say --voice Samantha`.

## Files in the work folder

`steps.js` (yours), `clips/` + `durations.json` + `captions.json` (voice), `results_dry.json` (practice run), `raw.webm` + `marks.json` + `results_record.json` (recording), and the final `NAME.mp4` + `NAME.srt`. If a step fails mid-recording, the output is named `NAME (partial).mp4`.

When something goes wrong, read `references/troubleshooting.md`.
