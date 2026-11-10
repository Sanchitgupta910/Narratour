"""List what can be seen, clicked or typed into on the open Chrome tab, to help
write steps.js without guessing at labels.

usage: inspect_page.py [--url URL] [--json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome  # noqa: E402

JS = r"""
(() => {
  const vis = (el) => { const b = el.getBoundingClientRect(); return b.width > 0 && b.height > 0; };
  const t = (el) => (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 70);
  const uniq = (a) => [...new Set(a)].slice(0, 150);
  const q = (s) => [...document.querySelectorAll(s)].filter(vis);
  const name = (el) => t(el) || el.getAttribute("aria-label") || el.title || "";
  return JSON.stringify({
    url: location.href,
    title: document.title,
    headings: uniq(q("h1, h2, h3").map(t).filter(Boolean)),
    buttons: uniq(q("button, [role=button], [role=tab], [role=menuitem], [role=option], [role=checkbox], [role=switch], [role=combobox]")
      .map((b) => (t(b) ? t(b) : "(label) " + (b.getAttribute("aria-label") || b.title || "?")))),
    links: uniq(q("a[href]").filter((a) => name(a)).map((a) => name(a) + "  ->  " + a.getAttribute("href"))),
    fields: q("input:not([type=hidden]), textarea, select, [contenteditable=true]").slice(0, 80).map((f) => ({
      tag: f.tagName.toLowerCase(), type: f.getAttribute("type"), placeholder: f.getAttribute("placeholder"),
      label: [...(f.labels || [])].map(t).join(" ") || f.getAttribute("aria-label"), name: f.getAttribute("name"),
      id: f.id || null, value: f.value ? String(f.value).slice(0, 40) : null,
    })),
    dialogs: q("[role=dialog], dialog[open]").map((d) => t(d).slice(0, 160)),
    tables: q("table").map((tb) => ({
      headers: [...tb.querySelectorAll("thead th")].map(t).filter(Boolean),
      rows: tb.querySelectorAll("tbody tr").length,
    })),
    iframes: q("iframe").length,
  });
})()
"""

p = argparse.ArgumentParser()
p.add_argument("--url", help="open this page first")
p.add_argument("--json", action="store_true")
a = p.parse_args()
if a.url:
    chrome.navigate(a.url)
info = json.loads(chrome.js(JS))
if a.json:
    print(json.dumps(info, indent=1))
    sys.exit(0)
print(f"{info['title']}\n{info['url']}\n")
for key in ("headings", "buttons", "links", "dialogs"):
    if info[key]:
        print(key.upper())
        for item in info[key]:
            print("  ", item)
        print()
if info["fields"]:
    print("FIELDS")
    for f in info["fields"]:
        print("  ", {k: v for k, v in f.items() if v})
    print()
for tb in info["tables"]:
    print(f"TABLE  {tb['rows']} rows  |  " + " | ".join(tb["headers"]))
if info["iframes"]:
    print(f"\nNote: {info['iframes']} iframe(s). The helpers only search the main page.")
