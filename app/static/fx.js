"use strict";
// Cinex app — motion elements (track M1) and sound effects (track S1).
// Loaded before app.js; uses its globals ($, st, pps, kept, save, tcode, rawToCut…) only at call time.
// Templates mirror scripts/formats.py; the preview here is an HTML approximation, the export draws them exactly.

const MT = {   // type: [label, default seconds, default text, default text2, y on the 9:16 scale]
  titulo: ["Título", 2.5, "O PROBLEMA", "", 330],
  topico: ["Tópico numerado", 3.5, "Uma ideia em até 8 palavras", "", 480],
  nome: ["Nome", 3, "Nome de quem fala", "Cargo ou empresa", 1110],
  citacao: ["Citação", 3.5, "A frase mais forte do vídeo", "", 520],
  frase: ["Frase grande", 3, "Frase que prende a atenção", "", 820],
  seguir: ["Siga", 3, "Siga para mais", "", 420],
  salvar: ["Salve", 3, "Salve para não esquecer", "", 420],
  gigante: ["Palavra gigante", 2.5, "75%", "", 640],
};
const SFX_GAIN = -12;
let fxCats = {}, selM = null, selS = null, fxLastT = 0, fxKey = "";
const fxAudio = {};

function fxDefaults() { st.motions = st.motions || []; st.sfx = st.sfx || []; st.motion_engine = st.motion_engine || "html"; }
const nextId = (list) => list.reduce((m, x) => Math.max(m, x.id || 0), 0) + 1;
const fxSave = () => save({ motions: st.motions, sfx: st.sfx });
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

// ------------------------------------------------------------ inspector: Motion tab
function bindFx() {
  $("#mtemplates").replaceChildren(...Object.entries(MT).map(([k, d]) => {
    const b = el("button", "", d[0]); b.title = "Adicionar no ponto da agulha";
    b.onclick = () => {
      if (!st) return; const t0 = $("#video").currentTime;
      const m = { id: nextId(st.motions), type: k, t0: +t0.toFixed(2), t1: +Math.min(st.duration, t0 + d[1]).toFixed(2), text: d[2], text2: d[3], sfx: "" };
      st.motions.push(m); selM = m.id; selS = null; renderFx(); fxSave();
    };
    return b;
  }));
  api("/api/sfx").then((c) => { fxCats = c; renderSfxCats(); }).catch(() => {});
  for (const b of $("#mengine").children) b.onclick = () => { if (!st) return; st.motion_engine = b.dataset.e; renderFx(); save({ motion_engine: st.motion_engine }); };
}

function renderMotionEditor() {
  const box = $("#msel"), m = st.motions.find((x) => x.id === selM);
  if (!m) { box.className = "selinfo muted"; box.textContent = "Adicione um elemento acima ou clique num bloco da trilha M1."; return; }
  box.className = "selinfo";
  const d = MT[m.type], rows = [];
  const field = (label, input) => { const r = el("div", "prop"); r.append(el("label", "", label), input); rows.push(r); };
  const txt = (key, ph) => { const i = el("input"); i.value = m[key] || ""; i.placeholder = ph; i.oninput = () => { m[key] = i.value; fxKey = ""; }; i.onchange = fxSave; return i; };
  const num = (key) => {
    const i = el("input"); i.type = "number"; i.step = "0.1"; i.min = "0"; i.value = m[key].toFixed(2);
    i.onchange = () => { const v = Math.max(0, Math.min(st.duration, +i.value)); m[key] = v;
      if (m.t1 <= m.t0 + .3) m.t1 = Math.min(st.duration, m.t0 + .5); renderFx(); fxSave(); };
    return i;
  };
  rows.push(el("div", "muted small", `${d[0]} · ${tcode(m.t0)} → ${tcode(m.t1)}`));
  field("Texto", txt("text", d[2]));
  if (m.type === "nome") field("Cargo", txt("text2", "opcional"));
  if (m.type === "citacao") field("Autor", txt("text2", "opcional"));
  if (m.type === "frase") field("Destacar", txt("text2", "palavras na cor de destaque"));
  { const cb = el("input"); cb.type = "checkbox"; cb.checked = m.atras ?? m.type === "gigante";
    cb.onchange = () => { m.atras = cb.checked; renderFx(); fxSave(); };
    const lab = el("label", "check small"); lab.append(cb, document.createTextNode(" recorta a pessoa por cima (aparece na exportação, motor HTML)"));
    field("Atrás da pessoa", lab); }
  field("Início (s)", num("t0")); field("Fim (s)", num("t1"));
  const sel = el("select"); sel.append(new Option("Sem som", ""), ...Object.keys(fxCats).map((c) => new Option(c, c)));
  sel.value = m.sfx || ""; sel.onchange = () => { m.sfx = sel.value; if (m.sfx) fxPlay(m.sfx, SFX_GAIN); renderFx(); fxSave(); };
  field("Som ao entrar", sel);
  const del = el("button", "secondary wide", "Remover elemento");
  del.onclick = () => { st.motions = st.motions.filter((x) => x !== m); selM = null; renderFx(); fxSave(); };
  rows.push(del); box.replaceChildren(...rows);
}

// ------------------------------------------------------------ inspector: Sons tab
function renderSfxCats() {
  const names = Object.keys(fxCats);
  $("#sfxcats").replaceChildren(...(names.length ? names.map((c) => {
    const r = el("div", "sfxrow"), play = el("button", "icon", "▶"); play.title = "Ouvir"; play.onclick = () => fxPlay(c, SFX_GAIN);
    const add = el("button", "secondary", "+ Adicionar"); add.title = "Adicionar no ponto da agulha";
    add.onclick = () => {
      if (!st) return; const s = { id: nextId(st.sfx), t: +$("#video").currentTime.toFixed(2), cat: c, gain: SFX_GAIN };
      st.sfx.push(s); selS = s.id; selM = null; renderFx(); fxSave(); fxPlay(c, SFX_GAIN);
    };
    r.append(play, el("span", "", c), el("span", "muted small", fxCats[c] + " sons"), add); return r;
  }) : [el("p", "muted small", "Nenhum som no banco. Baixe sons licenciados (Pixabay, Mixkit) e peça ao Claude para organizar em ~/reels-banco/sfx.")]));
}

function renderSfxEditor() {
  const box = $("#ssel"), s = st.sfx.find((x) => x.id === selS);
  if (!s) { box.className = "selinfo muted"; box.textContent = "Clique num som da trilha S1 para ajustar."; return; }
  box.className = "selinfo";
  const cat = el("select"); cat.append(...Object.keys(fxCats).map((c) => new Option(c, c))); cat.value = s.cat;
  cat.onchange = () => { s.cat = cat.value; fxPlay(s.cat, s.gain); renderFx(); fxSave(); };
  const vol = el("input"); vol.type = "range"; vol.min = "-24"; vol.max = "-4"; vol.value = s.gain;
  const out = el("output", "", s.gain + " dB");
  vol.oninput = () => { s.gain = +vol.value; out.textContent = s.gain + " dB"; };
  vol.onchange = () => { fxPlay(s.cat, s.gain); fxSave(); };
  const r1 = el("div", "prop"), r2 = el("div", "prop");
  r1.append(el("label", "", "Som"), cat); r2.append(el("label", "", "Volume"), vol, out);
  const del = el("button", "secondary wide", "Remover som");
  del.onclick = () => { st.sfx = st.sfx.filter((x) => x !== s); selS = null; renderFx(); fxSave(); };
  box.replaceChildren(el("div", "muted small", `Som em ${tcode(s.t)}`), r1, r2, del);
}

// manual §5: sounds only on key events, about 2 per 10 s at most, measured on the cut timeline
function sfxEvents() {
  const ev = [];
  for (const s of st.sfx) { const c = rawToCut(s.t); if (c != null) ev.push(c); }
  for (const m of st.motions) if (m.sfx) { const c = rawToCut(m.t0); if (c != null) ev.push(c); }
  return ev.sort((a, b) => a - b);
}
function renderSfxWarn() {
  const ev = sfxEvents(); let worst = 0;
  for (let i = 0; i < ev.length; i++) worst = Math.max(worst, ev.filter((x) => x >= ev[i] && x < ev[i] + 10).length);
  const w = $("#sfxwarn");
  w.className = "small " + (worst > 2 ? "warn" : "muted");
  w.textContent = worst > 2 ? `${worst} sons em 10 s. O manual pede no máximo ~2 a cada 10 s, só nos eventos-chave (gancho, card principal, prova, CTA).`
    : `${ev.length} sons no vídeo · dentro do limite do manual (~2 a cada 10 s).`;
}

// ------------------------------------------------------------ timeline tracks M1 / S1 (drag to move, edge to resize)
function renderFx() {
  if (!st) return; fxDefaults();
  $("#mlane").replaceChildren(...st.motions.map((m) => {
    const b = el("div", "blk mblk" + (m.id === selM ? " sel" : ""), (m.sfx ? "♪ " : "") + ((m.atras ?? m.type === "gigante") ? "◐ " : "") + MT[m.type][0] + ": " + (m.text || ""));
    b.style.left = m.t0 * pps + "px"; b.style.width = Math.max(6, (m.t1 - m.t0) * pps - 1) + "px"; b.title = b.textContent;
    const h = el("i", "grip"); b.append(h);
    drag(b, (dt, edge) => { if (edge) m.t1 = Math.max(m.t0 + .3, Math.min(st.duration, m.t1o + dt));
                            else { const d = m.t1o - m.t0o; m.t0 = Math.max(0, Math.min(st.duration - d, m.t0o + dt)); m.t1 = m.t0 + d; } },
         () => { m.t0o = m.t0; m.t1o = m.t1; }, () => { delete m.t0o; delete m.t1o; m.t0 = +m.t0.toFixed(2); m.t1 = +m.t1.toFixed(2); fxSave(); },
         () => { selM = m.id; selS = null; tab("motion"); $("#video").currentTime = m.t0 + .01; });
    return b;
  }));
  $("#slane").replaceChildren(...st.sfx.map((s) => {
    const b = el("div", "blk sblk" + (s.id === selS ? " sel" : ""), s.cat);
    b.style.left = s.t * pps - 1 + "px"; b.title = `${s.cat} · ${s.gain} dB`;
    drag(b, (dt) => { s.t = Math.max(0, Math.min(st.duration, s.to + dt)); }, () => { s.to = s.t; },
         () => { delete s.to; s.t = +s.t.toFixed(2); fxSave(); },
         () => { selS = s.id; selM = null; tab("sons"); $("#video").currentTime = Math.max(0, s.t - .5); });
    return b;
  }));
  for (const b of $("#mengine").children) b.classList.toggle("on", b.dataset.e === st.motion_engine);
  renderMotionEditor(); renderSfxEditor(); renderSfxWarn(); fxKey = "";
}

function drag(b, move, start, end, click) {
  b.onpointerdown = (e) => {
    e.preventDefault(); const edge = e.target.classList.contains("grip"), x0 = e.clientX; let moved = false;
    b.setPointerCapture(e.pointerId); start();
    b.onpointermove = (ev) => {
      const dx = ev.clientX - x0; if (Math.abs(dx) > 3) moved = true;
      if (moved) { move(dx / pps, edge); b.style.left = ""; renderFxLight(); }
    };
    b.onpointerup = () => { b.onpointermove = b.onpointerup = null; if (moved) end(); else { end(); click(); } renderFx(); };
  };
}
function renderFxLight() {        // reposition blocks while dragging without rebuilding them
  const mb = $("#mlane").children, sb = $("#slane").children;
  st.motions.forEach((m, i) => { if (mb[i]) { mb[i].style.left = m.t0 * pps + "px"; mb[i].style.width = Math.max(6, (m.t1 - m.t0) * pps - 1) + "px"; } });
  st.sfx.forEach((s, i) => { if (sb[i]) sb[i].style.left = s.t * pps - 1 + "px"; });
  fxKey = "";
}

// ------------------------------------------------------------ preview: motion overlay + sounds
function fxHidesCaptions(t) { return (st.motions || []).some((m) => (m.type === "citacao" || m.type === "frase") && t >= m.t0 && t < m.t1); }

function fxFrame(t, playing) {
  if (!st) return;
  const box = $("#phone"), [FW, FH] = frameSize(), k = box.clientWidth / FW, acc = st.captions.accent;
  const act = (st.motions || []).filter((m) => t >= m.t0 && t < m.t1);
  const key = act.map((m) => m.id + m.text + m.text2 + m.type).join("|") + box.clientWidth + acc;
  if (key !== fxKey) {
    fxKey = key;
    $("#mg").replaceChildren(...act.map((m) => mgNode(m, k, acc, FH)));
  }
  for (const n of $("#mg").children) {      // fade/slide in and out like formats.life()
    const m = act.find((x) => x.id === +n.dataset.id); if (!m) continue;
    const a = Math.min(1, (t - m.t0) / .3, (m.t1 - t) / .25), e = 1 - Math.pow(1 - Math.min(1, (t - m.t0) / .35), 3);
    n.style.opacity = Math.max(0, a); n.style.translate = `0 ${(1 - e) * 30 * k}px`;
  }
  // sounds: fire when the playhead crosses a marker during normal playback (not on seeks)
  if (playing && t > fxLastT && t - fxLastT < .5) {
    for (const s of st.sfx || []) if (s.t > fxLastT && s.t <= t) fxPlay(s.cat, s.gain);
    for (const m of st.motions || []) if (m.sfx && m.t0 > fxLastT && m.t0 <= t) fxPlay(m.sfx, SFX_GAIN);
  }
  fxLastT = t;
}

function mgNode(m, k, acc, FH) {
  const px = (v) => v * k + "px", n = el("div", "mg mg-" + m.type); n.dataset.id = m.id;
  n.style.top = (MT[m.type][4] / 1920) * 100 + "%"; n.style.setProperty("--acc", acc);
  n.style.fontSize = px({ titulo: 32, topico: 50, nome: 50, citacao: 62, frase: 78, seguir: 40, salvar: 40, gigante: 200 }[m.type]);
  if (m.atras ?? m.type === "gigante") n.style.opacity = .55;      // preview can't cut the person: shown faded
  if (m.type === "topico") {
    const i = st.motions.filter((x) => x.type === "topico").sort((a, b) => a.t0 - b.t0).indexOf(m) + 1;
    n.append(el("b", "num", String(i)), el("span", "", m.text));
  } else if (m.type === "nome") {
    const t = el("div"); t.append(el("b", "", m.text)); if (m.text2) t.append(el("small", "", m.text2)); n.append(el("i", "bar"), t);
  } else if (m.type === "citacao") {
    n.append(el("q", "", m.text)); if (m.text2) n.append(el("small", "", "— " + m.text2));
  } else if (m.type === "frase") {
    const hl = new Set((m.text2 || "").toLowerCase().split(/[\s,]+/).filter(Boolean));
    for (const w of m.text.split(/\s+/)) { const s = el("span", hl.has(w.toLowerCase().replace(/[.,!?]/g, "")) ? "hl" : "", w + " "); n.append(s); }
  } else {
    n.textContent = (m.type === "seguir" ? "+ " : "") + (m.type === "titulo" ? m.text.toUpperCase() : m.text);
  }
  return n;
}

function fxPlay(cat, gain) {
  if (!name || !fxCats[cat]) return;
  const a = fxAudio[cat] || (fxAudio[cat] = new Audio(`/api/sfx/${encodeURIComponent(cat)}`));
  const c = a.cloneNode(); c.volume = Math.min(1, Math.pow(10, (gain + 6) / 20)); c.play().catch(() => {});
}
