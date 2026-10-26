"use strict";
// Cinex app — Marca tab: the brand behind the project (onboarding status), what performs on its Instagram
// (scripts/desempenho.py) and its niche references (links and videos, scripts/brand.py + estilo.py).
// Loaded before app.js; uses its globals at call time.

let marcas = [], marcaData = null;
const TAGNAMES = { formato: "Formato", estilo: "Estilo", duracao: "Duração", gancho: "Gancho", tema: "Tema", legenda: "Legenda", motion: "Motion" };

async function loadMarcas() {
  marcas = await api("/api/marcas").catch(() => []);
  const sel = $("#marcasel");
  sel.replaceChildren(new Option("Nenhuma", ""), ...marcas.map((m) => new Option("@" + m.handle, m.handle)));
  sel.value = (st && st.marca) || ""; await renderMarca();
}

function bindMarca() {
  $("#marcasel").onchange = async () => { if (!st) return; st.marca = $("#marcasel").value || null; save({ marca: st.marca }); await renderMarca(); };
  $("#refaddlink").onclick = async () => {
    const url = $("#reflink").value.trim(); if (!url || !st || !st.marca) return;
    try { await api(`/api/marca/${st.marca}/ref`, { method: "POST", body: JSON.stringify({ url, nota: $("#refnota").value }) });
      $("#reflink").value = ""; $("#refnota").value = ""; await renderMarca(); } catch (e) { alert(e.message); }
  };
  $("#refvideo").onchange = async (e) => {
    const f = e.target.files[0]; if (!f || !st || !st.marca) return;
    $("#refstatus").textContent = `Enviando ${f.name}…`;
    try {
      await api(`/api/marca/${st.marca}/refvideo`, { method: "POST", body: f, timeout: 600000,
        headers: { "X-Filename": f.name, "X-Nota": encodeURIComponent($("#refnota").value) } });
      $("#refnota").value = ""; $("#refstatus").textContent = "Vídeo salvo. Medindo ritmo e cor em segundo plano…";
      await renderMarca();
    } catch (err) { $("#refstatus").textContent = err.message; }
    e.target.value = "";
  };
  const ask = async (text) => { if (!name) return; await api(`/api/p/${name}/chat`, { method: "POST", body: JSON.stringify({ text }) }); await reloadState(); };
  $("#marcaonb").onclick = () => st && st.marca && ask(`Faça (ou atualize) o onboarding da marca @${st.marca}.`);
  $("#marcadesemp").onclick = () => st && st.marca && ask(`Atualize o desempenho de @${st.marca} com os últimos vídeos e Insights e me diga quais estilos e formatos estão funcionando.`);
  $("#refask").onclick = () => st && st.marca && ask(`Analise as referências do nicho de @${st.marca} (links e vídeos) e complete o perfil de estilo nicho_${st.marca}.`);
}

async function renderMarca() {
  const h = st && st.marca, box = $("#marcainfo");
  $("#marcabody").hidden = !h;
  if (!h) { box.className = "selinfo muted"; box.textContent = marcas.length ? "Escolha a marca deste projeto." : "Nenhuma marca ainda: peça ao Cinex para fazer o onboarding."; return; }
  marcaData = await api(`/api/marca/${h}`).catch(() => null); const m = marcaData; if (!m) return;
  box.className = "selinfo";
  const a = m.arquivos, ok = (f) => (a[f] ? "✓" : "—");
  const kv = (k, v) => { const r = document.createElement("div"); r.className = "kv"; const x = document.createElement("span"); x.className = "muted"; x.textContent = k;
    const y = document.createElement("span"); y.textContent = v; r.append(x, y); return r; };
  const rows = [kv("Perfil", `${ok("perfil.md")} negócio e público · ${ok("video.md")} análise dos Reels · ${ok("marca.json")} padrões de edição`)];
  if (m.perfil_atualizado) rows.push(kv("Base", m.perfil_atualizado));
  if (m.marca && m.marca.formatos_preferidos && m.marca.formatos_preferidos.length) rows.push(kv("Funciona", m.marca.formatos_preferidos.join(", ")));
  box.replaceChildren(...rows);
  $("#marcaonb").textContent = a["video.md"] && a["marca.json"] ? "Atualizar onboarding" : "Fazer onboarding com o Cinex";
  renderDesempenho(m.desempenho); renderRefs(m);
}

function renderDesempenho(rep) {
  const box = $("#desemp");
  if (!rep || !rep.reels) { box.className = "muted small"; box.textContent = "Sem números ainda. O Cinex lê os Reels e os Insights do perfil (você faz o login) e monta o ranking."; return; }
  box.className = "";
  const head = document.createElement("p"); head.className = "muted small";
  head.textContent = `${rep.reels} publicações · atualizado em ${rep.atualizado} · mediana ${Math.round(rep.mediana.views || 0)} views` +
    (rep.mediana.retencao ? ` · retenção ${Math.round(100 * rep.mediana.retencao)}%` : "");
  const parts = [head];
  for (const k of ["formato", "estilo", "duracao", "gancho"]) {
    const rows = (rep.ranking[k] || []).slice(0, 4); if (!rows.length) continue;
    const t = document.createElement("div"); t.className = "rank";
    const h = document.createElement("b"); h.textContent = TAGNAMES[k]; t.append(h);
    for (const r of rows) {
      const line = document.createElement("div"); line.className = "rankrow" + (r.score >= 1.15 ? " up" : r.score < .85 ? " down" : "");
      const bar = document.createElement("i"); bar.style.width = Math.min(100, Math.round(50 * r.score)) + "%";
      const label = document.createElement("span"); label.textContent = `${r.valor} (${r.n})`;
      const val = document.createElement("small"); val.textContent = `${r.score.toFixed(2)} · ${Math.round(r.views || 0)} views` + (r.retencao ? ` · ${Math.round(100 * r.retencao)}%` : "");
      line.append(bar, label, val); t.append(line);
    }
    parts.push(t);
  }
  box.replaceChildren(...parts);
}

function renderRefs(m) {
  const list = $("#reflist");
  list.replaceChildren(...(m.referencias.length ? m.referencias.map((r) => {
    const d = document.createElement("div"); d.className = "refrow";
    const ic = document.createElement("span"); ic.textContent = r.tipo === "link" ? "🔗" : "🎬"; ic.className = "muted";
    const t = document.createElement(r.tipo === "link" ? "a" : "span"); t.className = "reftxt";
    if (r.tipo === "link") { t.href = r.url; t.target = "_blank"; t.rel = "noopener"; t.textContent = r.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 48); }
    else t.textContent = r.arquivo;
    const meta = document.createElement("small"); meta.className = "muted";
    meta.textContent = (r.nota ? r.nota + " · " : "") + (r.analisado ? "analisada" : r.tipo === "video" && m.analisando ? "medindo…" : "a analisar");
    const del = document.createElement("button"); del.className = "icon"; del.textContent = "×"; del.title = "Remover";
    del.onclick = async () => { await api(`/api/marca/${m.handle}/refs/${r.id}/remover`, { method: "POST", body: "{}" }); await renderMarca(); };
    const txt = document.createElement("div"); txt.append(t, meta); d.append(ic, txt, del); return d;
  }) : [Object.assign(document.createElement("p"), { className: "muted small", textContent: "Nenhuma referência ainda. Cole links do Instagram/TikTok/YouTube ou envie vídeos do nicho." })]));
  $("#refstatus").textContent = m.analisando ? "Medindo ritmo e cor dos vídeos…" : m.estilo_nicho ? `Perfil de estilo: ${m.estilo_nicho} (aparece na aba Revisão).` : "";
}
