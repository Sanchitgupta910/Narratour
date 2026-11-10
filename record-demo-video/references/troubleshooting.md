# Troubleshooting

| What you see | Why | Fix |
|---|---|---|
| "Chrome blocks this. ... Allow JavaScript from Apple Events" | Chrome setting is off | Chrome: View > Developer > Allow JavaScript from Apple Events |
| "macOS blocked control of Chrome" (-1743) | Automation permission denied | System Settings > Privacy & Security > Automation: allow the terminal/editor to control Chrome |
| "No Chrome window found" | Chrome closed, or no normal window | Open Chrome with the app tab active in the front window |
| Commands hang or fail only inside Claude Code | Sandbox blocks osascript or the local port | Run the script commands with the sandbox off |
| "steps.js did not run" | Syntax error in steps.js | `node --check steps.js` shows the line |
| `not found: Save` | No visible element with exactly that text | Run `inspect_page.py` on the page at that moment; use a RegExp for partial text, or `byText(text, selector)` |
| `cursor not on X (something covers it?)` | A toast, sticky header or overlay sits on top, or the page moved | Close the overlay in an earlier step, wait for the animation, or target a different part of the element |
| Step `timeout` | The step waited on something that never came (`waitFor`), or the app is slow | Raise the step's `timeout`, or check the app (dev server may have died) |
| Page shows 0 rows, then "refused to connect" | Local dev server crashed mid-run | Restart it, then rerun |
| "ready() did not turn true" | Data never loaded, or the selector is wrong | Check the page by hand; fix `ready` |
| Nothing happens after clicking the orange button | The Allow dialog was dismissed, or a different tab or window was picked | Click the button again and choose "this tab" |
| "Port 8765 is busy" | Another receiver still running | `--port 8777`, or stop the old process |
| "The page blocked the upload" | Strict Content-Security-Policy, or Chrome's local network rules on a non-localhost site | The video is in Downloads as `demo-raw.webm`: run `record.py WORK --mux-only --raw ~/Downloads/demo-raw.webm`. If Chrome asks about local network access, Allow it next time |
| Cursor froze in the video | The tab was hidden (another tab or window in front) so animation paused | Keep the tab visible and untouched during recording |
| Voice says old lines | Captions changed after voice.py | `record.py` normally stops you; run `voice.py` again |
| edge-tts errors (403, network) | Old edge-tts or no internet | `pip3 install --user -U edge-tts`, or use `--engine say` |
| Clicks land on the wrong thing | Clicked while a smooth scroll was still moving | The engine waits for scrolling to settle; if a custom scroller animates on its own, add `await T.sleep(500)` before the click |
| Typed text doesn't stick in a rich editor | Editor ignores input events | `type` uses execCommand for contenteditable; for canvas editors, set the value in `setup()` instead |
| Video is huge | Retina screens record at 2x | Fine for sharing. To shrink: `ffmpeg -i in.mp4 -vf scale=iw/2:-2 -c:a copy out.mp4` |

## Shell gotchas

- Write JavaScript to files with your file-writing tool, not with `echo` in zsh: zsh's `echo` turns `\n` into a real newline, which breaks regexes and strings.
- After changing the page URL, wait for the new page before reading it, or you read the old one. `chrome.navigate()` handles this with a marker on the old page.
- AppleScript can't wait for a promise. That's why steps are started and then polled through `window.__stepResults`.
