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

let name = null, st = null, words = [], wave = null, fonts = [], projectFonts = [];
let sel = null, pending = 0, pps = 60, loadedFonts = new Set(), groups = [], kept = [];

async function api(path, opt = {}) {
  const r = await fetch(path, { ...opt, headers: { ...H, ...(opt.headers || {}) } });
  const j = await r.json().catch(() => ({}));
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
  [words, wave] = await Promise.all([api(`/api/p/${name}/words`), api(`/api/p/${name}/waveform`).catch(() => null)]);
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
  kept = st.segments.filter((g) => g.keep).sort((a, b) => a.s - b.s);
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
  if (!c || !c.enabled || !words.length) { cap.replaceChildren(); lastKey = ""; return; }
  const ct = rawToCut($("#video").currentTime);
  const g = ct == null ? null : groups.find((x) => x.s <= ct && ct < x.e);
  const key = g ? `${g.s}|${JSON.stringify(c)}|${g.w.map((w) => w.s <= ct && ct < w.e + 0.05).join()}` : "";
  if (key === lastKey) return; lastKey = key;
  if (!g) { cap.replaceChildren(); return; }
  ensureFont(c.font);
  const box = $("#phone").clientWidth, px = (v) => (v * box) / 1080;
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
  const avail = box * (920 / 1080);
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
      await api(`/api/p/${name}/font`, { method: "POST", body: f, headers: { "X-Filename": f.name } });
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
  $("#blocks").replaceChildren(...st.segments.map((g) => {
    const b = document.createElement("div");
    b.className = `blk ${g.keep ? "keep" : "cut"}${sel === g.id ? " sel" : ""}`;
    b.style.left = g.s * pps + "px"; b.style.width = Math.max(2, (g.e - g.s) * pps - 2) + "px";
    b.textContent = g.keep ? g.text || "…" : g.reason || "cortado"; b.title = `#${g.id} ${g.s.toFixed(2)}–${g.e.toFixed(2)} s\n${g.text || ""}`;
    b.onclick = () => select(g.id, true);
    b.ondblclick = () => toggle(g.id);
    return b;
  }));
  drawWave(); renderInfo();
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
function afterCutChange() { buildGroups(); renderTimeline(); renderDur(); save({ segments: st.segments }); }

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
    const t = v.currentTime, g = st.segments.find((x) => t >= x.s && t < x.e);
    if (g && !g.keep) {
      const next = kept.find((x) => x.s >= g.e - 0.001);
      if (next) v.currentTime = next.s; else { v.pause(); }
    }
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
    drawCaption();
  }
}

function seekFromEvent(e, el) {
  const r = el.getBoundingClientRect(); const t = Math.max(0, (e.clientX - r.left) / pps);
  $("#video").currentTime = Math.min(st.duration, t);
}

// ------------------------------------------------------------ wiring
function tab(n) {
  for (const b of document.querySelectorAll(".ptabs button[data-tab]")) b.classList.toggle("on", b.dataset.tab === n);
  $("#tab-legendas").hidden = n !== "legendas"; $("#tab-corte").hidden = n !== "corte";
}

function renderAll() {
  if (!st) { $("#phempty").hidden = false; return; }
  $("#progname").textContent = st.name;
  buildGroups(); renderCaptionsUI(); renderChat(); renderDur(); renderTimeline(); lastKey = ""; drawCaption();
  $("#exportbtn").disabled = !st.segments.length;
}

async function init() {
  bindCaptionUI();
  for (const b of document.querySelectorAll(".ptabs button[data-tab]")) b.onclick = () => tab(b.dataset.tab);
  const step = (d) => { const v = $("#video"); v.pause(); v.currentTime = Math.max(0, Math.min(st.duration, v.currentTime + d)); };
  const jump = (dir) => {
    const t = $("#video").currentTime, list = $("#skipcut").checked ? kept : st.segments;
    const g = dir > 0 ? list.find((x) => x.s > t + 0.01) : [...list].reverse().find((x) => x.s < t - 0.3);
    $("#video").currentTime = g ? g.s : dir > 0 ? t : 0;
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
  $("#video").onseeked = $("#video").ontimeupdate = update;      // rAF stops while the tab is hidden
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
  await listProjects();
  setInterval(poll, 1500);
  requestAnimationFrame(tick);
}
init();
