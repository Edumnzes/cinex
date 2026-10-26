"use strict";
// Cinex app — B-roll (track V2): other clips over the speech. The picture changes, the voice keeps playing.
// Clips live in st.media (added by path or upload; the server builds a proxy + filmstrip with app_project.py media),
// windows in st.broll = [{id, media, t0, t1, ss, mode: "full"|"card", zoom}] in RAW seconds, like motions.
// The export maps them to the cut timeline (app_project.broll_windows) and draws them with reels_lib.
// Loaded before app.js; uses its globals ($, st, name, api, save, tcode, rawToCut, drag, el…) at call time.

let selB = null, bKey = "";

const bSave = () => save({ broll: st.broll });
const mediaOf = (id) => (st.media || []).find((m) => m.id === id);
const brollVisible = (b) => kept.some((g) => g.s < b.t1 && g.e > b.t0);     // over at least one kept stretch

function bindBroll() {
  $("#mediaform").onsubmit = async (e) => {
    e.preventDefault(); const src = $("#mediapath").value.trim(); if (!src || !name) return;
    try { await api(`/api/p/${name}/media`, { method: "POST", body: JSON.stringify({ src }) }); $("#mediapath").value = ""; mediaStatus("Preparando o clipe…"); }
    catch (err) { mediaStatus(err.message, true); }
  };
  $("#mediaup").onchange = async (e) => {
    const f = e.target.files[0]; e.target.value = ""; if (!f || !name) return;
    mediaStatus(`Enviando ${f.name} (${(f.size / 1e6).toFixed(0)} MB)…`);
    try {
      await api(`/api/p/${name}/mediaup`, { method: "POST", body: f, timeout: 30 * 60 * 1000,
                                             headers: { "X-Filename": encodeURIComponent(f.name), "Content-Type": "application/octet-stream" } });
      mediaStatus("Preparando o clipe…");
    } catch (err) { mediaStatus(err.message, true); }
  };
}
function mediaStatus(t, err) { const p = $("#mediastatus"); p.textContent = t || ""; p.classList.toggle("warn", !!err); }

// ------------------------------------------------------------ inspector: B-roll tab
function renderMedia() {
  const list = st.media || [];
  if (list.some((m) => m.ready) && !list.some((m) => !m.ready && !m.error)) mediaStatus("");
  $("#medialist").replaceChildren(...(list.length ? list.map((m) => {
    const r = el("div", "mediarow"), th = el("div", "mthumb");
    if (m.ready) th.style.backgroundImage = `url(/api/p/${name}/media/${m.id}.jpg)`;
    const info = el("div", "minfo"); info.append(el("b", "", m.name),
      el("small", "muted", m.error ? "erro: " + m.error.slice(0, 80) : m.ready ? `${m.dur.toFixed(1)} s${m.hdr ? " · HDR convertido" : ""}` : "preparando…"));
    const add = el("button", "secondary", "+ Na agulha"); add.disabled = !m.ready; add.title = "Cobrir a fala a partir do ponto da agulha";
    add.onclick = () => {
      const t0 = $("#video").currentTime, b = { id: nextId(st.broll), media: m.id, t0: +t0.toFixed(2),
        t1: +Math.min(st.duration, t0 + Math.min(3, m.dur)).toFixed(2), ss: 0, mode: "full", zoom: true };
      st.broll.push(b); selB = b.id; renderBroll(); bSave();
    };
    const del = el("button", "icon", "×"); del.title = "Remover clipe (e o B-roll que usa ele)";
    del.onclick = async () => {
      if (!confirm(`Remover ${m.name} do projeto? O arquivo original não é apagado.`)) return;
      try { await api(`/api/p/${name}/media/${m.id}/remover`, { method: "POST", body: "{}" }); await reloadState(); } catch (err) { mediaStatus(err.message, true); }
    };
    r.append(th, info, add, del); return r;
  }) : [el("p", "muted small", "Nenhum clipe ainda. Cole o caminho de um vídeo ou envie do computador.")]));
}

function renderBrollEditor() {
  const box = $("#bsel"), b = st.broll.find((x) => x.id === selB), m = b && mediaOf(b.media);
  if (!b || !m) { box.className = "selinfo muted"; box.textContent = "Adicione um clipe acima ou clique num bloco da trilha V2."; return; }
  box.className = "selinfo"; const rows = [];
  const field = (label, input) => { const r = el("div", "prop"); r.append(el("label", "", label), input); rows.push(r); };
  const len = () => b.t1 - b.t0;
  rows.push(el("div", "muted small", `${m.name} · ${tcode(b.t0)} → ${tcode(b.t1)} · ${len().toFixed(1)} s`));
  if (!brollVisible(b)) rows.push(el("p", "small warn", "Este B-roll está todo dentro de um trecho cortado: não aparece no vídeo. Arraste para cima de uma fala mantida."));
  // entry point: click the filmstrip (the window must fit in the clip: ss + length <= clip length)
  if (m.ready) {
    const strip = el("div", "bstrip"); strip.style.backgroundImage = `url(/api/p/${name}/media/${m.id}.jpg)`;
    const win = el("i", "bwin"); win.style.left = (b.ss / m.dur) * 100 + "%"; win.style.width = Math.min(100, (len() / m.dur) * 100) + "%";
    strip.append(win); strip.title = "Clique para escolher de onde o clipe começa";
    strip.onclick = (e) => {
      const r = strip.getBoundingClientRect(), x = (e.clientX - r.left) / r.width;
      b.ss = +Math.max(0, Math.min(m.dur - len(), x * m.dur - len() / 2)).toFixed(2); renderBroll(); bSave(); $("#video").currentTime = b.t0 + .01;
    };
    rows.push(strip);
  }
  const num = (key, lo, hi) => {
    const i = el("input"); i.type = "number"; i.step = "0.1"; i.min = String(lo); i.value = (+b[key]).toFixed(2);
    i.onchange = () => { b[key] = +Math.max(lo, Math.min(hi(), +i.value)).toFixed(2);
      if (b.t1 <= b.t0 + .3) b.t1 = +Math.min(st.duration, b.t0 + .5).toFixed(2); brollFit(b); renderBroll(); bSave(); };
    return i;
  };
  field("Entrada no clipe (s)", num("ss", 0, () => Math.max(0, m.dur - len())));
  const seg = el("div", "seg");
  for (const [v, l] of [["full", "Tela cheia"], ["card", "Cartão"]]) {
    const x = el("button", b.mode === v ? "on" : "", l); x.onclick = () => { b.mode = v; renderBroll(); bSave(); }; seg.append(x);
  }
  field("Modo", seg);
  { const cb = el("input"); cb.type = "checkbox"; cb.checked = b.zoom !== false; cb.onchange = () => { b.zoom = cb.checked; bSave(); };
    const lab = el("label", "check small"); lab.append(cb, document.createTextNode(" aproxima devagar (1,00 → 1,08)")); field("Zoom", lab); }
  field("Início (s)", num("t0", 0, () => st.duration)); field("Fim (s)", num("t1", 0, () => st.duration));
  const del = el("button", "secondary wide", "Remover B-roll");
  del.onclick = () => { st.broll = st.broll.filter((x) => x !== b); selB = null; renderBroll(); bSave(); };
  rows.push(del, el("p", "muted small note", "O áudio continua sendo a fala. Use para mostrar o que a pessoa descreve ou esconder um problema da imagem (cabo, pessoa no fundo, cena sem EPI)."));
  box.replaceChildren(...rows);
}

function brollFit(b) {            // keep the window inside its clip
  const m = mediaOf(b.media); if (!m || !m.dur) return;
  if (b.t1 - b.t0 > m.dur) b.t1 = +(b.t0 + m.dur).toFixed(2);
  b.ss = +Math.max(0, Math.min(b.ss, m.dur - (b.t1 - b.t0))).toFixed(2);
}

// ------------------------------------------------------------ timeline track V2
function renderBroll() {
  if (!st) return; st.media = st.media || []; st.broll = st.broll || [];
  $("#blane").replaceChildren(...st.broll.map((b) => {
    const m = mediaOf(b.media), x = el("div", "blk bblk" + (b.id === selB ? " sel" : "") + (brollVisible(b) ? "" : " off"), (b.mode === "card" ? "▣ " : "") + (m ? m.name : "?"));
    x.style.left = b.t0 * pps + "px"; x.style.width = Math.max(6, (b.t1 - b.t0) * pps - 1) + "px"; x.title = x.textContent;
    if (m && m.ready) x.style.backgroundImage = `linear-gradient(rgba(20,20,30,.55), rgba(20,20,30,.55)), url(/api/p/${name}/media/${m.id}.jpg)`;
    x.append(el("i", "grip"));
    drag(x, (dt, edge) => {
      const mx = m ? m.dur : 1e9;
      if (edge) b.t1 = Math.max(b.t0 + .3, Math.min(st.duration, b.t0 + mx - b.ss, b.t1o + dt));
      else { const d = b.t1o - b.t0o; b.t0 = Math.max(0, Math.min(st.duration - d, b.t0o + dt)); b.t1 = b.t0 + d; }
    }, () => { b.t0o = b.t0; b.t1o = b.t1; },
    () => { delete b.t0o; delete b.t1o; b.t0 = +b.t0.toFixed(2); b.t1 = +b.t1.toFixed(2); bSave(); },
    () => { selB = b.id; tab("broll"); $("#video").currentTime = b.t0 + .01; },
    brollLight, renderBroll);
    return x;
  }));
  renderMedia(); renderBrollEditor(); bKey = "";
}
function brollLight() {
  const xs = $("#blane").children;
  st.broll.forEach((b, i) => { if (xs[i]) { xs[i].style.left = b.t0 * pps + "px"; xs[i].style.width = Math.max(6, (b.t1 - b.t0) * pps - 1) + "px"; } });
  bKey = "";
}

// ------------------------------------------------------------ preview: second <video> over the program
function brollFrame(t, playing) {
  const v = $("#bvid"); if (!st) return;
  const b = (st.broll || []).find((x) => t >= x.t0 && t < x.t1), m = b && mediaOf(b.media);
  if (!b || !m || !m.ready) { if (!v.hidden) { v.pause(); v.hidden = true; } return; }
  const url = `/api/p/${name}/media/${m.id}.mp4`;
  if (!v.src.endsWith(url)) v.src = url;
  v.hidden = false; v.className = "bvid" + (b.mode === "card" ? " card" : "");
  // local time follows the CUT timeline (what the export plays), so cuts inside the window don't jump the clip
  const c = rawToCut(t), c0 = rawToCut(b.t0), lt = b.ss + (c != null && c0 != null ? c - c0 : t - b.t0);
  if (playing) { if (v.paused) v.play().catch(() => {}); if (Math.abs(v.currentTime - lt) > .25) v.currentTime = lt; }
  else { if (!v.paused) v.pause(); if (Math.abs(v.currentTime - lt) > .04) v.currentTime = lt; }
  const z = b.zoom === false ? 1 : 1 + .08 * Math.min(1, (t - b.t0) / Math.max(.01, b.t1 - b.t0));
  v.style.transform = b.mode === "card" ? "translate(-50%, -50%)" : `scale(${z})`;
  v.style.opacity = Math.max(0, Math.min(1, (t - b.t0) / .2, (b.t1 - t) / .2));
  v.style.filter = $("#video").style.filter;                     // same look preview as the program
}
