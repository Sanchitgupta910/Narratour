// Shows an orange button. The person clicks it and allows tab sharing (Chrome
// only lets a page record itself after a real click), then MediaRecorder
// records this tab. record.py swaps __PORT__ for the local receiver's port.
(() => {
  if (document.getElementById("__recbtn")) return "button already shown";
  const btn = document.createElement("button");
  btn.id = "__recbtn";
  btn.textContent = "● Click here to start recording";
  Object.assign(btn.style, {
    position: "fixed", top: "18px", left: "50%", transform: "translateX(-50%)", zIndex: 2147483647,
    background: "#f97316", color: "#fff", font: "700 18px -apple-system, sans-serif",
    padding: "14px 22px", border: "none", borderRadius: "12px",
    boxShadow: "0 6px 24px rgba(0,0,0,.25)", cursor: "pointer",
  });
  btn.onclick = async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 30 }, audio: false,
        preferCurrentTab: true, selfBrowserSurface: "include", surfaceSwitching: "exclude",
      });
      btn.remove();
      await new Promise((r) => setTimeout(r, 700));
      const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm";
      const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8000000 });
      const chunks = [];
      recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      window.__rec = { recorder, chunks, stream, marks: [], startedAt: null, uploaded: null, stoppedEarly: false };
      // The person pressed Chrome's "Stop sharing".
      stream.getVideoTracks()[0].addEventListener("ended", () => { window.__rec.stoppedEarly = true; });
      recorder.start(1000);
      window.__rec.startedAt = performance.now();
    } catch (e) {
      window.__recError = String(e);
      btn.textContent = "Recording was not allowed. Click to try again";
    }
  };
  document.body.appendChild(btn);

  window.__stopAndUpload = async () => {
    const rec = window.__rec;
    if (rec.recorder.state !== "inactive") {
      await new Promise((r) => { rec.recorder.onstop = r; rec.recorder.stop(); });
    }
    rec.stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(rec.chunks, { type: "video/webm" });
    try {
      const res = await fetch("http://127.0.0.1:__PORT__/upload", { method: "POST", body: blob });
      rec.uploaded = `${res.status}:${blob.size}`;
    } catch (e) {
      // The page blocked the upload (strict CSP, local network rules). Save the
      // video as a normal download instead; record.py --mux-only finishes it.
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "demo-raw.webm";
      document.body.appendChild(a);
      a.click();
      rec.uploaded = `download:${blob.size}:${e}`;
    }
    return "stopping";
  };
  return "button shown";
})();
