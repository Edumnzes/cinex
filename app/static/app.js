"use strict";
// Cinex app — talks only to the local server (app/server.py). State lives in ~/reels/<name>/cinex.json,
// shared with Claude Code, so the page polls for changes Claude makes (new cut, chat answers).

const $ = (s) => document.querySelector(s);
const H = { "X-Cinex": "1" };
const W8 = { Regular: 400, Medium: 500, SemiBold: 600, Bold: 700, ExtraBold: 800, Black: 900 };
const PRESETS = {
  Hormozi: { font: "sans", weight: "Black", upper: true, size: 62, stroke: 6, words: 3, color: "#FFFFFF", accent: "#FFD400" },
  Minimal: { font: "sans", weight: "SemiBold", upper: false, size: 50, stroke: 0, words: 3, color: "#FFFFFF", accent: "#FF8A47" },
  Cinema: { font: "cond", weight: "Black", upper: true, size: 78, stroke: 0, words: 3, color: "#FFFFFF", accent: "#FFD400" },
};

let faces = null, name = null, st = null, words = [], wave = null, fonts = [], projectFonts = [];
let sel = null, pending = 0, pps = 60, loadedFonts = new Set(), groups = [], kept = [];

async function api(path, opt = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), opt.timeout || 20000);   // a stalled request never hangs the app
  let r, j;
  try {
    r = await fetch(path, { ...opt, signal: ctl.signal, headers: { ...H, ...(opt.headers || {}) } });
    j = await r.json().catch(() => ({}));
  } finally { clearTimeout(timer); }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const FPS = 30, HEAD = 72;      // HEAD = track-header width (--head in app.css)
const p2 = (n) => String(Math.floor(n)).padStart(2, "0");
const tcode = (t) => { t = Math.max(0, t || 0); return `${p2(t / 3600)}:${p2((t / 60) % 60)}:${p2(t % 60)}:${p2(Math.round((t % 1) * FPS) % FPS)}`; };
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} } };

function banner(text, err) {
  const b = $("#banner"); b.hidden = !text; b.textContent = text || ""; b.classList.toggle("err", !!err);
}

// ------------------------------------------------------------ projects
async function listProjects(select) {
  const ps = await api("/api/projects"); const sel = $("#project");
  sel.replaceChildren(...ps.map((p) => new Option(`${p.name} · ${fmt(p.duration)}`, p.name)));
  if (!ps.length) sel.append(new Option("nenhum projeto", ""));
  const want = select || location.hash.slice(1) || store.get("cinex.project") || (ps[0] && ps[0].name);
  if (want && ps.some((p) => p.name === want)) { sel.value = want; await openProject(want); }
}

async function openProject(n) {
  name = n; location.hash = n; store.set("cinex.project", n); sel = null; words = []; wave = null;
  const j = await api(`/api/p/${n}`);
  st = j.state; projectFonts = j.project_fonts || [];
  showJobs(j.prep, j.export);
  if (st && st.segments.length) await loadMedia();
  renderAll();
}

async function loadMedia() {
  const n = name;
  api(`/api/p/${n}/faces`).then((f) => { if (n === name) faces = f; }).catch(() => {});   // preview-only: never blocks
  [words, wave] = await Promise.all([api(`/api/p/${n}/words`), api(`/api/p/${n}/waveform`).catch(() => null)]);
  const v = $("#video"); v.src = `/api/p/${name}/preview.mp4`; $("#phempty").hidden = true;
}

async function reloadState() {
  const j = await api(`/api/p/${name}`);
  const had = st && st.segments.length;
  st = j.state; projectFonts = j.project_fonts || [];
  if (!had && st && st.segments.length) await loadMedia();
  renderAll();
}

async function save(patch) {
  Object.assign(st, patch); pending++; $("#savestate").textContent = "Salvando…";
  try { const r = await api(`/api/p/${name}/state`, { method: "PUT", body: JSON.stringify(patch) }); st.rev = r.rev; $("#savestate").textContent = "Salvo"; }
  catch (e) { $("#savestate").textContent = "Erro ao salvar: " + e.message; }
  finally { pending--; }
}
let capTimer = null;
function saveCaptions() { renderCaptionsUI(); buildGroups(); drawCaption(); renderTimeline(); clearTimeout(capTimer); capTimer = setTimeout(() => save({ captions: st.captions, keywords: st.keywords }), 500); }

// ------------------------------------------------------------ jobs (prep / export) + polling
function showJobs(prep, exp) {
  if (prep && prep.error) banner("Erro ao preparar: " + prep.error, true);
  else if (prep && prep.done === false) banner(`Preparando o projeto: ${prep.step} (${prep.pct || 0}%)`);
  else banner("");
  const box = $("#exportbox"), running = exp && exp.done === false;
  box.hidden = !exp || !exp.step;
  if (exp && exp.step) {
    $("#exportbar").style.width = (exp.pct || 0) + "%";
    $("#exportmsg").textContent = exp.error ? "Erro: " + exp.error : exp.out ? `Pronto: ${exp.out}` : `${exp.step}… ${exp.pct || 0}%`;
  }
  $("#exportbtn").disabled = !st || !st.segments.length || running;
  $("#exportbtn").textContent = running ? "Exportando…" : "Exportar";
}

async function poll() {
  if (!name) return;
  try {
    const p = await api(`/api/p/${name}/poll`);
    if (!st && p.rev >= 0) await reloadState();
    else if (st && p.rev > st.rev && !pending) await reloadState();
    showJobs(p.prep, p.export);
  } catch {}
}

// ------------------------------------------------------------ captions (same grouping rules as reels_lib)
function buildGroups() {
  kept = playOrder();                         // play order (phrases may be reordered)
  let off = 0; const toks = [], c = st.captions, fix = st.fix || {}, keys = new Set((st.keywords || []).map((k) => k.toUpperCase()));
  for (const g of kept) {
    for (const w of words) {
      const m = (w.s + w.e) / 2; if (m < g.s || m >= g.e) continue;
      const s = off + Math.max(0, w.s - g.s), e = off + Math.min(g.e, w.e) - g.s;
      if (w.w.startsWith("-") && toks.length) { toks.at(-1).d += w.w; toks.at(-1).e = e; continue; }
      let core = w.w.replace(/[,.;:]/g, ""); core = fix[core.toLowerCase()] || core;
      const d = c.upper ? core.toUpperCase() : core;
      toks.push({ d, s, e, brk: /[,.?!]$/.test(w.w), key: keys.has(d.toUpperCase()) });
    }
    g.off = off; off += g.e - g.s;
  }
  const out = []; let cur = [];
  for (const t of toks) {
    if (cur.length && (cur.length >= c.words || cur.at(-1).brk || t.s - cur.at(-1).e > 0.4)) { out.push(cur); cur = []; }
    cur.push(t);
  }
  if (cur.length) out.push(cur);
  groups = out.map((g, i) => {
    const nxt = i + 1 < out.length ? out[i + 1][0].s - 0.05 : 1e9, last = g.at(-1).e;
    return { s: Math.max(0, g[0].s - 0.05), e: nxt - last < 0.6 ? nxt : last + 0.3, w: g };
  });
}

function frameSize() { return st && st.format === "horizontal" ? [1920, 1080] : [1080, 1920]; }
function renderFormat() {
  const f = (st && st.format) || "vertical";
  $("#phone").classList.toggle("wide", f === "horizontal");
  document.body.classList.toggle("lay-mobile", f === "vertical");       // app layout follows the preview shape
  applyLayout();
  if (st) requestAnimationFrame(renderTimeline);                          // the timeline panel changed width
  const v = $("#video"), fit = f === "horizontal" && v.videoHeight > v.videoWidth;   // vertical footage in 16:9
  $("#phone").classList.toggle("fit", fit); $("#bgfill").hidden = !fit;
  for (const b of $("#fmtseg").children) b.classList.toggle("on", b.dataset.f === f);
  lastKey = ""; drawCaption();
}

// ------------------------------------------------------------ resizable panels (sizes saved per layout)
const layoutKey = () => "cinex.layout." + (document.body.classList.contains("lay-mobile") ? "mobile" : "desktop");
function applyLayout() {
  const ws = $(".workspace"); for (const v of ["--c-insp", "--c-chat", "--c-mon", "--r-tl"]) ws.style.removeProperty(v);
  let saved = {}; try { saved = JSON.parse(store.get(layoutKey()) || "{}"); } catch {}
  for (const [k, v] of Object.entries(saved)) ws.style.setProperty(k, v + "px");
}
function bindResizers() {
  for (const h of document.querySelectorAll(".rz")) {
    const vert = h.classList.contains("y"), panel = h.parentElement;
    h.onpointerdown = (e) => {
      e.preventDefault(); h.setPointerCapture(e.pointerId); h.classList.add("drag"); document.body.classList.add("resizing");
      const r = panel.getBoundingClientRect(), start = vert ? r.height : r.width, p0 = vert ? e.clientY : e.clientX;
      const sign = +h.dataset.sign, min = +h.dataset.min, max = +h.dataset.max;
      h.onpointermove = (ev) => {
        const v = Math.round(Math.min(max, Math.max(min, start + sign * ((vert ? ev.clientY : ev.clientX) - p0))));
        $(".workspace").style.setProperty(h.dataset.var, v + "px"); lastKey = ""; drawCaption();
      };
      h.onpointerup = () => {
        h.onpointermove = h.onpointerup = null; h.classList.remove("drag"); document.body.classList.remove("resizing");
        let saved = {}; try { saved = JSON.parse(store.get(layoutKey()) || "{}"); } catch {}
        saved[h.dataset.var] = parseInt($(".workspace").style.getPropertyValue(h.dataset.var)); store.set(layoutKey(), JSON.stringify(saved));
        if (st) renderTimeline();
      };
    };
    h.ondblclick = () => {
      let saved = {}; try { saved = JSON.parse(store.get(layoutKey()) || "{}"); } catch {}
      delete saved[h.dataset.var]; store.set(layoutKey(), JSON.stringify(saved)); applyLayout(); lastKey = ""; drawCaption();
    };
  }
}

// ------------------------------------------------------------ camera + colour preview (approximate; export is exact)
const LOOKS = {   // label, CSS approximation of reels_lib.GRADES, vignette, swatch
  natural: ["Natural", "contrast(1.04) saturate(1.02)", .05, "#8a8f86"],
  none: ["Sem look", "", 0, "#777"],
  clean_warm: ["Quente suave", "contrast(.92) saturate(.86) sepia(.12) brightness(1.04)", .10, "#c8b08a"],
  teal_orange: ["Teal e laranja", "contrast(1.12) saturate(1.08) sepia(.06)", .18, "linear-gradient(135deg,#2c6e74,#e0874a)"],
  moody: ["Moody", "contrast(1.18) saturate(.8) brightness(.88)", .35, "#3a3640"],
  vivid_day: ["Dia vivo", "contrast(1.1) saturate(1.18)", .12, "linear-gradient(135deg,#3d9be0,#f2c14e)"],
};
function renderLookUI() {
  const c = st.color, k = st.camera;
  $("#k-follow").checked = k.follow; $("#k-punch").checked = k.punch; $("#k-correct").checked = c.correct;
  $("#k-zoom").value = Math.round(k.zoom * 100); $("#o-zoom").textContent = Math.round(k.zoom * 100) + "%";
  for (const b of $("#looks").children) b.classList.toggle("on", b.dataset.look === c.look);
  const L = LOOKS[c.look] || LOOKS.none;
  $("#video").style.filter = L[1]; $("#vig").style.opacity = Math.min(1, L[2] * 2.2);
}
function bindLookUI() {
  $("#looks").replaceChildren(...Object.entries(LOOKS).map(([id, L]) => {
    const b = document.createElement("button"); b.dataset.look = id;
    const sw = document.createElement("i"); sw.style.background = L[3]; b.append(sw, document.createTextNode(L[0]));
    b.onclick = () => { if (!st) return; st.color.look = id; renderLookUI(); save({ color: st.color }); };
    return b;
  }));
  const cam = (k, v) => { if (!st) return; st.camera[k] = v; renderLookUI(); clearTimeout(camTimer); camTimer = setTimeout(() => save({ camera: st.camera }), 400); };
  let camTimer = null;
  $("#k-follow").onchange = (e) => cam("follow", e.target.checked);
  $("#k-punch").onchange = (e) => cam("punch", e.target.checked);
  $("#k-zoom").oninput = (e) => cam("zoom", +e.target.value / 100);
  $("#k-correct").onchange = (e) => { if (!st) return; st.color.correct = e.target.checked; save({ color: st.color }); };
}

function faceAt(t, a, b) {          // mean centre of the biggest face between a and b (normalised 0..1)
  if (!faces) return null;
  let sx = 0, sy = 0, n = 0;
  for (let i = Math.max(0, Math.floor(a * 10)); i <= Math.min(faces.length - 1, Math.ceil(b * 10)); i++) {
    const g = faces[i]; if (!g) continue;
    sx += g[0]; sy += g[1]; n++;
  }
  return n ? { x: sx / n, y: sy / n } : null;
}

function camera(t) {
  const v = $("#video"), k = st.camera, box = $("#phone");
  if (!v.videoWidth || $("#phone").classList.contains("fit")) { v.style.objectPosition = ""; v.style.transform = ""; return; }
  const bw = box.clientWidth, bh = box.clientHeight, sc = Math.max(bw / v.videoWidth, bh / v.videoHeight);
  const Sw = v.videoWidth * sc, Sh = v.videoHeight * sc;
  const seg = st.segments.find((x) => t >= x.s && t < x.e);
  // like the engine: a short or steady shot gets a fixed framing (tripod); a long one follows a smoothed face
  const f = k.follow ? (seg && seg.e - seg.s < 4 ? faceAt(t, seg.s, seg.e) : faceAt(t, t - 0.6, t + 0.6)) : null;
  const fx = (f ? f.x : 0.5) * Sw, fy = (f ? f.y : 0.5) * Sh;
  const ox = Math.min(0, Math.max(bw - Sw, bw / 2 - fx)), oy = Math.min(0, Math.max(bh - Sh, bh * (f ? 0.4 : 0.5) - fy));
  v.style.objectPosition = `${ox}px ${oy}px`;
  let z = k.zoom;
  if (k.punch && seg && seg.keep) { const i = kept.indexOf(seg); if (i > 0 && kept[i].s - kept[i - 1].e < 1.5 && i % 2) z *= 1.07; }
  v.style.transformOrigin = `${Math.min(bw, Math.max(0, ox + fx))}px ${Math.min(bh, Math.max(0, oy + fy))}px`;
  v.style.transform = z > 1.001 ? `scale(${z})` : "";
}

function rawToCut(t) {
  for (const g of kept) if (t >= g.s && t < g.e) return g.off + (t - g.s);
  return null;
}
function cutToRaw(ct) {
  for (const g of kept) if (ct >= g.off && ct < g.off + (g.e - g.s)) return g.s + (ct - g.off);
  return kept.length ? kept.at(-1).e : 0;
}
function cutTotal() { return kept.reduce((a, g) => a + g.e - g.s, 0); }

function ensureFont(id) {
  if (loadedFonts.has(id)) return; loadedFonts.add(id);
  const f = fonts.find((x) => x.id === id);
  const face = new FontFace("cx-" + id, `url(/api/font/${encodeURIComponent(id)}?p=${encodeURIComponent(name)})`,
    f && f.weights.length ? { weight: "100 900" } : {});
  face.load().then((ff) => { document.fonts.add(ff); drawCaption(); }).catch(() => {});
}

let lastKey = "";
function drawCaption() {
  const cap = $("#cap"), c = st && st.captions;
  if (!c || !c.enabled || !words.length || fxHidesCaptions($("#video").currentTime)) { cap.replaceChildren(); lastKey = ""; return; }
  const ct = rawToCut($("#video").currentTime);
  const g = ct == null ? null : groups.find((x) => x.s <= ct && ct < x.e);
  const key = g ? `${g.s}|${JSON.stringify(c)}|${g.w.map((w) => w.s <= ct && ct < w.e + 0.05).join()}` : "";
  if (key === lastKey) return; lastKey = key;
  if (!g) { cap.replaceChildren(); return; }
  ensureFont(c.font);
  const [FW] = frameSize(), box = $("#phone").clientWidth, px = (v) => (v * box) / FW;
  cap.style.top = (c.y / 1920) * 100 + "%";
  cap.style.fontFamily = `"cx-${c.font}", system-ui`;
  cap.style.fontWeight = W8[c.weight] || 400;
  cap.style.fontSize = px(c.size) + "px";
  const spans = g.w.map((w) => {
    const s = document.createElement("span"); s.className = "w"; s.textContent = w.d;
    s.style.color = w.key ? c.accent : c.color;
    if (c.stroke) { s.style.webkitTextStroke = `${px(c.stroke * 2)}px #000`; }
    s.style.textShadow = `0 ${px(6)}px ${px(18)}px rgba(0,0,0,.55)`;
    if (c.upper && w.s <= ct && ct < w.e + 0.05) s.style.transform = "scale(1.06)";
    return s;
  });
  const avail = box * ((FW - 160) / FW);
  const line = (ws) => { const d = document.createElement("div"); d.className = "line"; d.append(...ws); return d; };
  let rows = [line(spans)]; cap.replaceChildren(...rows);
  if (c.lines === 2 && spans.length > 1 && rows[0].offsetWidth > avail) {
    const wd = spans.map((s) => s.offsetWidth), tot = wd.reduce((a, b) => a + b, 0); let acc = 0, best = 1, bd = 1e9;
    for (let i = 1; i < spans.length; i++) { acc += wd[i - 1]; if (Math.abs(acc - tot / 2) < bd) { bd = Math.abs(acc - tot / 2); best = i; } }
    rows = [line(spans.slice(0, best)), line(spans.slice(best))]; cap.replaceChildren(...rows.flatMap((r, i) => i ? [document.createElement("br"), r] : [r]));
  }
  for (const r of rows) { const k = Math.min(1, avail / r.offsetWidth); r.style.transform = `scale(${k})`; }
}

// ------------------------------------------------------------ caption panel
function renderCaptionsUI() {
  const c = st.captions;
  $("#c-enabled").checked = c.enabled; $("#c-upper").checked = c.upper;
  $("#c-color").value = c.color; $("#c-accent").value = c.accent;
  for (const k of ["size", "stroke", "y"]) { $("#c-" + k).value = c[k]; $("#o-" + k).textContent = c[k]; }
  for (const seg of document.querySelectorAll(".seg")) for (const b of seg.children) b.classList.toggle("on", +b.dataset.v === c[seg.dataset.key]);
  const fsel = $("#c-font");
  const opts = [...fonts.map((f) => new Option(f.label, f.id)), ...projectFonts.map((f) => new Option(f + " (projeto)", f))];
  fsel.replaceChildren(...opts); fsel.value = c.font;
  const f = fonts.find((x) => x.id === c.font);
  $("#weightrow").hidden = !(f && f.weights.length);
  if (f && f.weights.length) { $("#c-weight").replaceChildren(...f.weights.map((w) => new Option(w, w))); $("#c-weight").value = c.weight; }
  if (document.activeElement !== $("#c-keywords")) $("#c-keywords").value = (st.keywords || []).join(", ");
}

function bindCaptionUI() {
  $("#presets").replaceChildren(...Object.entries(PRESETS).map(([n, p]) => {
    const b = document.createElement("button"); b.textContent = p.upper ? n.toUpperCase() : n; b.title = "Estilo " + n;
    b.style.fontWeight = W8[p.weight]; b.style.color = p.accent;
    b.onclick = () => { if (!st) return; Object.assign(st.captions, p); saveCaptions(); };
    return b;
  }));
  const set = (k, v) => { if (!st) return; st.captions[k] = v; saveCaptions(); };
  $("#c-enabled").onchange = (e) => set("enabled", e.target.checked);
  $("#c-upper").onchange = (e) => set("upper", e.target.checked);
  $("#c-color").oninput = (e) => set("color", e.target.value.toUpperCase());
  $("#c-accent").oninput = (e) => set("accent", e.target.value.toUpperCase());
  for (const k of ["size", "stroke", "y"]) $("#c-" + k).oninput = (e) => set(k, +e.target.value);
  $("#c-font").onchange = (e) => set("font", e.target.value);
  $("#c-weight").onchange = (e) => set("weight", e.target.value);
  for (const seg of document.querySelectorAll(".seg")) for (const b of seg.children) b.onclick = () => set(seg.dataset.key, +b.dataset.v);
  $("#c-keywords").onchange = (e) => { if (!st) return; st.keywords = e.target.value.split(",").map((s) => s.trim()).filter(Boolean); saveCaptions(); };
  $("#c-upload").onchange = async (e) => {
    const f = e.target.files[0]; if (!f || !name) return;
    try {
      await api(`/api/p/${name}/font`, { method: "POST", body: f, headers: { "X-Filename": f.name }, timeout: 120000 });
      await reloadState();
    } catch (err) { alert(err.message); }
    e.target.value = "";
  };
}

// ------------------------------------------------------------ timeline
function renderTimeline() {
  const dur = st.duration, w = Math.ceil(dur * pps);
  $("#tlinner").style.width = w + HEAD + 24 + "px";
  $("#tlinner").classList.toggle("locked", st.cut_locked);
  const step = [1, 2, 5, 10, 15, 30, 60].find((s) => s * pps >= 90) || 120;
  const ticks = [];
  for (let t = 0; t <= dur; t += step) { const s = document.createElement("span"); s.style.left = t * pps + "px"; s.textContent = tcode(t); ticks.push(s); }
  $("#ruler").replaceChildren(...ticks);
  $("#caplane").replaceChildren(...(st.captions.enabled ? groups : []).map((g) => {
    const b = document.createElement("div"); b.className = "blk capb";
    const s = cutToRaw(g.s), clip = kept.find((k) => s >= k.s && s < k.e);
    const e = Math.min(cutToRaw(Math.max(g.s, g.e - 0.01)), clip ? clip.e : Infinity);
    b.style.left = s * pps + "px"; b.style.width = Math.max(2, (e - s) * pps - 1) + "px";
    b.textContent = b.title = g.w.map((w) => w.d).join(" ");
    return b;
  }));
  const reo = isReordered(), pn = reo ? phraseNumber() : null;
  $("#blocks").replaceChildren(...st.segments.map((g) => {
    const b = document.createElement("div");
    b.className = `blk ${g.keep ? "keep" : "cut"}${sel === g.id ? " sel" : ""}`;
    b.style.left = g.s * pps + "px"; b.style.width = Math.max(2, (g.e - g.s) * pps - 2) + "px";
    b.textContent = (g.keep && reo && pn.get(g.id) ? pn.get(g.id) + " · " : "") + (g.keep ? g.text || "…" : g.reason || "cortado"); b.title = `#${g.id} ${g.s.toFixed(2)}–${g.e.toFixed(2)} s\n${g.text || ""}`;
    b.onclick = () => select(g.id, true);
    b.ondblclick = () => toggle(g.id);
    return b;
  }));
  drawWave(); renderInfo(); renderFx(); renderOrder();
}

function drawWave() {
  const cv = $("#wave"), dur = st.duration, w = Math.min(32000, Math.ceil(dur * pps));
  cv.width = w; cv.style.width = Math.ceil(dur * pps) + "px";
  const g = cv.getContext("2d"); g.clearRect(0, 0, w, cv.height);
  if (!wave) return;
  const pk = wave.peaks, mid = cv.height / 2, segs = st.segments;
  let si = 0;
  for (let x = 0; x < w; x++) {
    const t0 = (x / w) * dur, t1 = ((x + 1) / w) * dur;
    let v = 0; for (let i = Math.floor(t0 / wave.step); i <= Math.min(pk.length - 1, Math.floor(t1 / wave.step)); i++) v = Math.max(v, pk[i]);
    while (si < segs.length - 1 && segs[si].e <= t0) si++;
    g.fillStyle = segs[si] && segs[si].keep ? "#4fa785" : "#3f3f3f";
    const h = Math.max(1, v * (cv.height - 6)); g.fillRect(x, mid - h / 2, 1, h);
  }
}

function select(id, seek) {
  sel = id; const g = st.segments.find((x) => x.id === id);
  if (seek && g) $("#video").currentTime = g.s + 0.01;
  tab("corte"); renderTimeline();
}

function toggle(id) {
  if (st.cut_locked) return;
  const g = st.segments.find((x) => x.id === id); if (!g) return;
  g.keep = !g.keep; if (!g.keep && !g.reason) g.reason = "cortado no app";
  afterCutChange();
}
function afterCutChange() { buildGroups(); renderTimeline(); renderDur(); st.order = playOrder().map((g) => g.id); save({ segments: st.segments, order: st.order }); }

function renderInfo() {
  const box = $("#selinfo"), g = st.segments.find((x) => x.id === sel);
  $("#lockbtn").textContent = st.cut_locked ? "Corte aprovado ✓ — reabrir" : "Aprovar e travar corte";
  if (!g) { box.className = "selinfo muted"; box.textContent = "Clique num clipe da linha do tempo."; return; }
  box.className = "selinfo";
  const head = document.createElement("div"); head.className = "muted small";
  head.textContent = `Clipe ${g.id} · ${tcode(g.s)} → ${tcode(g.e)} · ${(g.e - g.s).toFixed(1)} s · ${g.keep ? "mantido" : "cortado"}`;
  const text = document.createElement("p"); text.textContent = g.text || "(sem fala)";
  const row = document.createElement("div"); row.className = "row2";
  const reason = document.createElement("input"); reason.placeholder = "Motivo do corte"; reason.value = g.reason || ""; reason.disabled = st.cut_locked;
  reason.onchange = () => { g.reason = reason.value; save({ segments: st.segments }); };
  const btn = document.createElement("button"); btn.className = g.keep ? "secondary" : "primary"; btn.disabled = st.cut_locked;
  btn.textContent = g.keep ? "Cortar" : "Manter"; btn.onclick = () => toggle(g.id);
  row.append(reason, btn); box.replaceChildren(head, text, row);
}

function renderDur() {
  const k = st.segments.filter((g) => g.keep).reduce((a, g) => a + g.e - g.s, 0);
  $("#durinfo").textContent = `${fmt(st.duration)} → ${fmt(k)} · ${st.segments.filter((g) => !g.keep).length} cortes`;
}

// ------------------------------------------------------------ chat
function renderChat() {
  const box = $("#msgs"), atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 30;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const msgs = (st.chat || []).map((m) => {
    const user = m.who === "user", d = el("div", "msg" + (user ? " user" : ""));
    const who = el("div", "who", user ? "Você" : "Cinex"); who.append(el("small", "", (m.t || "").slice(11, 16)));
    d.append(el("div", "av", user ? "V" : "C"), who, el("div", "txt", m.text)); return d;
  });
  box.replaceChildren(...(msgs.length ? msgs : [el("div", "empty", "Nenhuma mensagem ainda. Peça um ajuste: “corta a parte em que eu gaguejo”, “legenda maior”…")]));
  if (atEnd) box.scrollTop = box.scrollHeight;
}

// ------------------------------------------------------------ player
function tick() {
  try { update(); } finally { requestAnimationFrame(tick); }
}
function update() {
  const v = $("#video");
  if (st && !v.paused && $("#skipcut").checked) {
    followOrder(v);                                              // skip cuts, follow the phrase order
  }
  if (st) {
    const t = v.currentTime;
    $("#playhead").style.left = HEAD + t * pps + "px";
    const tl = $("#timeline"), x = t * pps;                      // page the view with the playhead (Premiere)
    if (!v.paused && (x < tl.scrollLeft || x > tl.scrollLeft + tl.clientWidth - HEAD - 40)) tl.scrollLeft = Math.max(0, x - 40);
    const ct = rawToCut(t), cut = $("#skipcut").checked;
    $("#tc").textContent = tcode(cut ? ct ?? 0 : t);
    $("#tctotal").textContent = tcode(cut ? cutTotal() : st.duration);
    $("#tlcode").textContent = tcode(t);
    drawCaption(); camera(t); fxFrame(t, !v.paused);
    if (!$("#bgfill").hidden && v.readyState >= 2) {                  // blurred fill behind vertical footage
      const c = $("#bgfill"), g = c.getContext("2d"), k = Math.max(c.width / v.videoWidth, c.height / v.videoHeight);
      g.drawImage(v, (c.width - v.videoWidth * k) / 2, (c.height - v.videoHeight * k) / 2, v.videoWidth * k, v.videoHeight * k);
    }
  }
}

function seekFromEvent(e, el) {
  const r = el.getBoundingClientRect(); const t = Math.max(0, (e.clientX - r.left) / pps);
  $("#video").currentTime = Math.min(st.duration, t);
}

// ------------------------------------------------------------ wiring
function tab(n) {
  for (const b of document.querySelectorAll(".ptabs button[data-tab]")) b.classList.toggle("on", b.dataset.tab === n);
  for (const t of ["legendas", "camera", "cor", "motion", "sons", "corte"]) $("#tab-" + t).hidden = n !== t;
}

function renderAll() {
  if (!st) { $("#phempty").hidden = false; return; }
  st.camera = { follow: true, zoom: 1.0, punch: true, ...(st.camera || {}) };
  st.color = { correct: true, look: "natural", ...(st.color || {}) };
  fxDefaults(); ensureFont("sans"); ensureFont("serif");
  $("#progname").textContent = st.name; renderFormat(); renderLookUI();
  buildGroups(); renderCaptionsUI(); renderChat(); renderDur(); renderTimeline(); lastKey = ""; drawCaption();
  $("#exportbtn").disabled = !st.segments.length;
}

async function init() {
  bindCaptionUI(); bindLookUI(); bindFx(); bindResizers(); applyLayout();
  for (const b of document.querySelectorAll(".ptabs button[data-tab]")) b.onclick = () => tab(b.dataset.tab);
  for (const b of $("#fmtseg").children) b.onclick = () => { if (!st) return; st.format = b.dataset.f; renderFormat(); save({ format: st.format }); };
  const step = (d) => { const v = $("#video"); v.pause(); v.currentTime = Math.max(0, Math.min(st.duration, v.currentTime + d)); };
  const jump = (dir) => {
    const t = $("#video").currentTime, list = $("#skipcut").checked ? kept : st.segments;
    const i = list.findIndex((x) => t >= x.s - 0.02 && t < x.e);           // neighbours in PLAY order
    const g = i < 0 ? (dir > 0 ? list.find((x) => x.s > t) : null) : list[i + (dir > 0 ? 1 : (t - list[i].s > 0.3 ? 0 : -1))];
    $("#video").currentTime = g ? g.s : dir > 0 ? t : 0; playIdx = g ? list.indexOf(g) : -1;
  };
  $("#backbtn").onclick = () => st && step(-1 / FPS); $("#fwdbtn").onclick = () => st && step(1 / FPS);
  $("#prevbtn").onclick = () => st && jump(-1); $("#nextbtn").onclick = () => st && jump(1);
  $("#project").onchange = (e) => e.target.value && openProject(e.target.value);
  $("#newform").onsubmit = async (e) => {
    e.preventDefault(); const src = $("#srcpath").value.trim(); if (!src) return;
    try { const r = await api("/api/projects", { method: "POST", body: JSON.stringify({ src }) }); $("#srcpath").value = "";
      banner("Preparando o projeto…"); name = r.name; st = null; location.hash = r.name; setTimeout(() => listProjects(r.name), 1500); }
    catch (err) { banner(err.message, true); }
  };
  $("#exportbtn").onclick = async () => {
    try { await api(`/api/p/${name}/export`, { method: "POST", body: "{}" }); poll(); } catch (e) { alert(e.message); }
  };
  $("#orderreset").onclick = () => { if (!st || st.cut_locked) return; st.order = []; buildGroups(); renderTimeline(); renderDur(); save({ order: [] }); };
  $("#lockbtn").onclick = () => { st.cut_locked = !st.cut_locked; renderTimeline(); save({ cut_locked: st.cut_locked }); };
  $("#chatform").onsubmit = async (e) => {
    e.preventDefault(); const t = $("#chatin").value.trim(); if (!t || !name) return;
    $("#chatin").value = "";
    try { await api(`/api/p/${name}/chat`, { method: "POST", body: JSON.stringify({ text: t }) }); await reloadState(); }
    catch (err) { alert(err.message); }
  };
  $("#tlzoom").oninput = (e) => { pps = +e.target.value; if (st) renderTimeline(); };
  $("#ruler").onclick = (e) => st && seekFromEvent(e, $("#ruler"));
  $("#wave").onclick = (e) => st && seekFromEvent(e, $("#wave"));
  $("#playbtn").onclick = () => { const v = $("#video"); v.paused ? v.play() : v.pause(); };
  $("#video").onplay = () => ($("#playbtn").textContent = "❚❚");
  $("#video").onpause = () => ($("#playbtn").textContent = "▶");
  $("#video").onseeked = $("#video").ontimeupdate = update;
  $("#video").onloadedmetadata = renderFormat;      // rAF stops while the tab is hidden
  $("#video").onclick = () => $("#playbtn").click();
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea")) return;
    if (e.code === "Space") { e.preventDefault(); $("#playbtn").click(); }
    if (e.key === "ArrowLeft") { e.preventDefault(); $("#backbtn").click(); }
    if (e.key === "ArrowRight") { e.preventDefault(); $("#fwdbtn").click(); }
    if ((e.key === "Delete" || e.key === "Backspace") && sel) toggle(sel);
  });
  window.addEventListener("resize", () => { lastKey = ""; drawCaption(); });
  fonts = await api("/api/fonts").catch(() => []);
  setInterval(poll, 1500);
  requestAnimationFrame(tick);
  await listProjects();
}
init();
