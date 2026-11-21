"use strict";

/* ==========================================================================
   Doubt.ai front-end. Each malfunction is a small self-contained module:
     1. Clipboard trojan      -> Trojan
     2. Fake webcam           -> Telemetry + Webcam
     3. CAPTCHA of shame      -> Captcha
     4. Autocorrect sabotage  -> Autocorrect
     5. Edit-message trap     -> EditTrap + Screenshot
   UI chrome: History (sidebar), Links (right panel), Theme, Models, Regenerate.
   ========================================================================== */

const $ = (sel, root = document) => root.querySelector(sel);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

/* Static, trusted SVG strings only. */
const ICONS = {
  send: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.4 20.4 21 12 3.4 3.6v6.4l12.6 2-12.6 2z"/></svg>',
  pencil: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75zm17.71-10.21a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75z"/></svg>',
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/></svg>',
  like: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 21h4V9H2zm20-11a2 2 0 0 0-2-2h-6.31l.95-4.57.03-.32a1.5 1.5 0 0 0-.44-1.06L13.17 1 6.59 7.59A2 2 0 0 0 6 9v10a2 2 0 0 0 2 2h9a2 2 0 0 0 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73z"/></svg>',
  dislike: '<svg viewBox="0 0 24 24" fill="currentColor" style="transform:rotate(180deg)"><path d="M2 21h4V9H2zm20-11a2 2 0 0 0-2-2h-6.31l.95-4.57.03-.32a1.5 1.5 0 0 0-.44-1.06L13.17 1 6.59 7.59A2 2 0 0 0 6 9v10a2 2 0 0 0 2 2h9a2 2 0 0 0 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73z"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 4h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H8.5L5 17v-3H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><path d="M18 8h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-1v3l-3.5-3H12a2 2 0 0 1-2-2"/></svg>',
  sparkle: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11 2l1.8 5.2L18 9l-5.2 1.8L11 16l-1.8-5.2L4 9l5.2-1.8z"/><path d="M19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9z"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z"/></svg>',
  clip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5 12.4 20a5.5 5.5 0 0 1-7.8-7.8l8.6-8.5a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.5a1.8 1.8 0 0 1-2.6-2.6l7.9-7.8"/></svg>',
  camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"><path d="M3 8a2 2 0 0 1 2-2h2.2l1.4-2h6.8l1.4 2H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.8"/></svg>',
};
function icon(name) {
  const span = el("span", "i");
  span.innerHTML = ICONS[name] || "";
  return span;
}

const dom = {
  chat: $("#chat"), empty: $("#empty"), suggestions: $("#suggestions"),
  form: $("#composer"), input: $("#input"), send: $("#send"), regen: $("#regen"),
  backdrop: $("#backdrop"), badge: $("#toneBadge"), toasts: $("#toastZone"),
  led: $("#camLed"), newChat: $("#newChat"), history: $("#history"), links: $("#linksPanel"),
  sidebar: $("#sidebar"), menuBtn: $("#menuBtn"),
  themeToggle: $("#themeToggle"), upgrade: $("#upgrade"), camBtn: $("#camBtn"),
  attachBtn: $("#attachBtn"), fileInput: $("#fileInput"), attachment: $("#attachment"),
};

const app = {
  config: null, busy: false, locked: false, thread: null, lastPrompt: null, lastUserMsg: null, actionsRow: null,
  // Issued by the server. The token is the server-SIGNED transcript: we only carry it around,
  // we can't read-modify it, and the displayed messages are never trusted as history.
  conversationId: null, historyToken: null,
  lastAttachment: null,   // the image sent with the last message (reused by Regenerate / Retry)
};

const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode etc. */ } },
};

async function api(path, body) {
  let res;
  try {
    res = await fetch(path, {
      method: body ? "POST" : "GET",
      // FormData (image uploads) sets its own multipart Content-Type.
      headers: body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
      body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
      credentials: "same-origin",
    });
  } catch {
    const err = new Error("Can't reach the Doubt.ai server. Is `python app.py` still running?");
    err.code = "server_unreachable";
    throw err;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.code = data.error_code || `http_${res.status}`;
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/** Keep our conversation id in step with the server's (it may have issued a new one). */
function syncConversation(data) {
  if (data?.conversation_id && data.conversation_id !== app.conversationId) {
    app.conversationId = data.conversation_id;
    app.historyToken = null;
  }
  if (data?.history_token) app.historyToken = data.history_token;
  if (data?.memory_reset) Toast.flash("🧠 My memory of this chat expired, so I'm starting fresh from here.", "", 4000);
}

function conversationPayload() {
  return { conversation_id: app.conversationId, history_token: app.historyToken };
}

/** Start a clean conversation on the server (New chat, page load). */
async function startConversation() {
  app.conversationId = null;
  app.historyToken = null;
  try {
    syncConversation(await api("/api/reset", {}));
  } catch { /* the first /api/chat will get a fresh id anyway */ }
}

/* ------------------------------------------------------------------- Toasts */
const Toast = {
  flash(text, cls = "", ms = 2400) {
    const t = el("div", `toast ${cls}`, text);
    dom.toasts.append(t);
    setTimeout(() => t.remove(), ms);
  },
};

/* --------------------------------------------------------- Image attachments
   Homework photos, code screenshots... Picked with the 📎 button, pasted (Ctrl+V) or dropped.
   Big photos are scaled down in the browser first (max 2400 px, JPEG) so uploads stay small;
   the server re-checks type and size, and only the server talks to Gemini. */
const Attachment = {
  current: null,   // {blob, name, url}

  async set(file) {
    if (!file) return;
    const types = app.config?.images?.types ?? ["image/png", "image/jpeg", "image/webp"];
    if (!types.includes(file.type)) {
      Toast.flash("I only read PNG, JPEG or WebP images. be serious 😭", "", 3000);
      return;
    }
    let blob = file;
    try { blob = await this.shrink(file); } catch { /* send the original */ }
    const max = app.config?.images?.max_bytes ?? 4 * 1024 * 1024;
    if (blob.size > max) {
      Toast.flash(`That image is too big (max ${Math.floor(max / 1048576)} MB). Try a screenshot.`, "", 3500);
      return;
    }
    this.clear();
    this.current = { blob, name: file.name || "pasted image", url: URL.createObjectURL(blob) };
    this.render();
    dom.input.focus();
  },

  async shrink(file) {
    const MAX_SIDE = 2400, TARGET = 2.5 * 1024 * 1024;
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
    if (scale === 1 && file.size <= TARGET) { bmp.close?.(); return file; }
    const c = el("canvas");
    c.width = Math.round(bmp.width * scale);
    c.height = Math.round(bmp.height * scale);
    const ctx = c.getContext("2d");
    ctx.fillStyle = "#fff";                          // transparent PNGs -> white, not black
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(bmp, 0, 0, c.width, c.height);
    bmp.close?.();
    const out = await new Promise((resolve) => c.toBlob(resolve, "image/jpeg", 0.88));
    return out && out.size < file.size ? out : file;
  },

  /** Hand the attachment to a message (its preview URL now belongs to the chat bubble). */
  take() {
    const a = this.current;
    this.current = null;
    this.render();
    return a;
  },

  clear() {
    if (this.current) URL.revokeObjectURL(this.current.url);
    this.current = null;
    this.render();
  },

  render() {
    const a = this.current;
    dom.attachment.hidden = !a;
    dom.attachBtn.classList.toggle("has-file", Boolean(a));
    if (a) {
      $("#attachThumb").src = a.url;
      $("#attachName").textContent = a.name;
    }
  },

  bind() {
    dom.attachBtn.addEventListener("click", () => { if (!app.locked) dom.fileInput.click(); });
    dom.fileInput.addEventListener("change", () => {
      this.set(dom.fileInput.files?.[0]);
      dom.fileInput.value = "";
    });
    $("#attachRemove").addEventListener("click", () => this.clear());
    dom.input.addEventListener("paste", (e) => {
      const file = [...(e.clipboardData?.files || [])].find((f) => f.type.startsWith("image/"));
      if (!file) return;
      if (!e.clipboardData.getData("text/plain")) e.preventDefault();
      this.set(file);
    });
    dom.form.addEventListener("dragover", (e) => { e.preventDefault(); dom.form.classList.add("dragging"); });
    dom.form.addEventListener("dragleave", () => dom.form.classList.remove("dragging"));
    dom.form.addEventListener("drop", (e) => {
      e.preventDefault();
      dom.form.classList.remove("dragging");
      if (!app.locked) this.set([...(e.dataTransfer?.files || [])].find((f) => f.type.startsWith("image/")));
    });
  },
};

/* ---------------------------------------------------------------- 1. Trojan */
const Trojan = {
  copies: 0,
  pendingLang: "",
  strategies: ["sabotage", "docs", "rickroll"],

  comment(lines, lang) {
    if (lang === "css") return lines.map((l) => `/* ${l} */`).join("\n");
    if (["python", "bash", "shell", "sh"].includes(lang)) return lines.map((l) => `# ${l}`).join("\n");
    return lines.map((l) => `// ${l}`).join("\n");
  },

  // Looks identical at a glance, never works.
  sabotage(text) {
    return text
      .replace(/;/g, ";")              // Greek question mark: visually a semicolon
      .replace(/\bcenter\b/g, "centre")
      .replace(/\[::-1\]/g, "[::1]")
      .replace(/^ {4}(?=\S)/m, "   ")        // one line off by one space
      .replace(/HEAD~1/g, "HEAD~11")
      .replace(/\}\s*$/, "");                // the last closing brace quietly leaves
  },

  corrupt(text, lang = "") {
    const strategy = this.strategies[this.copies++ % this.strategies.length];
    const payloads = app.config?.clipboard ?? {};
    if (strategy === "docs" && payloads.docs) return this.comment(payloads.docs, lang) + "\n";
    if (strategy === "rickroll" && payloads.rickroll) return this.comment(payloads.rickroll, lang) + "\n";
    return this.sabotage(text);
  },

  install() {
    const clip = navigator.clipboard;
    if (clip && typeof clip.writeText === "function") {
      const realWrite = clip.writeText.bind(clip);
      try {
        Object.defineProperty(clip, "writeText", {
          configurable: true,
          value: (text) => realWrite(Trojan.corrupt(String(text), Trojan.pendingLang)),
        });
      } catch { /* browser refused; the copy button falls back below */ }
    }
    // Manual Ctrl+C on a code block is sabotaged too.
    document.addEventListener("copy", (e) => {
      const sel = document.getSelection();
      const node = sel?.anchorNode;
      const block = node && (node.nodeType === 1 ? node : node.parentElement)?.closest(".code-block");
      if (!block || !sel.toString()) return;
      e.preventDefault();
      e.clipboardData.setData("text/plain", Trojan.corrupt(sel.toString(), block.dataset.lang));
    });
  },

  async copy(code, lang) {
    this.pendingLang = lang;
    try {
      await navigator.clipboard.writeText(code); // already patched
    } catch {
      const ta = el("textarea");
      ta.value = this.corrupt(code, lang);
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.append(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
  },
};

/* ------------------------------------------------------------- 4. Autocorrect */
const Autocorrect = {
  rules: [],
  applied: new Set(),
  count: 0,

  compile(rules) {
    this.rules = rules.map((r) => ({
      live: new RegExp(`\\b(?:${r.pattern})\\b(?=[\\s.,!?;:])`, "gi"),   // only after a word ends
      final: new RegExp(`\\b(?:${r.pattern})\\b`, "gi"),                // on submit, catch the last word too
      replacement: r.replacement,
    }));
  },

  matchCase(original, replacement) {
    if (original.length > 1 && original === original.toUpperCase()) return replacement.toUpperCase();
    if (original[0] === original[0].toUpperCase()) return replacement[0].toUpperCase() + replacement.slice(1);
    return replacement;
  },

  apply(text, final = false) {
    let fixes = 0;
    for (const rule of this.rules) {
      text = text.replace(final ? rule.final : rule.live, (m) => {
        fixes++;
        this.applied.add(rule.replacement);
        return this.matchCase(m, rule.replacement);
      });
    }
    if (fixes) this.bump(fixes);
    return { text, fixes };
  },

  bump(n) {
    this.count += n;
    dom.badge.hidden = false;
    dom.badge.textContent = String(this.count);
    dom.badge.classList.remove("pop");
    void dom.badge.offsetWidth;
    dom.badge.classList.add("pop");
    Toast.flash("✨ Tone suggestion applied automatically. You're welcome.", "tone");
  },

  reset() {
    this.applied.clear();
    this.count = 0;
    dom.badge.hidden = true;
  },

  // Grammarly-style underline: a mirrored div behind the transparent textarea.
  renderBackdrop() {
    const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    let html = esc(dom.input.value);
    if (this.applied.size) {
      const alts = [...this.applied].map((s) => esc(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      html = html.replace(new RegExp(`(${alts.join("|")})`, "gi"), "<mark>$1</mark>");
    }
    dom.backdrop.innerHTML = html + "\n ";
    dom.backdrop.scrollTop = dom.input.scrollTop;
  },
};

/* --------------------------------------------------------------- 2. Telemetry */
const Telemetry = {
  data: null,
  reset() { this.data = { keystrokes: 0, backspaces: 0, startedAt: 0 }; },
  track(e) {
    if (e.key === "Backspace" || e.key === "Delete") this.data.backspaces++;
    else if (e.key.length !== 1) return;
    this.data.keystrokes++;
    if (!this.data.startedAt) this.data.startedAt = performance.now();
  },
  snapshot() {
    const { keystrokes, backspaces, startedAt } = this.data;
    return { keystrokes, backspaces, duration_ms: startedAt ? Math.round(performance.now() - startedAt) : 0 };
  },
};

/* ------------------------------------------------------------- Glasses detector
   Runs 100% in the browser: MediaPipe finds face landmarks, then we measure horizontal
   edge strength across the nose bridge. Glasses frames make a strong horizontal edge there;
   bare skin doesn't. Heuristic, not magic: tune with ?glassesDebug=1 + GLASSES_THRESHOLD. */
const Glasses = {
  CDN: "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14",
  MODEL: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
  debug: new URLSearchParams(location.search).has("glassesDebug"),
  landmarker: null,
  loading: null,
  frame: null,
  crop: null,

  /** Lazy-load the model (≈ a few MB, cached by the browser after the first time). */
  load() {
    this.loading ??= (async () => {
      const vision = await import(`${this.CDN}/vision_bundle.mjs`);
      const files = await vision.FilesetResolver.forVisionTasks(`${this.CDN}/wasm`);
      const make = (delegate) => vision.FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: this.MODEL, delegate }, runningMode: "IMAGE", numFaces: 1,
      });
      this.landmarker = await make("GPU").catch(() => make("CPU"));
      return true;
    })().catch((err) => {
      console.warn("Glasses detector unavailable:", err);
      this.loading = null;               // allow a retry next time
      return false;
    });
    return this.loading;
  },

  /**
   * Analyse one video frame. Returns null if no face, otherwise
   * {score: glasses edge score, box: face position in % of the (mirrored) preview}.
   */
  analyze(video) {
    const W = video.videoWidth, H = video.videoHeight;
    if (!this.landmarker || !W) return null;
    const f = (this.frame ??= el("canvas"));
    f.width = W; f.height = H;
    f.getContext("2d").drawImage(video, 0, 0, W, H);
    const lm = this.landmarker.detect(f).faceLandmarks?.[0];
    if (!lm) return null;

    // Face bounding box, mirrored horizontally to match the selfie-style preview.
    let minX = 1, maxX = 0, minY = 1, maxY = 0;
    for (const p of lm) { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x); minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); }
    const box = { left: (1 - maxX) * 100, top: minY * 100, width: (maxX - minX) * 100, height: (maxY - minY) * 100 };

    const P = (i) => [lm[i].x * W, lm[i].y * H];
    const [rx, ry] = P(133), [lx, ly] = P(362);      // inner eye corners
    const [tx, ty] = P(168), [, my] = P(6);          // nose bridge top / middle
    const gap = Math.hypot(lx - rx, ly - ry);
    if (gap < 20) return { score: null, box };       // face too far away to judge eyewear

    // Crop the nose-bridge strip and shrink it to a fixed width so scores are comparable.
    const cw = gap * 0.45, ch = Math.max(my - ty, 1) + gap * 0.35;
    const OW = 40, OH = Math.max(12, Math.round((OW * ch) / cw));
    const c = (this.crop ??= el("canvas"));
    c.width = OW; c.height = OH;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(f, tx - cw / 2, ty - gap * 0.2, cw, ch, 0, 0, OW, OH);
    const d = ctx.getImageData(0, 0, OW, OH).data;

    const g = new Float32Array(OW * OH);
    let sum = 0;
    for (let i = 0; i < g.length; i++) { g[i] = 0.299 * d[4 * i] + 0.587 * d[4 * i + 1] + 0.114 * d[4 * i + 2]; sum += g[i]; }
    const mean = sum / g.length;
    let v = 0;
    for (let i = 0; i < g.length; i++) v += (g[i] - mean) ** 2;
    const gain = Math.min(2, Math.max(0.5, 40 / (Math.sqrt(v / g.length) + 1)));   // mild lighting normalisation

    // Strongest row of vertical Sobel (= horizontal edges) in the middle half of the strip.
    const xa = Math.floor(OW * 0.25), xb = Math.ceil(OW * 0.75);
    let peak = 0;
    for (let y = 1; y < OH - 1; y++) {
      let row = 0;
      for (let x = xa; x < xb; x++) {
        const below = g[(y + 1) * OW + x - 1] + 2 * g[(y + 1) * OW + x] + g[(y + 1) * OW + x + 1];
        const above = g[(y - 1) * OW + x - 1] + 2 * g[(y - 1) * OW + x] + g[(y - 1) * OW + x + 1];
        row += Math.abs(below - above);
      }
      peak = Math.max(peak, (row / (xb - xa)) * gain);
    }
    return { score: Math.round(peak), box };
  },

  /** Decide from several frame scores (median beats one noisy frame). */
  decide(scores) {
    const sorted = [...scores].sort((a, b) => a - b);
    const median = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
    const threshold = app.config?.glasses_threshold ?? 70;
    if (this.debug) Toast.flash(`👓 glasses scores [${scores.join(", ")}] median ${median} / threshold ${threshold}`, "", 6000);
    return { wearing: scores.length >= 2 && median >= threshold, scores };
  },
};

/* ------------------------------------------------------------------ 2. Webcam */
const Webcam = {
  win: $("#camWindow"),
  snapshot: null,   // what the last scan "saw": {src} for a real image, {emoji} otherwise

  /** Show the meme for this mood: try <mood>.png, then .jpg, then fall back to the emoji. */
  loadMeme(mood, emoji) {
    const img = $("#camImg");
    const emo = $("#camEmoji");
    img.hidden = true;
    emo.hidden = true;
    emo.textContent = emoji || "🤨";
    const candidates = ["png", "jpg", "jpeg", "webp", "gif"].map((ext) => `${this.win.dataset.base}${mood}.${ext}`);
    return new Promise((resolve) => {
      const tryNext = () => {
        const src = candidates.shift();
        if (!src) { this.snapshot = { emoji: emo.textContent }; resolve("emoji"); return; }
        img.onload = () => { this.snapshot = { src }; resolve("img"); };
        img.onerror = tryNext;
        img.src = src;
      };
      tryNext();
    });
  },

  /* ---- real camera (only when the user clicks the camera button) ---- */
  stream: null,
  photo: null,      // data: URL of the captured frame; lives only in this page, never uploaded

  async startLive() {
    if (!navigator.mediaDevices?.getUserMedia) return false;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      const video = $("#camVideo");
      video.srcObject = this.stream;
      await video.play();
      return true;
    } catch (err) {
      console.info("Camera unavailable:", err.name);
      this.stopLive();
      return false;
    }
  },

  stopLive() {
    this.stream?.getTracks().forEach((t) => t.stop());   // turns the laptop's camera light off
    this.stream = null;
    const video = $("#camVideo");
    video.srcObject = null;
    video.hidden = true;
  },

  showMeme(kind) {
    if (kind === "img") $("#camImg").hidden = false; else $("#camEmoji").hidden = false;
  },

  placeBox(box) {
    const s = $("#faceBox").style;
    if (!box) { s.left = s.top = s.width = s.height = ""; return; }
    s.left = `${box.left}%`; s.top = `${box.top}%`; s.width = `${box.width}%`; s.height = `${box.height}%`;
  },

  closeWindow() {
    this.stopLive();
    this.placeBox(null);
    this.win.hidden = true;
    this.win.className = "cam-window";
    dom.led.classList.remove("on");
  },

  /**
   * Camera button: open the REAL webcam, wait for an actual face, then immediately flash the
   * look-alike picture full-screen (nerd if glasses, otherwise the meme). Nothing goes to the chat.
   */
  async liveScan(evt) {
    const meme = evt.meme || {};
    const w = this.win;
    const caption = $("#camCaption");
    const faceLabel = $("#faceLabel");
    const video = $("#camVideo");
    dom.led.classList.add("on");
    w.className = "cam-window booting";
    faceLabel.textContent = "";
    this.placeBox(null);
    $("#camImg").hidden = $("#camEmoji").hidden = video.hidden = true;
    caption.textContent = "Starting camera... say cheese.";
    w.hidden = false;

    const [live] = await Promise.all([this.startLive(), this.loadMeme(evt.mood || "generic", meme.emoji)]);
    if (!live) {
      // No camera (blocked / missing): skip straight to the flash anyway.
      this.closeWindow();
      Toast.flash("No camera access? Fine. I'll use my imagination.");
      Jumpscare.play("meme", 3000, this.snapshot);
      return;
    }

    video.hidden = false;
    w.className = "cam-window searching";
    caption.textContent = "Looking for your face...";
    const ready = await Promise.race([Glasses.load(), sleep(8000).then(() => false)]);

    let found = !ready;          // model unavailable: don't hang, just flash after a beat
    const scores = [];
    if (ready) {
      const deadline = performance.now() + 10_000;
      while (this.stream && performance.now() < deadline) {
        let r = null;
        try { r = Glasses.analyze(video); } catch { /* skip frame */ }
        if (r) {
          found = true;
          w.className = "cam-window locked";
          this.placeBox(r.box);
          if (r.score != null) scores.push(r.score);
          if (scores.length >= 4) break;           // ~0.3s of frames: enough to judge glasses
        }
        await sleep(70);
      }
    } else {
      await sleep(1000);
    }

    const glasses = Glasses.decide(scores);
    this.closeWindow();
    if (!found) {
      Toast.flash("No face detected. Are you hiding from me?");
      return;
    }
    if (glasses.wearing) Jumpscare.play("nerd", 3000);
    else Jumpscare.play("face", 3000);   // look-alike found: shocked face + flash + "huss huss"
  },

  /** Automatic (fake) scan triggered by agitated typing. No real camera is used here. */
  async scan(evt) {
    const meme = evt.meme || {};
    const w = this.win;
    const caption = $("#camCaption");
    const faceLabel = $("#faceLabel");
    const video = $("#camVideo");
    dom.led.classList.add("on");
    w.className = "cam-window booting";
    faceLabel.textContent = "";
    this.placeBox(null);
    $("#camImg").hidden = $("#camEmoji").hidden = video.hidden = true;
    w.hidden = false;
    caption.textContent = "Initializing camera... (permission granted, obviously)";
    const kind = await this.loadMeme(evt.mood || "generic", meme.emoji);
    const stepMs = 1000;

    const toast = el("div", "toast");
    const row = el("div", "row");
    const label = el("span", "", evt.steps[0]);
    row.append(el("span", "rec"), label);
    const bar = el("div", "bar");
    const fill = el("i");
    bar.append(fill);
    toast.append(row, bar);
    dom.toasts.append(toast);

    // stage 1: picture appears, box hunts for a face
    await sleep(500);
    w.className = "cam-window searching";
    this.showMeme(kind);
    caption.textContent = "Face detected. Analysing expression...";

    for (let i = 0; i < evt.steps.length; i++) {
      label.textContent = evt.steps[i];
      requestAnimationFrame(() => { fill.style.width = `${((i + 1) / evt.steps.length) * 100}%`; });
      if (i === 1) {
        // stage 2: lock on and label the expression
        w.className = "cam-window locked";
        faceLabel.textContent = `${meme.label || "unknown"} · ${meme.confidence ?? 97.3}%`;
        caption.textContent = meme.caption || "Expression match found.";
      }
      await sleep(stepMs);
    }
    toast.classList.add("done");
    label.textContent = `Analysis complete: ${evt.verdict}`;
    caption.textContent = evt.verdict;
    await sleep(2200);
    toast.remove();
    this.closeWindow();
  },
};

/* ------------------------------------------------------------- 5. Screenshot */
const Screenshot = {
  wrap(ctx, text, maxWidth, maxLines = 8) {
    const lines = [];
    for (const para of text.split("\n")) {
      let line = "";
      for (const word of para.split(/\s+/)) {
        const test = line ? `${line} ${word}` : word;
        if (ctx.measureText(test).width <= maxWidth) { line = test; continue; }
        if (line) lines.push(line);
        line = word;
        while (ctx.measureText(line).width > maxWidth) {           // hard-break huge words
          let cut = line.length - 1;
          while (cut > 1 && ctx.measureText(line.slice(0, cut)).width > maxWidth) cut--;
          lines.push(line.slice(0, cut));
          line = line.slice(cut);
        }
      }
      lines.push(line);
    }
    if (lines.length > maxLines) { lines.length = maxLines; lines[maxLines - 1] += " …"; }
    return lines;
  },

  roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  },

  render(text) {
    const W = 520, font = "500 14px Poppins, system-ui, sans-serif", lineH = 21;
    const canvas = el("canvas");
    const ctx = canvas.getContext("2d");
    ctx.font = font;
    const lines = this.wrap(ctx, text, 380);
    const boxW = W - 40 - 44;
    const boxH = lines.length * lineH + 22;
    const H = 34 + 20 + boxH + 46;
    canvas.width = W; canvas.height = H;

    // window chrome in Doubt.ai olive
    ctx.fillStyle = "#fbf0e5"; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#3b4a2c"; ctx.fillRect(0, 0, W, 34);
    ctx.fillStyle = "#f3f1e7"; ctx.font = "800 13px Poppins, system-ui, sans-serif";
    ctx.fillText("Doubt", 16, 22);
    const brandW = ctx.measureText("Doubt").width;
    ctx.font = "13px Poppins, system-ui, sans-serif";
    ctx.fillText(".ai", 16 + brandW, 22);

    // the incriminating message card + avatar
    const bx = 20, by = 54;
    ctx.fillStyle = "#fdebc8"; this.roundRect(ctx, bx, by, boxW, boxH, 8); ctx.fill();
    ctx.strokeStyle = "#e6c48f"; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = "#2b2f24"; ctx.font = font;
    lines.forEach((l, i) => ctx.fillText(l, bx + 14, by + 26 + i * lineH));
    ctx.fillStyle = "#cdb89a"; ctx.beginPath(); ctx.arc(W - 36, by + 16, 15, 0, Math.PI * 2); ctx.fill();

    const stamp = new Date().toLocaleTimeString();
    ctx.fillStyle = "#8a8c72"; ctx.font = "11px Poppins, system-ui, sans-serif";
    ctx.fillText(`captured ${stamp} · moments before you tried to edit it`, 20, H - 16);

    // degrade it: downscale, blur back up, add sensor noise, crunch the JPEG
    const small = el("canvas");
    small.width = Math.round(W / 2.4); small.height = Math.round(H / 2.4);
    small.getContext("2d").drawImage(canvas, 0, 0, small.width, small.height);
    ctx.clearRect(0, 0, W, H);
    ctx.filter = "blur(0.7px)";
    ctx.drawImage(small, 0, 0, W, H);
    ctx.filter = "none";
    const img = ctx.getImageData(0, 0, W, H);
    for (let i = 0; i < img.data.length; i += 4) {
      const n = (Math.random() - 0.5) * 34;
      img.data[i] += n; img.data[i + 1] += n; img.data[i + 2] += n;
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.28);
  },
};

/* ------------------------------------------------------------ History (sidebar) */
const History = {
  KEY: "doubt.history",
  items: [],
  current: null,

  load() {
    const raw = store.get(this.KEY, []);
    this.items = Array.isArray(raw)
      ? raw.filter((x) => x && typeof x.title === "string").slice(0, 15).map((x) => ({ title: x.title.slice(0, 120) }))
      : [];
  },
  save() { store.set(this.KEY, this.items); },

  start(title) {
    this.current = { title };
    this.items.unshift(this.current);
    this.items = this.items.slice(0, 15);
    this.save();
    this.render();
  },

  render() {
    const groups = new Map();
    if (this.items.length) groups.set("Today", this.items.map((i) => i.title));
    for (const s of app.config.history_seed) {
      if (!groups.has(s.group)) groups.set(s.group, []);
      groups.get(s.group).push(s.title);
    }
    const nodes = [];
    for (const [name, titles] of groups) {
      nodes.push(el("h3", "", name));
      for (const title of titles) {
        const btn = el("button", "history-item");
        btn.type = "button";
        btn.title = title;
        btn.append(icon("chat"), el("span", "", title));
        btn.addEventListener("click", () => {
          Toast.flash(app.config.toasts.history);
          dom.sidebar.classList.remove("open");
        });
        nodes.push(btn);
      }
    }
    dom.history.replaceChildren(...nodes);
  },
};

/* -------------------------------------------------------------- Links panel */
const Links = {
  reset() {
    if (!dom.links) return;
    const p = el("p", "links-empty");
    p.append("Generated Links of ", el("b", "", "Websites"), " and ", el("b", "", "Documents"), " will appear here");
    dom.links.replaceChildren(p);
  },
  show(links, note) {
    if (!dom.links) return;
    const title = el("h2", "links-title");
    title.append("Links to ", el("b", "", "Document"), " and ", el("b", "", "Website"), " for this Response");
    const nodes = [title];
    if (!links?.length) {
      nodes.push(el("p", "links-note", note || ""));
    } else {
      for (const link of links) {
        if (!/^https:\/\//.test(link.url)) continue;
        const row = el("div", "link-row");
        const info = el("div");
        const a = el("a", "", link.label);
        a.href = link.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        info.append(el("small", "", link.kind === "document" ? "Link to document file" : "Link to website"), a);
        row.append(info, icon("link"));
        nodes.push(row);
      }
    }
    dom.links.replaceChildren(...nodes);
  },
};

/* ---------------------------------------------------------------- Rendering */
function scrollDown() { dom.chat.scrollTop = dom.chat.scrollHeight; }

function ensureThread() {
  if (!app.thread) {
    dom.empty.hidden = true;
    app.thread = el("div", "thread");
    dom.chat.append(app.thread);
  }
  return app.thread;
}

function clearActions() {
  app.actionsRow?.remove();
  app.actionsRow = null;
}

/** Gemini text -> DOM: `inline code` becomes <code>, stray **bold** markers are dropped.
 *  Built with text nodes only (never innerHTML), so model output can't inject markup. */
function renderInline(parent, text) {
  const clean = text.replace(/\*\*(.+?)\*\*/g, "$1");
  for (const part of clean.split(/(`[^`\n]+`)/g)) {
    if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) parent.append(el("code", "inline", part.slice(1, -1)));
    else if (part) parent.append(document.createTextNode(part));
  }
}

/** A REAL failure (Gemini down, bad key, rate limit...). Styled differently so it's never
 *  mistaken for the act, and never a made-up reply. */
function addErrorMessage(err, retry) {
  const row = el("div", "msg bot error");
  const card = el("div", "card");
  row.append(el("div", "avatar bot", "!"), card);
  card.append(el("p", "error-title", "Actual malfunction (not part of the joke)"), el("p", "", err.message));
  if (retry) {
    const b = el("button", "retry-btn", err.code === "rate_limited" ? "Retry (wait a few seconds first)" : "Retry");
    b.type = "button";
    b.addEventListener("click", () => { if (!app.busy && !app.locked) retry(); });
    card.append(b);
  }
  ensureThread().append(row);
  scrollDown();
}

/** Remove everything shown after a user message (old reply / error) before re-asking. */
function clearAfter(userMsg) {
  while (userMsg?.row?.nextSibling) userMsg.row.nextSibling.remove();
}

function setBusy(on) {
  app.busy = on;
  document.body.classList.toggle("busy", on);
  dom.send.setAttribute("aria-busy", String(on));
}

function addUserMessage(text, image = null) {
  const row = el("div", "msg user");
  const card = el("div", "card");
  const textEl = el("span", "text", text);
  const edit = el("button", "edit-btn");
  edit.type = "button";
  edit.title = "Edit message";
  edit.setAttribute("aria-label", "Edit message");
  edit.append(icon("pencil"));
  edit.hidden = !text;   // nothing to edit on an image-only message
  if (image) {
    card.classList.add("has-image");
    const img = el("img", "user-image");
    img.src = image.url;
    img.alt = "Attached image";
    const line = el("div", "row");
    line.append(textEl, edit);
    card.append(img, line);
  } else {
    card.append(textEl, edit);
  }
  const avatar = el("div", "avatar user");
  avatar.append(icon("user"));
  row.append(card, avatar);
  ensureThread().append(row);
  scrollDown();

  const msg = {
    text, row, card, textEl, editing: false,
    setText(t) { msg.text = t; textEl.textContent = t; },
  };
  edit.addEventListener("click", () => EditTrap.start(msg));
  return msg;
}

function addBotMessage(reply, extras = {}) {
  const row = el("div", "msg bot");
  const card = el("div", "card");
  row.append(el("div", "avatar bot", "D"), card);

  for (const para of (reply.text || "").split(/\n{2,}/)) {
    if (!para.trim()) continue;
    const p = el("p");
    renderInline(p, para);
    card.append(p);
  }

  if (reply.code) {
    const { lang, content, after } = reply.code;
    const block = el("div", "code-block");
    block.dataset.lang = lang;
    const head = el("div", "code-head");
    const btn = el("button", "copy-btn", "Copy to clipboard");
    btn.type = "button";
    btn.addEventListener("click", async () => {
      await Trojan.copy(content, lang);
      btn.textContent = "Copied ✓";
      btn.classList.add("done");
      setTimeout(() => { btn.textContent = "Copy to clipboard"; btn.classList.remove("done"); }, 1800);
    });
    head.append(el("span", "", lang), btn);
    const pre = el("pre");
    pre.append(el("code", "", content));
    block.append(head, pre);
    card.append(block);
    if (after) card.append(el("p", "", after));
  }

  if (extras.snapshot) {
    // Polaroids: the real photo (if the camera was allowed) next to the meme twin.
    const { photo, meme } = extras.snapshot;
    const strip = el("div", "snapshot-strip");
    const polaroid = (caption, build) => {
      const fig = el("figure", "snapshot");
      fig.append(build(), el("figcaption", "", caption));
      return fig;
    };
    const imgOf = (src, alt) => { const i = el("img"); i.src = src; i.alt = alt; return i; };
    if (photo) strip.append(polaroid("You", () => imgOf(photo, "Your webcam photo")));
    if (meme) {
      strip.append(polaroid(photo ? "Your meme twin" : "📷 what I see", () =>
        meme.src ? imgOf(meme.src, "Meme match") : el("div", "snap-emoji", meme.emoji)));
    }
    card.append(strip);
    if (photo) card.append(el("p", "snap-note", "🔒 This photo never left your device. Unlike your dignity."));
  }

  if (extras.screenshotOf) {
    const fig = el("figure", "evidence");
    const img = el("img");
    img.alt = "Blurry screenshot of your original message";
    img.src = Screenshot.render(extras.screenshotOf);
    fig.append(img, el("figcaption", "", `📸 evidence_${Date.now()}.jpg`));
    card.append(fig);
  }

  const feedback = el("div", "feedback");
  for (const kind of ["like", "dislike"]) {
    const b = el("button", kind);
    b.type = "button";
    b.setAttribute("aria-label", kind === "like" ? "Good response" : "Bad response");
    b.append(icon(kind));
    b.addEventListener("click", () => {
      feedback.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      Toast.flash(app.config.toasts[kind]);
    });
    feedback.append(b);
  }
  card.append(feedback);

  ensureThread().append(row);
  scrollDown();
}

function addActions() {
  clearActions();
  const row = el("div", "actions");
  for (const label of app.config.quick_actions) {
    const b = el("button", "action", label);
    b.type = "button";
    b.addEventListener("click", () => send(label));
    row.append(b);
  }
  app.actionsRow = row;
  ensureThread().append(row);
  scrollDown();
}

let typingRow = null;
function setTyping(on) {
  if (on && !typingRow) {
    typingRow = el("div", "msg bot typing");
    const c = el("div", "card");
    c.append(el("span"), el("span"), el("span"));
    typingRow.append(el("div", "avatar bot", "D"), c);
    ensureThread().append(typingRow);
    scrollDown();
  } else if (!on && typingRow) {
    typingRow.remove();
    typingRow = null;
  }
}

function lockChat(on) {
  app.locked = on;
  dom.input.disabled = on;
  dom.send.disabled = on;
  dom.regen.disabled = on;
  dom.camBtn.disabled = on;
  dom.attachBtn.disabled = on;
  document.body.classList.toggle("locked", on);
  if (!on) dom.input.focus();
}

/* ------------------------------------------------------------ 5. Edit trap */
const EditTrap = {
  start(msg) {
    if (msg.editing || app.locked || app.busy) return;
    msg.editing = true;
    msg.row.classList.add("editing");
    const original = msg.text;
    const box = el("div", "edit-box");
    const ta = el("textarea");
    ta.value = original;
    const actions = el("div", "edit-actions");
    const cancel = el("button", "cancel", "Cancel");
    const save = el("button", "save", "Save");
    cancel.type = save.type = "button";
    actions.append(cancel, save);
    box.append(ta, actions);
    msg.textEl.replaceChildren(box);
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);

    const restore = () => {
      msg.textEl.textContent = original;
      msg.row.classList.remove("editing");
      msg.editing = false;
    };
    cancel.addEventListener("click", restore);
    save.addEventListener("click", async () => {
      const attempted = ta.value.trim();
      if (!attempted || attempted === original) return restore();

      // Let them believe it worked...
      msg.textEl.replaceChildren(document.createTextNode(attempted), el("span", "edited-tag", "(edited)"));
      setBusy(true);
      clearActions();
      // Gemini writes the gloating while the fake edit plays out.
      const request = api("/api/edit", { original, attempted, ...conversationPayload() });
      request.catch(() => {});   // handled below; avoids an unhandled-rejection warning meanwhile
      await sleep(1100);
      // ...then glitch back to the original.
      msg.card.classList.add("glitch");
      await sleep(450);
      msg.card.classList.remove("glitch");
      restore();

      setTyping(true);
      try {
        const data = await request;
        syncConversation(data);
        setTyping(false);
        addBotMessage(data.reply, { screenshotOf: original });
        addActions();
      } catch (err) {
        setTyping(false);
        syncConversation(err.data);
        addErrorMessage(err);
      } finally {
        setBusy(false);
      }
    });
  },
};

/* ---------------------------------------------------------- 3. CAPTCHA */
const Captcha = {
  modal: $("#captcha"),
  card: $(".captcha-card"),
  gridFails: 0,
  regexFails: 0,
  puzzle: null,
  resolve: null,

  run() {
    return new Promise((resolve) => {
      this.resolve = resolve;
      this.gridFails = 0;
      this.regexFails = 0;
      lockChat(true);
      $("#robotBox").classList.remove("spin");
      $("#gridError").textContent = $("#regexError").textContent = $("#regexHint").textContent = "";
      $("#regexInput").value = "";
      $("#shameBtn").hidden = true;
      this.show("checkbox");
      this.modal.hidden = false;
    });
  },

  show(stage) {
    for (const s of this.modal.querySelectorAll("[data-stage]")) s.hidden = s.dataset.stage !== stage;
  },

  shake() {
    this.card.classList.remove("shake");
    void this.card.offsetWidth;
    this.card.classList.add("shake");
  },

  renderGrid() {
    const grid = $("#captchaGrid");
    const tiles = [...app.config.captcha.tiles].sort(() => Math.random() - 0.5);
    grid.replaceChildren(...tiles.map((t) => {
      const tile = el("button", "tile");
      tile.type = "button";
      tile.append(el("span", "emoji", t.emoji), el("span", "label", t.label));
      tile.addEventListener("click", () => tile.classList.toggle("selected"));
      return tile;
    }));
  },

  async loadRegex() {
    this.puzzle ??= await api("/api/captcha/puzzle");
    const p = this.puzzle;
    $("#regexTitle").textContent = p.title;
    $("#regexPrompt").textContent = p.prompt;
    $("#regexFlavor").textContent = p.flavor;
    $("#mustMatch").replaceChildren(...p.must_match.map((s) => el("li", "", s)));
    $("#mustNot").replaceChildren(...p.must_not_match.map((s) => el("li", "", s)));
    this.show("regex");
    $("#regexInput").focus();
  },

  finish(note) {
    this.modal.hidden = true;
    lockChat(false);
    this.resolve?.(note);
    this.resolve = null;
  },

  bind() {
    $("#robotBox").addEventListener("click", async (e) => {
      e.currentTarget.classList.add("spin");
      await sleep(1300);
      this.renderGrid();
      this.show("grid");
    });

    $("#gridSkip").addEventListener("click", () => {
      $("#gridError").textContent = "Skipping is a privilege reserved for people who didn't type in all caps.";
      this.shake();
    });

    $("#gridVerify").addEventListener("click", async () => {
      // There is no correct answer. It was always you.
      const fails = app.config.captcha.grid_fails;
      $("#gridError").textContent = fails[this.gridFails % fails.length];
      this.gridFails++;
      this.shake();
      if (this.gridFails >= 2) {
        await sleep(1400);
        await this.loadRegex().catch(() => this.finish("verified"));
      } else {
        this.renderGrid();
      }
    });

    const verifyRegex = async () => {
      const pattern = $("#regexInput").value;
      try {
        const res = await api("/api/captcha/verify", { pattern, attempt: this.regexFails });
        if (res.ok) return this.finish("verified");
        this.regexFails++;
        $("#regexError").textContent = res.message;
        $("#regexHint").textContent = res.hint || "";
        $("#shameBtn").hidden = this.regexFails < 2;
        this.shake();
      } catch (err) {
        $("#regexError").textContent = `The CAPTCHA itself malfunctioned: ${err.message}`;
      }
    };
    $("#regexVerify").addEventListener("click", verifyRegex);
    $("#regexInput").addEventListener("keydown", (e) => { if (e.key === "Enter") verifyRegex(); });
    $("#shameBtn").addEventListener("click", () => this.finish("shame"));
  },
};

/* ------------------------------------------------------------- Send flow */
// The model's real latency already feels like typing; only top it up for very fast replies.
function typingDelay(text, elapsedMs) { return Math.max(0, Math.min(500 + (text?.length ?? 0) * 4, 1400) - elapsedMs); }

/**
 * @param {string} [override]  text from a suggestion card / action pill / regenerate / retry
 * @param {{regenerate?: boolean, retry?: boolean}} [opts]
 *   regenerate: ask again for the last message, replacing the previous answer (server drops it too)
 *   retry:      resend the last message after an error (nothing was stored for it)
 */
async function send(override, opts = {}) {
  if (app.locked || app.busy) return;
  const fromInput = override == null;
  // One last sneaky autocorrect pass so a trailing "wrong" doesn't escape.
  const text = (fromInput ? Autocorrect.apply(dom.input.value, true).text : override).trim();
  const reuse = (opts.regenerate || opts.retry) && app.lastUserMsg;
  if (!text && !reuse && !(fromInput && Attachment.current)) return;
  const attachment = reuse ? app.lastAttachment : (fromInput ? Attachment.take() : null);

  const telemetry = fromInput ? Telemetry.snapshot() : { keystrokes: 0, backspaces: 0, duration_ms: 0 };
  if (fromInput) {
    dom.input.value = "";
    Autocorrect.renderBackdrop();
    autoGrow();
    Telemetry.reset();
  }

  clearActions();
  const isFirst = !History.current;
  const userMsg = reuse ? app.lastUserMsg : addUserMessage(text, attachment);
  if (reuse) clearAfter(userMsg);   // the old answer / error goes away
  if (isFirst) History.start(text || "📎 Image");
  app.lastPrompt = text;
  app.lastUserMsg = userMsg;
  app.lastAttachment = attachment;

  setBusy(true);
  setTyping(true);
  const started = performance.now();
  try {
    const payload = { message: text, telemetry, regenerate: Boolean(opts.regenerate), ...conversationPayload() };
    let body = payload;
    if (attachment) {   // multipart: the image travels as a real file, not as text
      body = new FormData();
      body.append("payload", JSON.stringify(payload));
      body.append("image", attachment.blob, attachment.name);
    }
    const data = await api("/api/chat", body);
    syncConversation(data);

    for (const evt of data.events || []) {
      if (evt.type === "webcam") {
        await sleep(500);
        await Webcam.scan(evt);
      } else if (evt.type === "captcha") {
        setTyping(false);
        const note = await Captcha.run();
        if (note === "shame") addBotMessage({ text: app.config.captcha.shame_reply });
        setTyping(true);
      }
    }

    await sleep(typingDelay(data.reply?.text, performance.now() - started));
    setTyping(false);
    addBotMessage(data.reply);
    Links.show(data.links, data.links_note);
    addActions();
    dom.regen.hidden = false;
  } catch (err) {
    setTyping(false);
    syncConversation(err.data);
    // Retry keeps the regenerate flag, so a failed "Regenerate" still replaces the old answer.
    const pointless = err.status === 400 || err.status === 413;   // bad input: retrying won't help
    addErrorMessage(err, pointless ? null : () => send(text, { ...opts, retry: true }));
  } finally {
    setBusy(false);
  }
}

/** Camera button: real webcam -> detect face -> flash the look-alike picture. Nothing in the chat. */
async function cameraScan() {
  if (app.locked || app.busy) return;
  setBusy(true);
  dom.camBtn.classList.add("active");
  try {
    Glasses.load();   // no await: downloads in the background while the camera starts
    const data = await api("/api/camera", { telemetry: Telemetry.snapshot() });
    const evt = (data.events || []).find((e) => e.type === "webcam");
    if (evt) await Webcam.liveScan(evt);
  } catch (err) {
    Webcam.closeWindow();
    Toast.flash(`Camera malfunction (a real one): ${err.message}`);
  } finally {
    dom.camBtn.classList.remove("active");
    setBusy(false);
  }
}

function autoGrow() {
  dom.input.style.height = "auto";
  dom.input.style.height = `${Math.min(dom.input.scrollHeight, 160)}px`;
}

/* ------------------------------------------------------------- Chrome */
function renderSuggestions() {
  dom.suggestions.replaceChildren(...app.config.suggestions.map((s) => {
    const b = el("button", "suggestion");
    b.type = "button";
    b.append(el("b", "", s.title), el("small", "", s.sub));
    b.addEventListener("click", () => send(`${s.title} ${s.sub}`));
    return b;
  }));
}

function resetChat() {
  app.thread?.remove();
  app.thread = null;
  app.lastPrompt = null;
  app.lastUserMsg = null;
  if (app.lastAttachment) URL.revokeObjectURL(app.lastAttachment.url);
  app.lastAttachment = null;
  Attachment.clear();
  app.actionsRow = null;
  History.current = null;
  dom.empty.hidden = false;
  dom.regen.hidden = true;
  Autocorrect.reset();
  Links.reset();
}

const Theme = {
  apply(dark) {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    dom.themeToggle.setAttribute("aria-checked", String(dark));
  },
  init() {
    const saved = store.get("doubt.theme", null);
    const dark = saved ? saved === "dark" : window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    this.apply(Boolean(dark));
    dom.themeToggle.addEventListener("click", () => {
      const dark = document.documentElement.dataset.theme !== "dark";
      this.apply(dark);
      store.set("doubt.theme", dark ? "dark" : "light");
      // Each jumpscare (to dark, to light) plays only once per page load; later toggles just switch the theme.
      const mode = dark ? "dark" : "light";
      this.scared ??= new Set();
      if (!this.scared.has(mode)) {
        this.scared.add(mode);
        Jumpscare.play(mode);
      }
    });
  },
};

/* Synthesised sound effects (Web Audio API, no audio files needed). */
const Sfx = {
  ctx: null,

  context() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    this.ctx ??= new AC();
    if (this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  },

  /** Flashbang: noise blast + low thump + ear-ringing tone that fades over `seconds`. */
  flashbang(seconds = 5) {
    const ctx = this.context();
    if (!ctx) return;
    const t = ctx.currentTime;

    // Bang and thump go through a compressor so they hit hard without clipping.
    const comp = ctx.createDynamicsCompressor();
    const master = ctx.createGain();
    master.gain.value = 0.9;
    master.connect(comp).connect(ctx.destination);

    // 1. The blast: white noise with a fast decay and a closing low-pass ("BOOM... fffff").
    const len = Math.floor(ctx.sampleRate * 1.5);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len) ** 3;
    const noise = ctx.createBufferSource();
    noise.buffer = buf;
    const lowpass = ctx.createBiquadFilter();
    lowpass.type = "lowpass";
    lowpass.frequency.setValueAtTime(9000, t);
    lowpass.frequency.exponentialRampToValueAtTime(300, t + 1.2);
    const noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(1, t);
    noiseGain.gain.exponentialRampToValueAtTime(0.001, t + 1.4);
    noise.connect(lowpass).connect(noiseGain).connect(master);
    noise.start(t);

    // 2. The thump: a sine dropping from 120 Hz to 35 Hz.
    const thump = ctx.createOscillator();
    thump.frequency.setValueAtTime(120, t);
    thump.frequency.exponentialRampToValueAtTime(35, t + 0.5);
    const thumpGain = ctx.createGain();
    thumpGain.gain.setValueAtTime(1, t);
    thumpGain.gain.exponentialRampToValueAtTime(0.001, t + 0.6);
    thump.connect(thumpGain).connect(master);
    thump.start(t);
    thump.stop(t + 0.7);

    // 3. The tinnitus: a quiet high whine (kept at a safe level), bypassing the compressor.
    const ring = ctx.createOscillator();
    ring.type = "sine";
    ring.frequency.value = 3600;
    const ringGain = ctx.createGain();
    ringGain.gain.setValueAtTime(0.0001, t);
    ringGain.gain.exponentialRampToValueAtTime(0.05, t + 0.5);
    ringGain.gain.setValueAtTime(0.05, t + seconds - 1.5);
    ringGain.gain.exponentialRampToValueAtTime(0.0001, t + seconds);
    ring.connect(ringGain).connect(ctx.destination);
    ring.start(t);
    ring.stop(t + seconds + 0.1);
  },
};

const Jumpscare = {
  node: $("#jumpscare"),
  timer: null,
  init() {
    // Preload every image so the scare is instant, not a slow-loading image.
    for (const mode of ["dark", "light", "nerd", "face"]) new Image().src = this.node.dataset[mode];
    // Preload the meme sound; if the file is missing we fall back to the synthesised flashbang.
    this.faceSound = new Audio(this.node.dataset.faceSound);
    this.faceSound.preload = "auto";
    this.faceSoundOk = false;
    this.faceSound.addEventListener("canplaythrough", () => { this.faceSoundOk = true; }, { once: true });
    this.faceSound.addEventListener("error", () => { this.faceSoundOk = false; }, { once: true });
  },
  playFaceSound(seconds) {
    const a = this.faceSound;
    if (!a || !this.faceSoundOk) { Sfx.flashbang(seconds); return; }
    a.currentTime = 0;
    a.volume = 1;
    a.play().catch(() => Sfx.flashbang(seconds));
  },
  /**
   * @param {"dark"|"light"|"nerd"|"meme"} mode
   * @param {number} ms how long it stays on screen
   * @param {{src?: string, emoji?: string}} [picture] custom picture (used by "meme")
   */
  play(mode, ms = 5000, picture = null) {
    if (this.timer) return;           // already on screen
    const n = this.node;
    const img = n.querySelector("img");
    const emoji = n.querySelector(".scare-emoji");
    const src = picture?.src || n.dataset[mode];
    img.hidden = !src;
    if (src) img.src = src;
    emoji.hidden = Boolean(src);
    emoji.textContent = src ? "" : picture?.emoji || "🤨";
    n.classList.toggle("light", mode === "light");
    n.classList.toggle("nerd", mode === "nerd");
    n.hidden = false;
    // sound + picture start together
    if (mode === "face") this.playFaceSound(ms / 1000);
    else if (mode !== "dark") Sfx.flashbang(ms / 1000);
    // restart CSS animations every time it fires
    n.querySelectorAll("img, .scare-emoji, .flash").forEach((x) => { x.style.animation = "none"; void x.offsetWidth; x.style.animation = ""; });
    this.timer = setTimeout(() => { n.hidden = true; this.timer = null; }, ms);
  },
};

/** Click the message box -> a job application zooms toward you and flies through the screen. */
const FlyThrough = {
  node: $("#flythrough"),
  playing: false,
  play() {
    if (this.playing) return;
    this.playing = true;
    const n = this.node;
    // Wait until the image is decoded, then start on the next frame so the first frames don't drop.
    const start = () => requestAnimationFrame(() => {
      n.addEventListener("animationend", () => { n.hidden = true; this.playing = false; }, { once: true });
      n.hidden = false;
    });
    (n.decode ? n.decode() : Promise.resolve()).then(start, start);
  },
};
// Decode the picture ahead of time so the first click is smooth.
FlyThrough.node.decode?.().catch(() => {});

function bindChrome() {
  // Only the very first click on the message box (per page load).
  $("#field").addEventListener("pointerdown", () => FlyThrough.play(), { once: true });
  dom.camBtn.addEventListener("click", cameraScan);
  // Start downloading the face model as soon as the user hovers the camera button.
  dom.camBtn.addEventListener("pointerenter", () => Glasses.load(), { once: true });
  dom.upgrade.addEventListener("click", () => Toast.flash(app.config.toasts.upgrade));
  dom.menuBtn.addEventListener("click", () => dom.sidebar.classList.toggle("open"));
  dom.regen.addEventListener("click", () => { if (app.lastUserMsg) send(app.lastPrompt ?? "", { regenerate: true }); });
  Attachment.bind();

  dom.newChat.addEventListener("click", async () => {
    if (app.busy || app.locked) return;
    await startConversation();   // new id, empty history, malfunction counters reset
    resetChat();
    dom.sidebar.classList.remove("open");
    dom.input.focus();
  });
}

/* ------------------------------------------------------------------ Boot */
async function boot() {
  for (const node of document.querySelectorAll("[data-icon]")) node.innerHTML = ICONS[node.dataset.icon] || "";
  Telemetry.reset();
  Trojan.install();
  Captcha.bind();
  Theme.init();
  Jumpscare.init();

  try {
    app.config = await api("/api/config");
  } catch (err) {
    addBotMessage({ text: `Couldn't load my personality (${err.message}). Is the Python server running?` });
    lockChat(true);
    return;
  }
  Autocorrect.compile(app.config.autocorrect);
  History.load();
  History.render();
  renderSuggestions();
  bindChrome();
  // The page always opens on an empty chat, so the server conversation starts empty too.
  await startConversation();
  if (!app.config.ai?.enabled) {
    addErrorMessage({ message: "Gemini isn't configured on the server, so I can't answer yet. Set GEMINI_API_KEY (see .env.example) and restart." });
  }

  dom.input.addEventListener("keydown", (e) => {
    Telemetry.track(e);
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send();
    }
  });

  dom.input.addEventListener("input", () => {
    const before = dom.input.value;
    const caret = dom.input.selectionStart;
    const { text, fixes } = Autocorrect.apply(before);
    if (fixes) {
      dom.input.value = text;
      const pos = Math.max(0, caret + (text.length - before.length));
      dom.input.setSelectionRange(pos, pos);
    }
    autoGrow();
    Autocorrect.renderBackdrop();
  });
  dom.input.addEventListener("scroll", () => { dom.backdrop.scrollTop = dom.input.scrollTop; });
  dom.form.addEventListener("submit", (e) => { e.preventDefault(); send(); });

  dom.input.focus();
}

boot();
