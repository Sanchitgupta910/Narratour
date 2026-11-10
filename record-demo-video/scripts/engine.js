// Demo engine: a drawn cursor that moves and really clicks, typing, captions and
// a step runner. chrome.py injects this into the page first, then steps.js.
//
// Why a drawn cursor: Chrome's tab capture does not record the system pointer,
// so the page draws one, eases it to each target and fires real pointer/mouse
// events on whatever is under its tip, the same way a hand would.
(() => {
  if (window.__T) return "already";

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const text = (el) => (el?.innerText || el?.textContent || "").trim();
  const visible = (el) => {
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0 && getComputedStyle(el).visibility !== "hidden";
  };
  const matches = (value, want) =>
    value != null && (want instanceof RegExp ? want.test(value) : String(value).trim() === want);

  // ---- Finding things -------------------------------------------------------
  const CLICKABLE =
    "button, a, [role=button], [role=tab], [role=menuitem], [role=option], [role=checkbox], " +
    "[role=switch], [role=link], [role=combobox], label, summary";

  // First visible element whose text matches. Falls back to aria-label, title
  // and placeholder, so icon buttons can be found by their label too.
  function byText(want, selector = CLICKABLE, root = document) {
    const all = $$(selector, root).filter(visible);
    return (
      all.find((el) => matches(text(el), want)) ||
      all.find((el) => ["aria-label", "title", "placeholder"].some((a) => matches(el.getAttribute(a), want)))
    );
  }
  const button = (want, root) => byText(want, "button, [role=button], a", root);

  // A text box by its placeholder, aria-label or <label> text.
  function field(want, root = document) {
    return $$("input, textarea, select, [contenteditable=true]", root)
      .filter(visible)
      .find(
        (el) =>
          matches(el.getAttribute("placeholder"), want) ||
          matches(el.getAttribute("aria-label"), want) ||
          matches(el.getAttribute("name"), want) ||
          [...(el.labels || [])].some((l) => matches(text(l), want))
      );
  }

  // Waits until a selector or function gives something truthy, then returns it.
  async function waitFor(what, timeout = 10000) {
    const t0 = performance.now();
    while (performance.now() - t0 < timeout) {
      let v = null;
      try {
        v = typeof what === "string" ? $(what) : await what();
      } catch {}
      if (v) return v;
      await sleep(120);
    }
    throw new Error(`timed out waiting for ${typeof what === "string" ? what : "condition"}`);
  }

  // Lets click/hover/type take an element, visible text, a RegExp or a finder function.
  async function resolve(target, finder = byText) {
    if (target instanceof Element) return target;
    if (typeof target === "function") return waitFor(target, 6000);
    if (typeof target === "string" || target instanceof RegExp) {
      try {
        return await waitFor(() => finder(target), 6000);
      } catch {
        throw new Error(`not found: ${target}`);
      }
    }
    throw new Error(`not found: ${target}`);
  }
  const label = (target) => (target instanceof Element ? target.tagName.toLowerCase() : String(target));

  // ---- The cursor -----------------------------------------------------------
  const cursor = document.createElement("div");
  cursor.id = "__cursor";
  cursor.innerHTML =
    '<svg width="24" height="30" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M3 2 L3 23 L8.6 17.6 L12.4 26.6 L16.2 25 L12.5 16.4 L20 16.4 Z" fill="#111827" ' +
    'stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/></svg>';
  Object.assign(cursor.style, {
    position: "fixed", left: "0px", top: "0px", width: "24px", height: "30px",
    zIndex: 2147483647, pointerEvents: "none", transformOrigin: "3px 2px",
    transform: "translate(-3px, -2px)", transition: "transform 90ms ease-out",
    filter: "drop-shadow(0 1px 2px rgba(0,0,0,.35))",
  });
  document.body.appendChild(cursor);
  let cx = Math.round(innerWidth * 0.62);
  let cy = Math.round(innerHeight * 0.42);
  const place = (x, y) => {
    cursor.style.left = `${x}px`;
    cursor.style.top = `${y}px`;
  };
  place(cx, cy);

  async function moveTo(x, y) {
    const sx = cx, sy = cy;
    const dist = Math.hypot(x - sx, y - sy);
    if (dist < 2) return;
    const dur = Math.min(780, Math.max(280, dist * 0.85));
    // A slight arc, like a hand, not a ruler.
    const mx = (sx + x) / 2 + (y - sy) * 0.08;
    const my = (sy + y) / 2 - (x - sx) * 0.08;
    const t0 = performance.now();
    await new Promise((done) => {
      const frame = (now) => {
        const t = Math.min(1, (now - t0) / dur);
        const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        place((1 - e) * (1 - e) * sx + 2 * (1 - e) * e * mx + e * e * x,
              (1 - e) * (1 - e) * sy + 2 * (1 - e) * e * my + e * e * y);
        if (t < 1) requestAnimationFrame(frame);
        else done();
      };
      requestAnimationFrame(frame);
    });
    cx = x;
    cy = y;
  }

  function ripple(x, y) {
    const r = document.createElement("div");
    Object.assign(r.style, {
      position: "fixed", left: `${x - 16}px`, top: `${y - 16}px`, width: "32px", height: "32px",
      borderRadius: "50%", background: "rgba(249,115,22,.28)", border: "2px solid rgba(249,115,22,.85)",
      zIndex: 2147483646, pointerEvents: "none", transform: "scale(.35)", opacity: "1",
      transition: "transform .38s ease-out, opacity .5s ease-out",
    });
    document.body.appendChild(r);
    requestAnimationFrame(() => {
      r.style.transform = "scale(1.35)";
      r.style.opacity = "0";
    });
    setTimeout(() => r.remove(), 560);
  }

  // Waits until something stops moving (smooth scroll, animation).
  async function settle(pos, maxMs = 1800) {
    let last = pos();
    let still = 0;
    const t0 = performance.now();
    while (performance.now() - t0 < maxMs && still < 5) {
      await new Promise((r) => requestAnimationFrame(r));
      const now = pos();
      still = Math.abs(now - last) < 0.5 ? still + 1 : 0;
      last = now;
    }
  }
  const settleEl = (el) => settle(() => {
    const b = el.getBoundingClientRect();
    return b.top + b.left * 10000;
  });

  // Where the cursor aims on an element: its centre, or near the left of a wide
  // one (table rows, long inputs). Scrolls it into view first if needed.
  async function aim(el) {
    let box = el.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    // Off screen, or hidden inside a scrolled container (a wide table): scroll it
    // to the middle, both ways, and wait for the scroll to finish. Clicking
    // before it settles hits whatever scrolled under the tip.
    const hidden =
      box.top < 70 || box.bottom > innerHeight - 70 || box.left < 0 || box.right > innerWidth ||
      !(hit && (el.contains(hit) || hit.contains(el)));
    if (hidden) {
      el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
      await settleEl(el);
      box = el.getBoundingClientRect();
    }
    const x = box.width > 220 ? box.left + 36 : box.left + box.width / 2;
    return { x: Math.round(x), y: Math.round(box.top + box.height / 2) };
  }

  // Hover events, so tooltips and hover menus open as they would for a person.
  let hovered = null;
  function hoverEvents(target, x, y) {
    if (target === hovered) return;
    const base = { clientX: x, clientY: y, view: window, composed: true };
    const p = { pointerId: 1, pointerType: "mouse", isPrimary: true };
    if (hovered && hovered.isConnected) {
      hovered.dispatchEvent(new PointerEvent("pointerout", { ...base, ...p, bubbles: true }));
      hovered.dispatchEvent(new PointerEvent("pointerleave", { ...base, ...p, bubbles: false }));
      hovered.dispatchEvent(new MouseEvent("mouseout", { ...base, bubbles: true }));
      hovered.dispatchEvent(new MouseEvent("mouseleave", { ...base, bubbles: false }));
    }
    hovered = target;
    if (!target) return;
    target.dispatchEvent(new PointerEvent("pointerover", { ...base, ...p, bubbles: true }));
    target.dispatchEvent(new PointerEvent("pointerenter", { ...base, ...p, bubbles: false }));
    target.dispatchEvent(new MouseEvent("mouseover", { ...base, bubbles: true }));
    target.dispatchEvent(new MouseEvent("mouseenter", { ...base, bubbles: false }));
    target.dispatchEvent(new PointerEvent("pointermove", { ...base, ...p, bubbles: true }));
    target.dispatchEvent(new MouseEvent("mousemove", { ...base, bubbles: true }));
  }

  async function hover(target) {
    const el = await resolve(target);
    const { x, y } = await aim(el);
    await moveTo(x, y);
    hoverEvents(document.elementFromPoint(x, y), x, y);
    await sleep(250);
    return el;
  }

  async function click(target) {
    const el = await resolve(target);
    const what = label(target);
    let { x, y } = await aim(el);
    await moveTo(x, y);
    await sleep(110);
    // Click what is really under the tip. If something moved in the meantime,
    // aim again rather than click the wrong control.
    const onTarget = (t) => t && (el.contains(t) || t.contains(el));
    let tip = document.elementFromPoint(x, y);
    if (!onTarget(tip)) {
      await settleEl(el);
      ({ x, y } = await aim(el));
      await moveTo(x, y);
      await sleep(110);
      tip = document.elementFromPoint(x, y);
      if (!onTarget(tip)) throw new Error(`cursor not on ${what} (something covers it?)`);
    }
    hoverEvents(tip, x, y);
    const base = { bubbles: true, cancelable: true, composed: true, clientX: x, clientY: y, button: 0, view: window };
    const pointer = { ...base, pointerId: 1, pointerType: "mouse", isPrimary: true };
    cursor.style.transform = "translate(-3px, -2px) scale(0.86)";
    ripple(x, y);
    tip.dispatchEvent(new PointerEvent("pointerdown", { ...pointer, buttons: 1 }));
    tip.dispatchEvent(new MouseEvent("mousedown", { ...base, buttons: 1 }));
    const focusable = tip.closest("input, button, select, textarea, a, [tabindex], [contenteditable=true]");
    if (focusable && typeof focusable.focus === "function") focusable.focus({ preventScroll: true });
    await sleep(85);
    tip.dispatchEvent(new PointerEvent("pointerup", { ...pointer, buttons: 0 }));
    tip.dispatchEvent(new MouseEvent("mouseup", { ...base, buttons: 0 }));
    tip.dispatchEvent(new MouseEvent("click", { ...base, buttons: 0 }));
    cursor.style.transform = "translate(-3px, -2px)";
    await sleep(240);
    return el;
  }

  // ---- Typing and form values ----------------------------------------------
  // React and friends track the value through the native setter, so plain
  // `el.value = x` is ignored. Use the prototype's setter, then fire events.
  function setNative(el, value) {
    const proto =
      el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype :
      el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  }

  async function type(target, value, { clear = true, delay = 45 } = {}) {
    const el = await resolve(target, field);
    await click(el);
    if (el.isContentEditable) {
      if (clear) {
        document.execCommand("selectAll");
        document.execCommand("delete");
      }
      for (const ch of value) {
        document.execCommand("insertText", false, ch);
        await sleep(delay * 0.75 + Math.random() * delay * 0.6);
      }
      return el;
    }
    let v = clear ? "" : el.value;
    setNative(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    for (const ch of value) {
      v += ch;
      setNative(el, v);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(delay * 0.75 + Math.random() * delay * 0.6);
    }
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return el;
  }

  // For <select>, date and other inputs where typing char by char makes no sense.
  async function setValue(target, value) {
    const el = await resolve(target, field);
    await click(el);
    setNative(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(300);
    return el;
  }

  const KEYS = { Enter: 13, Escape: 27, Tab: 9, Backspace: 8, ArrowUp: 38, ArrowDown: 40, ArrowLeft: 37, ArrowRight: 39, " ": 32 };
  async function press(key, target) {
    const el = target ? await resolve(target, field) : document.activeElement || document.body;
    const init = { key, code: key === " " ? "Space" : key, keyCode: KEYS[key] || 0, which: KEYS[key] || 0, bubbles: true, cancelable: true, composed: true };
    el.dispatchEvent(new KeyboardEvent("keydown", init));
    el.dispatchEvent(new KeyboardEvent("keyup", init));
    await sleep(120);
    return el;
  }

  async function scroll(to) {
    if (typeof to === "number") window.scrollTo({ top: to, behavior: "smooth" });
    else (await resolve(to)).scrollIntoView({ block: "center", behavior: "smooth" });
    await sleep(120);
    await settle(() => window.scrollY + window.scrollX * 10000);
  }

  // ---- Captions -------------------------------------------------------------
  function caption(t) {
    if (window.__DEMO && window.__DEMO.captionBar === false) t = "";
    let bar = document.getElementById("__cap");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "__cap";
      Object.assign(bar.style, {
        position: "fixed", left: "50%", bottom: "22px", transform: "translateX(-50%)",
        zIndex: 2147483645, background: "rgba(17,24,39,.9)", color: "#fff",
        font: "600 17px/1.4 -apple-system, Segoe UI, sans-serif", padding: "10px 18px",
        borderRadius: "10px", maxWidth: "78vw", textAlign: "center", pointerEvents: "none",
      });
      document.body.appendChild(bar);
    }
    bar.textContent = t;
    bar.style.display = t ? "block" : "none";
  }

  // ---- Step runner ----------------------------------------------------------
  const T = { sleep, $, $$, text, byText, button, field, waitFor, hover, click, type, setValue, press, scroll, caption, moveTo };
  window.__T = T;
  window.__stepResults = {};

  const json = (v) => {
    try {
      return v === undefined ? null : JSON.parse(JSON.stringify(v));
    } catch {
      return String(v);
    }
  };

  // Python starts a step and polls __stepResults, because AppleScript cannot
  // wait for a promise.
  window.__runStep = (i) => {
    const step = window.__DEMO.steps[i];
    caption(step.say);
    if (window.__rec?.startedAt != null) {
      window.__rec.marks.push({ i, t: (performance.now() - window.__rec.startedAt) / 1000, text: step.say });
    }
    window.__stepResults[i] = { status: "running" };
    Promise.resolve()
      .then(() => step.run(T))
      .then(async (value) => {
        let check = null;
        if (window.__DEMO.check) {
          try {
            check = await window.__DEMO.check(T);
          } catch (e) {
            check = { error: String(e?.message || e) };
          }
        }
        window.__stepResults[i] = { status: "done", value: json(value), check: json(check) };
      })
      .catch((e) => {
        window.__stepResults[i] = { status: "error", error: String(e?.message || e) };
      });
    return "started";
  };

  window.__runSetup = () => {
    window.__setupState = "running";
    Promise.resolve()
      .then(() => window.__DEMO.setup && window.__DEMO.setup(T))
      .then(() => { window.__setupState = "done"; })
      .catch((e) => { window.__setupState = "error: " + String(e?.message || e); });
    return "started";
  };

  return "loaded";
})();
