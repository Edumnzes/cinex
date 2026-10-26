"use strict";
// Cinex app — Revisão tab: reference style profiles (scripts/estilo.py) and the "AI look" review (scripts/revisao.py).
// Loaded before app.js; uses its globals at call time.

let estilos = [];
const LEVEL = { alto: ["Importante", "lv-hi"], medio: ["Atenção", "lv-md"], ok: ["Ok", "lv-ok"] };

function bindReview() {
  $("#estilosel").onchange = () => renderEstilo();
  $("#estiloapply").onclick = () => {
    const e = estilos.find((x) => x.id === $("#estilosel").value); if (!st) return;
    if (!e) { st.estilo = null; if (String(st.color.look).startsWith("ref:")) st.color.look = "natural"; }
    else {
      st.estilo = e.id;
      if (e.legenda) Object.assign(st.captions, e.legenda);
      if (e.camera) Object.assign(st.camera, e.camera);
      st.color.look = "ref:" + e.id;
    }
    renderAll(); save({ estilo: st.estilo, captions: st.captions, camera: st.camera, color: st.color });
  };
  $("#revrun").onclick = async () => {
    if (!name) return; $("#revrun").disabled = true;
    try { renderReview(await api(`/api/p/${name}/revisao`, { method: "POST", body: "{}" })); }
    catch (e) { $("#revlist").textContent = e.message; } finally { $("#revrun").disabled = false; }
  };
  $("#revask").onclick = async () => {
    if (!name) return;
    await api(`/api/p/${name}/chat`, { method: "POST", body: JSON.stringify({ text: "Revise a edição: o que ainda tem cara de inteligência artificial?" }) });
    await reloadState();
  };
  loadEstilos();
}

async function loadEstilos() {
  estilos = await api("/api/estilos").catch(() => []);
  const sel = $("#estilosel"), cur = st && st.estilo;
  sel.replaceChildren(new Option("Nenhum", ""), ...estilos.map((e) => new Option(e.id + (e.revisado ? "" : " (só medido)"), e.id)));
  sel.value = cur || ""; renderEstilo();
  if (st) { estiloLook(); bindLookButtons(); renderLookUI(); }
}

function estiloLook() {             // LOOKS entry for the applied reference, so the Cor tab can show/select it
  const e = st && estilos.find((x) => x.id === st.estilo);
  for (const k of Object.keys(LOOKS)) if (k.startsWith("ref:")) delete LOOKS[k];
  if (e) LOOKS["ref:" + e.id] = ["Ref: " + e.id, e.css || "", .08, "linear-gradient(135deg,#6c65c7,#2383e2)"];
}

function renderEstilo() {
  const box = $("#estiloinfo"), e = estilos.find((x) => x.id === $("#estilosel").value);
  if (!estilos.length) { box.className = "selinfo muted"; box.textContent = "Nenhum perfil ainda. Mande vídeos de referência ao Claude: ele mede e cria o perfil em ~/reels-banco/estilos."; return; }
  if (!e) { box.className = "selinfo muted"; box.textContent = "Sem estilo de referência: a edição segue as regras gerais do manual."; return; }
  box.className = "selinfo";
  const rows = [];
  const line = (k, v) => { if (v == null || v === "") return; const r = document.createElement("div"); r.className = "kv";
    const a = document.createElement("span"); a.className = "muted"; a.textContent = k; const b = document.createElement("span"); b.textContent = v; r.append(a, b); rows.push(r); };
  const r = e.ritmo || {};
  line("Vídeos", `${e.videos}${e.revisado ? "" : " · regras visuais ainda não preenchidas"}`);
  line("Ritmo", r.plano_mediano_s != null ? `plano de ${r.plano_mediano_s} s · ${r.cortes_por_10s} cortes/10 s · ${r.cortes_nos_3s} no gancho` : "");
  if (e.legenda) line("Legenda", `${e.legenda.upper ? "CAIXA ALTA" : "normal"} · ${e.legenda.words || "?"} palavras · ${e.legenda.lines || 1} linha(s)`);
  line("Gancho", e.gancho); line("Notas", e.notas);
  const imgs = document.createElement("div"); imgs.className = "refsheets";
  for (const f of e.folhas.filter((f) => f.startsWith("quadros") || f.startsWith("gancho")).slice(0, 4)) {
    const a = document.createElement("a"); a.href = `/api/estilos/${e.id}/${f}`; a.target = "_blank"; a.title = f;
    const im = document.createElement("img"); im.src = a.href; im.loading = "lazy"; a.append(im); imgs.append(a);
  }
  rows.push(imgs); box.replaceChildren(...rows);
}

function renderReview(r) {
  const box = $("#revlist"); if (!r || !r.itens) { box.textContent = ""; return; }
  const m = r.medidas || {};
  const head = document.createElement("p"); head.className = "muted small";
  head.textContent = `${m.duracao_s} s · ${m.cortes} cortes (plano ${m.plano_mediano_s} s) · ${m.motions} motions · ${m.sons} sons · ${m.legendas} legendas` +
    (r.estilo ? ` · comparado com ${r.estilo}` : "");
  box.replaceChildren(head, ...r.itens.map((it) => {
    const d = document.createElement("div"); d.className = "revitem " + LEVEL[it.nivel][1];
    const t = document.createElement("div"); const b = document.createElement("b"); b.textContent = `${LEVEL[it.nivel][0]} · ${it.area}`;
    t.append(b, document.createTextNode(" " + it.texto));
    d.append(t); if (it.sugestao) { const s = document.createElement("small"); s.textContent = "→ " + it.sugestao; d.append(s); }
    return d;
  }));
}

async function loadReview() {
  if (!name) return;
  renderReview(await api(`/api/p/${name}/revisao`).catch(() => null));
}
