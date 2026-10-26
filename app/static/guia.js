"use strict";
// Cinex — guided mode for people who don't edit video. One page per step on the left/centre, the chat with the AI
// always on the right (the main way to change things), voice commands through the local whisper (/api/voz).
// The preview is the full editor's program monitor in an iframe (/editor?embed=1), so captions, motion, B-roll and
// camera look exactly like in the editor. State is the same ~/reels/<name>/cinex.json Claude Code reads and edits.

const $ = (s) => document.querySelector(s);
const H = { "X-Cinex": "1" };
async function api(path, opt = {}) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), opt.timeout || 20000);
  let r, j;
  try { r = await fetch(path, { ...opt, signal: ctl.signal, headers: { ...H, ...(opt.headers || {}) } }); j = await r.json().catch(() => ({})); }
  finally { clearTimeout(timer); }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const fmt = (t) => `${Math.floor((t || 0) / 60)}:${String(Math.floor((t || 0) % 60)).padStart(2, "0")}`;
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} } };

let name = null, st = null, prep = null, exp = null, step = "comecar", projects = [], marcas = [], fresh = false;
let sentAt = 0, lastCinex = 0, review = null, typing = false;

// ------------------------------------------------------------ data helpers (same rules as the editor)
function playOrder() {
  const keptRaw = st.segments.filter((g) => g.keep).sort((a, b) => a.s - b.s), by = new Map(keptRaw.map((g) => [g.id, g]));
  const out = [...new Set((st.order || []).filter((i) => by.has(i)))];
  keptRaw.forEach((g, j) => {
    if (out.includes(g.id)) return;
    const prev = keptRaw.slice(0, j).reverse().find((k) => out.includes(k.id));
    out.splice(prev ? out.indexOf(prev.id) + 1 : 0, 0, g.id);
  });
  return out.map((i) => by.get(i));
}
const segLen = (g) => (g.e - g.s) / (g.speed || 1);
function phrases() {                    // kept segments grouped into phrases (ends at . ? ! or a jump in the order)
  const out = []; let cur = [];
  for (const g of playOrder()) {
    if (cur.length && (Math.abs(g.s - cur.at(-1).e) > 1 || /[.?!]\s*$/.test(cur.at(-1).text || ""))) { out.push(cur); cur = []; }
    cur.push(g);
  }
  if (cur.length) out.push(cur);
  return out;
}
const keptTotal = () => st.segments.filter((g) => g.keep).reduce((a, g) => a + segLen(g), 0);
const FORMATS = { vertical: [1080, 1920, "9:16", "Reels, Stories, TikTok"], feed: [1080, 1350, "4:5", "Feed do Instagram"],
                  quadrado: [1080, 1080, "1:1", "Quadrado"], horizontal: [1920, 1080, "16:9", "YouTube, site"],
                  "4x3": [1440, 1080, "4:3", "Apresentação"], led: [1024, 768, "LED", "Painel de feira 512×384"] };
const PRESETS = {
  Hormozi: ["Forte e chamativa", "Palavra a palavra, caixa alta, destaque amarelo", { font: "sans", weight: "Black", upper: true, size: 62, stroke: 6, words: 3, color: "#FFFFFF", accent: "#FFD400" }],
  Minimal: ["Discreta", "Frases curtas, sem contorno: autoridade", { font: "sans", weight: "SemiBold", upper: false, size: 50, stroke: 0, words: 3, color: "#FFFFFF", accent: "#FF8A47" }],
  Cinema: ["Cinematográfica", "Letra alta e condensada, sem contorno", { font: "cond", weight: "Black", upper: true, size: 78, stroke: 0, words: 3, color: "#FFFFFF", accent: "#FFD400" }],
};
const LOOKS = { natural: ["Natural", "#8a8f86"], clean_warm: ["Quente suave", "#c8b08a"], teal_orange: ["Cinema", "linear-gradient(135deg,#2c6e74,#e0874a)"],
                moody: ["Escuro e dramático", "#3a3640"], vivid_day: ["Dia vivo", "linear-gradient(135deg,#3d9be0,#f2c14e)"], none: ["Sem cor extra", "#777"] };
const ACCENTS = ["#FFD400", "#22C55E", "#FF8A47", "#38BDF8", "#F43F5E", "#FFFFFF"];
const MOTION_NAMES = { titulo: "Título", topico: "Tópico", nome: "Nome de quem fala", citacao: "Citação", frase: "Frase grande", seguir: "Chamada para seguir",
                       salvar: "Chamada para salvar", gigante: "Palavra gigante", cenario: "Texto 3D no cenário" };

async function save(patch) {
  Object.assign(st, patch);
  const r = await api(`/api/p/${name}/state`, { method: "PUT", body: JSON.stringify(patch) }); st.rev = r.rev;
}
const guia = () => (st && st.guia) || {};
async function mark(k) { if (!guia()[k]) await save({ guia: { ...guia(), [k]: true } }); }

// ------------------------------------------------------------ steps
const STEPS = [
  { id: "comecar", icon: "🎬", title: "Começar", lead: "Escolha a marca e envie o vídeo.", pv: false, done: () => !!(st && st.segments.length) },
  { id: "corte", icon: "✂️", title: "Corte", lead: "A IA tirou pausas, repetições e tropeços. Confira as frases.", pv: true, done: () => !!(st && st.cut_locked) },
  { id: "estilo", icon: "🎨", title: "Estilo", lead: "Onde vai publicar, como a legenda aparece e a cor do vídeo.", pv: true, done: () => !!guia().estilo },
  { id: "elementos", icon: "✨", title: "Elementos", lead: "Textos na tela, imagens extras e música.", pv: true, done: () => !!guia().elementos },
  { id: "revisao", icon: "🔍", title: "Revisão", lead: "Uma conferência do que ainda parece edição automática.", pv: true, done: () => !!guia().revisao },
  { id: "publicar", icon: "🚀", title: "Publicar", lead: "Gere o vídeo final e prepare a postagem.", pv: true, done: () => !!(exp && exp.out) },
];
const CHIPS = {
  comecar: ["Quero cadastrar minha marca", "Que tipo de vídeo funciona no meu perfil?"],
  corte: ["Deixa mais curto, só o essencial", "Começa com a frase mais forte", "Tira repetições e vícios de linguagem", "Por que você cortou essas partes?"],
  estilo: ["Legenda maior", "Destaca os números na legenda", "Deixa com cara de cinema", "Usa as cores da minha marca"],
  elementos: ["Sugere textos na tela para este vídeo", "Coloca o nome de quem fala no começo", "Põe efeitos sonoros só nos pontos-chave", "Qual música viral combina com este vídeo?"],
  revisao: ["O que ainda parece feito por IA?", "Corrige os pontos da revisão", "Assiste e me diz o que melhorar"],
  publicar: ["Escreve a legenda do post", "Qual o melhor horário para postar?", "Sugere uma música viral do Instagram"],
};
const stepIdx = () => STEPS.findIndex((s) => s.id === step);
const needsProject = (id) => id !== "comecar";

function go(id) {
  if (needsProject(id) && !(st && st.segments.length)) id = "comecar";
  step = id; if (name) location.hash = `${name}/${id}`;
  render();
  $(".page").scrollTop = 0;
}

function renderSteps() {
  $("#gsteps").replaceChildren(...STEPS.map((s, i) => {
    const locked = needsProject(s.id) && !(st && st.segments.length);
    const b = el("button", "step" + (s.id === step ? " on" : "") + (s.done() ? " done" : "") + (locked ? " locked" : ""));
    b.append(el("span", "ic", s.icon), el("span", "", s.title), el("span", "num", s.done() ? "✓" : String(i + 1)));
    b.disabled = locked; b.onclick = () => go(s.id); return b;
  }));
}

function header(box, s) {
  box.append(el("div", "picon", s.icon), el("h1", "ptitle", s.title), el("p", "plead", s.lead));
}
function callout(box, emoji, text, kind) {
  const c = el("div", "callout" + (kind ? " " + kind : "")); c.append(el("span", "ce", emoji), el("div", "", text)); box.append(c); return c;
}
function navrow(box, nextLabel, onNext) {
  const r = el("div", "navrow"), i = stepIdx();
  if (i > 0) { const b = el("button", "btn", "← Voltar"); b.onclick = () => go(STEPS[i - 1].id); r.append(b); }
  r.append(el("span", "spacer"));
  if (i < STEPS.length - 1 || onNext) {
    const n = el("button", "btn primary", nextLabel || "Próximo →");
    n.onclick = async () => { n.disabled = true; try { if (onNext) await onNext(); go(STEPS[Math.min(i + 1, STEPS.length - 1)].id); } catch (e) { alert(e.message); n.disabled = false; } };
    r.append(n);
  }
  box.append(r);
}

// ------------------------------------------------------------ pages
const PAGES = {
  async comecar(box) {
    const s = STEPS[0]; header(box, s);
    const novo = fresh || !name;
    // brand
    box.append(el("h3", "", "1. De qual marca é o vídeo?"));
    const cur = novo ? store.get("cinex.marca") || "" : (st && st.marca) || "";
    const cards = el("div", "cards");
    const pick = async (h) => { if (novo) store.set("cinex.marca", h); else await save({ marca: h || null }); render(); };
    for (const m of [{ handle: "" }, ...marcas]) {
      const c = el("button", "card" + (cur === m.handle ? " on" : ""));
      c.append(el("b", "", m.handle ? "@" + m.handle : "Sem marca"),
               el("small", "", m.handle ? (m.arquivos && m.arquivos["perfil.md"] ? "perfil pronto" : "perfil a completar") : "edição com as regras gerais"));
      c.onclick = () => pick(m.handle); cards.append(c);
    }
    box.append(cards);
    if (!marcas.length) callout(box, "💡", "Ainda não há marca cadastrada. Peça no chat “quero cadastrar minha marca”: o Cinex analisa seu perfil e passa a editar no seu estilo.");
    // video
    box.append(el("h3", "", novo ? "2. Envie o vídeo" : "2. Seu vídeo"));
    if (novo) {
      const d = el("div", "drop"); d.append(el("div", "de", "📥"), el("div", "", "Arraste o vídeo aqui ou clique para escolher"),
                                          el("div", "muted small", "Vídeo do celular, do jeito que gravou. A IA assiste, transcreve e propõe o corte."));
      d.onclick = () => $("#gfile").click();
      d.ondragover = (e) => { e.preventDefault(); d.classList.add("over"); }; d.ondragleave = () => d.classList.remove("over");
      d.ondrop = (e) => { e.preventDefault(); d.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) upload(f); };
      box.append(d);
      const pr = el("form", "pathrow"), inp = el("input"); inp.placeholder = "ou cole o caminho do arquivo (C:\\…\\IMG_1234.MOV)";
      const b = el("button", "btn", "Abrir"); pr.append(inp, b);
      pr.onsubmit = async (e) => { e.preventDefault(); const src = inp.value.trim().replace(/^"|"$/g, ""); if (!src) return;
        try { const r = await api("/api/projects", { method: "POST", body: JSON.stringify({ src }) }); await afterNew(r.name); } catch (err) { alert(err.message); } };
      const um = el("p", "muted small"); um.id = "upmsg"; box.append(pr, um);
      if (name) { const c = el("button", "linkbtn", "← voltar para o vídeo aberto"); c.onclick = () => { fresh = false; render(); }; box.append(c); }
      return;
    }
    const running = prep && prep.done === false;
    if (running || (prep && prep.error)) {
      if (prep.error) callout(box, "⚠️", "Algo deu errado ao preparar: " + prep.error, "err");
      else {
        const c = callout(box, "🤖", ""); c.lastChild.append(el("b", "", prep.step || "Preparando"), el("div", "muted small", "A IA está assistindo e transcrevendo o vídeo. Leva alguns minutos; pode deixar a página aberta."));
        const bar = el("div", "bar"), sp = el("span"); sp.style.width = (prep.pct || 0) + "%"; bar.append(sp); c.lastChild.append(bar);
      }
    }
    if (st && st.segments.length) {
      const stt = el("div", "stats");
      const add = (v, l) => { const x = el("div", "stat"); x.append(el("b", "", v), el("span", "", l)); stt.append(x); };
      add(fmt(st.duration), "vídeo gravado"); add(fmt(keptTotal()), "depois do corte"); add(String((st.clips || []).length || 1), (st.clips || []).length > 1 ? "vídeos juntos" : "vídeo");
      box.append(stt);
      callout(box, "✅", "Vídeo pronto. A IA já fez um primeiro corte; no próximo passo você confere.", "ok");
      const more = el("button", "btn", "＋ Juntar mais vídeos (palestra, evento)"); more.onclick = () => $("#gfiles").click();
      box.append(more);
      navrow(box);
    }
  },

  async corte(box) {
    const s = STEPS[1]; header(box, s);
    const stt = el("div", "stats");
    const add = (v, l) => { const x = el("div", "stat"); x.append(el("b", "", v), el("span", "", l)); stt.append(x); };
    add(fmt(st.duration), "gravado"); add(fmt(keptTotal()), "editado"); add(String(st.segments.filter((g) => !g.keep).length), "cortes");
    box.append(stt);
    const locked = st.cut_locked;
    callout(box, "💡", locked ? "Corte aprovado. Para mudar algo, reabra o corte ou peça no chat."
      : "Cada linha é uma frase do vídeo, na ordem em que vai aparecer. Desmarque o que não quer. Para mudar a ordem ou pedir algo diferente, é só falar no chat.");
    box.append(el("h3", "", "Frases do vídeo"));
    const list = el("div", "rows");
    for (const p of phrases()) {
      const r = el("div", "row"), cb = el("input"); cb.type = "checkbox"; cb.checked = true; cb.disabled = locked;
      cb.onchange = async () => { for (const g of p) { g.keep = false; g.reason = "tirado no modo guiado"; } await saveCut(); };
      const txt = p.map((g) => g.text).join(" ").trim();
      const pl = el("button", "play", "▶"); pl.title = "Ver este trecho"; pl.onclick = () => preview(p[0].s);
      r.append(cb, editable(txt, p), el("span", "rm", (p.reduce((a, g) => a + segLen(g), 0)).toFixed(1) + " s"), pl); list.append(r);
    }
    box.append(list);
    const cut = st.segments.filter((g) => !g.keep && (g.text || "").trim());
    if (cut.length) {
      const d = el("details", "toggle"); d.append(el("summary", "", `O que saiu (${cut.length} trechos com fala)`));
      const l2 = el("div", "rows");
      for (const g of cut) {
        const r = el("div", "row"), cb = el("input"); cb.type = "checkbox"; cb.checked = false; cb.disabled = locked;
        cb.onchange = async () => { g.keep = true; g.reason = ""; await saveCut(); };
        const pl = el("button", "play", "▶"); pl.onclick = () => preview(g.s, true);
        r.append(cb, el("span", "rt off", g.text), el("span", "rm", g.reason || "cortado"), pl); l2.append(r);
      }
      d.append(l2); box.append(d);
    }
    if (locked) { const b = el("button", "btn", "Reabrir o corte"); b.onclick = async () => { await save({ cut_locked: false }); render(); }; box.append(b); }
    navrow(box, locked ? "Próximo →" : "Aprovar corte e seguir →", async () => { if (!st.cut_locked) await save({ cut_locked: true }); });
  },

  async estilo(box) {
    const s = STEPS[2]; header(box, s);
    box.append(el("h3", "", "Onde vai publicar?"));
    const fc = el("div", "cards");
    for (const [k, [w, h, ar, desc]] of Object.entries(FORMATS)) {
      const c = el("button", "card" + ((st.format || "vertical") === k ? " on" : "")), sh = el("div", "shape");
      const sc = 36 / Math.max(w, h); sh.style.width = w * sc + "px"; sh.style.height = h * sc + "px";
      c.append(sh, el("b", "", ar), el("small", "", desc));
      c.onclick = async () => { await save({ format: k }); render(); }; fc.append(c);
    }
    box.append(fc);
    box.append(el("h3", "", "Legenda"));
    const lc = el("div", "cards"), cap = st.captions;
    for (const [k, [label, desc, p]] of Object.entries(PRESETS)) {
      const on = cap.enabled && cap.font === p.font && cap.weight === p.weight && cap.upper === p.upper && cap.stroke === p.stroke;
      const c = el("button", "card" + (on ? " on" : "")), sw = el("div", "sw");
      const t = el("span", "", p.upper ? "ISSO MUDA" : "isso muda"); t.style.cssText = `font-weight:${p.weight === "Black" ? 900 : 600};font-family:${p.font === "cond" ? "Impact, 'Arial Narrow', sans-serif" : "inherit"};` +
        `font-size:${p.font === "cond" ? 22 : 17}px;${p.stroke ? "-webkit-text-stroke:1px #000;paint-order:stroke fill;" : ""}`;
      const kw = el("span", "", p.upper ? " TUDO" : " tudo"); kw.style.color = cap.accent || p.accent; t.append(kw); sw.append(t);
      c.append(sw, el("b", "", label), el("small", "", desc));
      c.onclick = async () => { await save({ captions: { ...cap, ...p, accent: cap.accent || p.accent, enabled: true } }); render(); }; lc.append(c);
    }
    const off = el("button", "card" + (cap.enabled ? "" : " on")), sw0 = el("div", "sw", "—"); off.append(sw0, el("b", "", "Sem legenda"), el("small", "", "Só o vídeo"));
    off.onclick = async () => { await save({ captions: { ...cap, enabled: false } }); render(); }; lc.append(off);
    box.append(lc);
    box.append(el("div", "muted small", "Cor de destaque (palavras importantes)"));
    const sws = el("div", "swatches");
    for (const col of ACCENTS) { const b = el("button", "swatch" + ((cap.accent || "").toUpperCase() === col ? " on" : "")); b.style.background = col; b.title = col;
      b.onclick = async () => { await save({ captions: { ...cap, accent: col } }); render(); }; sws.append(b); }
    box.append(sws);
    box.append(el("h3", "", "Cor do vídeo"));
    const cc = el("div", "cards");
    for (const [k, [label, swc]] of Object.entries(LOOKS)) {
      const c = el("button", "card" + ((st.color || {}).look === k ? " on" : "")), sw = el("div", "sw"); sw.style.background = swc;
      c.append(sw, el("b", "", label)); c.onclick = async () => { await save({ color: { ...(st.color || {}), look: k } }); render(); }; cc.append(c);
    }
    box.append(cc);
    callout(box, "🗣️", "Quer algo diferente? Diga no chat, por exemplo: “legenda um pouco maior e mais para baixo”.");
    navrow(box, null, () => mark("estilo"));
  },

  async elementos(box) {
    const s = STEPS[3]; header(box, s);
    box.append(el("h3", "", "Textos na tela"));
    const ms = (st.motions || []).slice().sort((a, b) => a.t0 - b.t0);
    if (!ms.length) callout(box, "✨", "Nenhum texto na tela ainda. Peça “sugere textos na tela para este vídeo”: a IA escolhe os pontos que ajudam a entender (números, o problema, o benefício).");
    const l = el("div", "rows");
    for (const m of ms) {
      const r = el("div", "row"), pl = el("button", "play", "▶"); pl.onclick = () => preview(m.t0);
      const x = el("button", "play", "✕"); x.title = "Remover"; x.onclick = async () => { await save({ motions: st.motions.filter((y) => y !== m) }); render(); };
      r.append(el("span", "badge", MOTION_NAMES[m.type] || m.type), el("span", "rt", m.text || ""), pl, x); l.append(r);
    }
    box.append(l);
    box.append(el("h3", "", "Imagens extras (B-roll)"));
    const nb = (st.broll || []).length, nm = (st.media || []).length;
    callout(box, "🎞️", nm ? `${nm} clipe(s) enviado(s), ${nb} usado(s) por cima da fala. Diga no chat onde cada um entra: “mostra o clipe da obra quando eu falo do telhado”.`
      : "Envie imagens do que você fala (a obra, o produto, o cliente). A imagem troca e a sua voz continua.");
    const ub = el("button", "btn", "＋ Enviar imagens extras"); ub.onclick = () => { $("#gfiles").dataset.kind = "broll"; $("#gfiles").click(); }; box.append(ub);
    box.append(el("h3", "", "Música"));
    callout(box, "🎵", "Música viral: adicione no editor do Instagram na hora de publicar (é o jeito de não ter o vídeo silenciado). Peça no chat uma sugestão de música e o ponto de entrada.");
    const mu = st.music;
    if (mu && mu.src) {
      const r = el("div", "row"), x = el("button", "play", "✕"); x.onclick = async () => { await save({ music: null }); render(); };
      r.append(el("span", "", "♪"), el("span", "rt", mu.src.split(/[\\/]/).pop() + " · abaixa quando alguém fala"), x); box.append(r);
    } else {
      const b = el("button", "btn", "Tenho uma trilha licenciada (Artlist, Epidemic…)"); b.onclick = () => $("#gaudio").click(); box.append(b);
    }
    navrow(box, null, () => mark("elementos"));
  },

  async revisao(box) {
    const s = STEPS[4]; header(box, s);
    callout(box, "🔍", "A revisão mede o ritmo, as legendas, os textos e os sons, e compara com o estilo de referência. Cada ponto vem com o que fazer.");
    const b = el("button", "btn primary", review ? "Revisar de novo" : "Revisar agora");
    b.onclick = async () => { b.disabled = true; b.textContent = "Revisando…"; try { review = await api(`/api/p/${name}/revisao`, { method: "POST", body: "{}" }); await mark("revisao"); } catch (e) { alert(e.message); } render(); };
    box.append(b);
    if (review) {
      const items = review.itens || [], lv = { alto: ["Importante", "hi"], medio: ["Atenção", "md"], ok: ["Ok", "okb"] };
      if (!items.length) callout(box, "🎉", "Nada a corrigir: o vídeo segue as regras do manual.", "ok");
      const l = el("div", "rows");
      for (const it of items) {
        const r = el("div", "row"), [lab, cls] = lv[it.nivel] || ["", ""], t = el("div", "rt");
        t.append(el("div", "", it.texto)); if (it.sugestao) t.append(el("div", "muted small", it.sugestao));
        const fx = el("button", "linkbtn small", "Pedir correção"); fx.onclick = () => send(`Corrige este ponto da revisão: ${it.texto}${it.sugestao ? " (" + it.sugestao + ")" : ""}`);
        r.append(el("span", "badge " + cls, lab), t); if (it.nivel !== "ok") r.append(fx); l.append(r);
      }
      box.append(l);
    }
    navrow(box);
  },

  async publicar(box) {
    const s = STEPS[5]; header(box, s);
    const f = FORMATS[st.format || "vertical"];
    const stt = el("div", "stats");
    const add = (v, l) => { const x = el("div", "stat"); x.append(el("b", "", v), el("span", "", l)); stt.append(x); };
    add(f[2], f[3]); add(fmt(keptTotal()), "duração"); add(st.captions.enabled ? "com" : "sem", "legenda");
    box.append(stt);
    const running = exp && exp.done === false;
    if (running) {
      const c = callout(box, "⏳", ""); c.lastChild.append(el("b", "", (exp.step || "Gerando") + "…"), el("div", "muted small", "Isso leva alguns minutos. Pode continuar conversando no chat."));
      const bar = el("div", "bar"), sp = el("span"); sp.style.width = (exp.pct || 0) + "%"; bar.append(sp); c.lastChild.append(bar);
    } else if (exp && exp.error) callout(box, "⚠️", "A geração falhou: " + exp.error + ". Conte no chat que eu verifico.", "err");
    else if (exp && exp.out) {
      const c = callout(box, "🎉", "", "ok"); c.lastChild.append(el("b", "", "Vídeo pronto!"), el("div", "small", exp.out));
      const sb = el("button", "btn", "Mostrar na pasta"); sb.onclick = () => api(`/api/p/${name}/mostrar`, { method: "POST", body: "{}" }).catch((e) => alert(e.message));
      c.lastChild.append(el("div", "", "")); c.lastChild.lastChild.append(sb);
    }
    const gb = el("button", "btn primary big", exp && exp.out ? "Gerar de novo" : "Gerar vídeo final"); gb.disabled = running;
    gb.onclick = async () => { gb.disabled = true; try { await api(`/api/p/${name}/export`, { method: "POST", body: "{}" }); await poll(); } catch (e) { alert(e.message); gb.disabled = false; } };
    box.append(gb);
    box.append(el("h3", "", "Versões curtas"));
    box.append(el("p", "muted small", "A mesma edição em 10, 15 ou 30 segundos: gancho, chamada final e as frases com mais prova. Vira um vídeo novo na lista."));
    const vr = el("div", "swatches");
    for (const sec of [10, 15, 30]) {
      const b = el("button", "btn", `${sec} s`);
      b.onclick = async () => { b.disabled = true; try { const r = await api(`/api/p/${name}/versao`, { method: "POST", body: JSON.stringify({ s: sec }) });
        await loadProjects(); if (confirm(`Versão de ${r.total} s criada (${r.name}). Abrir agora?`)) openProject(r.name, "corte"); } catch (e) { alert(e.message); } b.disabled = false; };
      vr.append(b);
    }
    box.append(vr);
    callout(box, "📱", "Ao postar: adicione a música viral no editor do Instagram e use a legenda do post que o Cinex escreve (peça no chat).");
    navrow(box);
  },
};

// a phrase's text: click to correct what the transcription got wrong (captions follow; timings are re-aligned)
function editable(txt, segs) {
  const sp = el("span", "rt edit", txt || "(sem fala)"); sp.title = "Clique para corrigir o texto";
  sp.onclick = () => {
    const box = el("div", "rt editbox"), ta = el("textarea"); ta.value = txt; ta.rows = Math.max(2, Math.ceil(txt.length / 60));
    const ok = el("button", "btn primary", "Salvar"), no = el("button", "btn", "Cancelar"), bar = el("div", "editbar");
    bar.append(ok, no, el("span", "muted small", "A legenda passa a usar este texto."));
    box.append(ta, bar); sp.replaceWith(box); ta.focus();
    const close = () => { box.replaceWith(sp); };
    no.onclick = (e) => { e.preventDefault(); close(); render(); };
    ta.onkeydown = (e) => { if (e.key === "Escape") { close(); render(); } if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ok.click(); } };
    ok.onclick = async (e) => {
      e.preventDefault(); ok.disabled = true;
      const s = Math.min(...segs.map((g) => g.s)), en = Math.max(...segs.map((g) => g.e));
      try { await api(`/api/p/${name}/texto`, { method: "POST", body: JSON.stringify({ s, e: en, text: ta.value }) }); close(); await refresh(); }
      catch (err) { alert(err.message); ok.disabled = false; }
    };
  };
  return sp;
}

async function saveCut() {
  st.order = playOrder().map((g) => g.id);
  await save({ segments: st.segments, order: st.order }); render();
}

// ------------------------------------------------------------ preview (iframe = editor's monitor)
function frameWin() { const w = $("#gframe").contentWindow; return w && w.document && w.document.querySelector("#video") ? w : null; }
function preview(t, raw) {
  const w = frameWin(); if (!w) return;
  const v = w.document.querySelector("#video");
  if (raw) { const sk = w.document.querySelector("#skipcut"); if (sk) sk.checked = false; }   // a removed stretch: play it anyway
  v.currentTime = t + .01; v.play().catch(() => {});
}
function sizePreview() {
  const [FW, FH] = FORMATS[(st && st.format) || "vertical"], ar = FW / FH, f = $("#gframe");
  let h = Math.min(580, window.innerHeight - 80), w = h * ar * .9 + 16;      // the text column keeps most of the width
  if (w > 480) { w = 480; h = (w - 16) / ar + 60; }
  f.style.width = Math.round(w) + "px"; f.style.height = Math.round(h) + "px";
}

// ------------------------------------------------------------ render
async function render() {
  renderSteps(); renderChips(); renderChat();
  $("#geditor").href = name ? "/editor#" + name : "/editor";
  const s = STEPS.find((x) => x.id === step), box = $("#gpage");
  if (document.activeElement && box.contains(document.activeElement) && document.activeElement.matches("input, textarea")) return;   // keep what's being typed
  const out = el("div"); await PAGES[step](out); box.replaceChildren(...out.childNodes);
  if (box.dataset.step !== step) { box.dataset.step = step; box.classList.remove("enter"); void box.offsetWidth; box.classList.add("enter"); }   // page slide-in
  const showPv = s.pv && st && st.segments.length;
  $("#gpv").hidden = !showPv; if (showPv) sizePreview();
}

// ------------------------------------------------------------ chat
let chatKey = "", chatShown = 0;
function renderChat() {
  const box = $("#gmsgs"), atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  const chat = (st && st.chat) || [];
  const key = (name || "") + "|" + chat.length + "|" + ((chat.at(-1) || {}).t || "");
  if (key !== chatKey) {                                  // rebuild only when a message arrived (polling runs every 1.5 s)
  const fresh = key.split("|")[0] === chatKey.split("|")[0] ? chatShown : chat.length;   // animate only the new ones
  chatKey = key; chatShown = chat.length;
  if (!name) {
    box.replaceChildren(el("div", "empty", "Oi! Eu sou o Cinex. Envie seu vídeo ao lado e eu cuido da edição. Depois é só me dizer o que quer mudar, escrevendo ou falando."));
  } else {
    const msgs = chat.map((m, i) => {
      const u = m.who === "user", d = el("div", "msg" + (u ? " user" : "") + (i >= fresh ? " new" : ""));
      const who = el("div", "who", u ? "Você" : "Cinex"); who.append(el("small", "", (m.t || "").slice(11, 16)));
      const body = el("div"); body.append(who, el("div", "txt", m.text));
      d.append(el("div", "av", u ? "V" : "C"), body); return d;
    });
    box.replaceChildren(...(msgs.length ? msgs : [el("div", "empty", "Peça qualquer ajuste aqui, do seu jeito: “tira a parte em que eu gaguejo”, “legenda maior”, “coloca o preço na tela”.")]));
  }
  if (atEnd) box.scrollTop = box.scrollHeight;
  }
  // waiting for the AI
  const last = chat.at(-1), wait = name && last && last.who === "user";
  const stt = $("#gstatus");
  if (!wait) { stt.hidden = true; return; }
  const secs = (Date.now() - (sentAt || Date.parse(last.t))) / 1000;
  stt.hidden = false; stt.className = "status" + (secs > 45 ? " warn" : "");
  stt.replaceChildren(...(secs > 45
    ? [el("span", "", "Sem resposta ainda. O Claude Code precisa estar aberto com o Cinex ouvindo esta conversa.")]
    : [Object.assign(el("span", "dots"), { innerHTML: "<i></i><i></i><i></i>" }), el("span", "", "O Cinex está trabalhando…")]));
}
function renderChips() {
  $("#gchips").replaceChildren(...(name ? CHIPS[step] || [] : []).map((t) => { const b = el("button", "chip", t); b.onclick = () => send(t); return b; }));
}
async function send(text) {
  text = (text || "").trim(); if (!text) return;
  if (!name) { alert("Envie um vídeo primeiro: a conversa fica guardada junto com ele."); return; }
  sentAt = Date.now();
  try { await api(`/api/p/${name}/chat`, { method: "POST", body: JSON.stringify({ text, passo: step }) }); $("#gin").value = ""; autosize(); await refresh(); }
  catch (e) { alert(e.message); }
}
function autosize() { const t = $("#gin"); t.style.height = "auto"; t.style.height = Math.min(160, t.scrollHeight) + "px"; }

// ------------------------------------------------------------ voice (local whisper on the server)
let rec = null, chunks = [], recTimer = null, recStart = 0;
function micState(s, label) { const m = $("#gmic"); m.className = "mic" + (s ? " " + s : ""); $("#gmiclabel").textContent = label; }
async function toggleMic() {
  if (rec && rec.state === "recording") { rec.stop(); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { alert("Não consegui usar o microfone. Libere o acesso ao microfone para esta página no navegador."); return; }
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
  rec = new MediaRecorder(stream, type ? { mimeType: type } : {}); chunks = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  rec.onstop = async () => {
    clearInterval(recTimer); stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
    if (blob.size < 2000) { micState("", "Falar"); return; }
    micState("busy", "Entendendo…");
    try {
      const r = await api("/api/voz", { method: "POST", body: blob, timeout: 120000, headers: { "Content-Type": blob.type } });
      micState("", "Falar"); handleVoice(r.text || "");
    } catch (e) { micState("", "Falar"); alert("Não entendi o áudio: " + e.message); }
  };
  rec.start(); recStart = Date.now(); micState("rec", "Ouvindo… toque para enviar");
  recTimer = setInterval(() => { const s = Math.floor((Date.now() - recStart) / 1000); $("#gmiclabel").textContent = `Ouvindo ${s}s… toque para enviar`; if (s >= 60) rec.stop(); }, 500);
}
const norm = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[.,!?;:]/g, "").trim();
function handleVoice(text) {
  const n = norm(text); if (!n) return;
  const stepNames = { comecar: "comecar", inicio: "comecar", corte: "corte", estilo: "estilo", elementos: "elementos", revisao: "revisao", publicar: "publicar", exportar: "publicar" };
  const i = stepIdx();
  if (/^(proximo|proxima|avancar|seguir|continuar)( passo| etapa| pagina)?$/.test(n)) return go(STEPS[Math.min(i + 1, STEPS.length - 1)].id);
  if (/^(voltar|anterior)( passo| etapa| pagina)?$/.test(n)) return go(STEPS[Math.max(i - 1, 0)].id);
  const m = n.match(/^(ir para|vai para|abrir|abre)( o| a)? (\w+)$/);
  if (m && stepNames[m[3]]) return go(stepNames[m[3]]);
  const w = frameWin();
  if (w && /^(tocar|toca|reproduzir|play|assistir|mostra o video)$/.test(n)) { w.document.querySelector("#video").play().catch(() => {}); return; }
  if (w && /^(pausar|pausa|parar|para)$/.test(n)) { w.document.querySelector("#video").pause(); return; }
  $("#gin").value = text; autosize(); send(text);        // everything else is a request for the AI
}

// ------------------------------------------------------------ projects, uploads, polling
async function loadProjects() {
  projects = await api("/api/projects").catch(() => []);
  const sel = $("#gproj");
  sel.replaceChildren(...(projects.length ? projects.map((p) => new Option(`${p.name} · ${fmt(p.duration)}`, p.name)) : [new Option("nenhum vídeo ainda", "")]));
  if (name) sel.value = name;
}
async function openProject(n, wantStep) {
  name = n; fresh = false; review = null; store.set("cinex.project", n);
  const j = await api(`/api/p/${n}`); st = j.state; prep = j.prep; exp = j.export;
  $("#gproj").value = n;
  $("#gframe").src = `/editor?embed=1#${n}`;
  go(wantStep || (st && st.segments.length ? (st.cut_locked ? "estilo" : "corte") : "comecar"));
}
async function afterNew(n) {
  const marca = store.get("cinex.marca");
  await loadProjects(); name = n; st = null; prep = { step: "Começando", pct: 1, done: false }; exp = null; fresh = false;
  $("#gproj").value = n; location.hash = `${n}/comecar`; step = "comecar"; render();
  const t = setInterval(async () => {                       // apply the chosen brand as soon as the project exists
    try { const j = await api(`/api/p/${n}`); if (j.state) { clearInterval(t); st = j.state; if (marca && !st.marca) await save({ marca }); } } catch {}
  }, 2000);
}
async function upload(f) {
  const msg = $("#upmsg"); if (msg) msg.textContent = `Enviando ${f.name} (${(f.size / 1e6).toFixed(0)} MB)…`;
  try {
    const r = await api("/api/upload", { method: "POST", body: f, timeout: 60 * 60 * 1000, headers: { "X-Filename": encodeURIComponent(f.name), "Content-Type": "application/octet-stream" } });
    await afterNew(r.name);
  } catch (e) { if (msg) msg.textContent = e.message; else alert(e.message); }
}
async function uploadMany(files, kind) {
  const paths = [];
  for (const [i, f] of files.entries()) {
    callStatus(`Enviando ${i + 1}/${files.length}: ${f.name}…`);
    const r = await api(`/api/p/${name}/${kind === "broll" ? "mediaup" : "clipup"}`, { method: "POST", body: f, timeout: 60 * 60 * 1000,
                         headers: { "X-Filename": encodeURIComponent(f.name), "Content-Type": "application/octet-stream" } });
    if (r.path) paths.push(r.path);
  }
  if (kind !== "broll" && paths.length) await api(`/api/p/${name}/clips`, { method: "POST", body: JSON.stringify({ paths }) });
  callStatus(""); await refresh();
}
function callStatus(t) { const s = $("#gstatus"); s.hidden = !t; s.className = "status"; s.textContent = t; }

let pollRev = -1;
async function poll() {
  if (!name) return;
  try {
    const p = await api(`/api/p/${name}/poll`);
    const changed = p.rev !== pollRev || JSON.stringify(p.prep) !== JSON.stringify(prep) || JSON.stringify(p.export) !== JSON.stringify(exp);
    prep = p.prep; exp = p.export;
    if (p.rev !== pollRev) { pollRev = p.rev; const j = await api(`/api/p/${name}`); st = j.state; }
    if (changed) render(); else renderChat();
  } catch {}
}
const refresh = async () => { pollRev = -1; await poll(); };

async function init() {
  $("#gform").onsubmit = (e) => { e.preventDefault(); send($("#gin").value); };
  $("#gin").oninput = autosize;
  $("#gin").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send($("#gin").value); } };
  $("#gmic").onclick = toggleMic;
  $("#gnew").onclick = () => { fresh = true; step = "comecar"; render(); };
  $("#gproj").onchange = (e) => e.target.value && openProject(e.target.value);
  $("#gfile").onchange = (e) => { const f = e.target.files[0]; e.target.value = ""; if (f) upload(f); };
  $("#gfiles").onchange = (e) => { const fs = [...e.target.files], kind = e.target.dataset.kind; e.target.value = ""; delete e.target.dataset.kind;
    if (fs.length) uploadMany(fs, kind).catch((err) => { callStatus(""); alert(err.message); }); };
  $("#gaudio").onchange = async (e) => {
    const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    try { const r = await api(`/api/p/${name}/musicup`, { method: "POST", body: f, timeout: 600000, headers: { "X-Filename": encodeURIComponent(f.name), "Content-Type": "application/octet-stream" } });
          await save({ music: { src: r.path, db: -18, duck: true } }); render(); } catch (err) { alert(err.message); }
  };
  window.addEventListener("resize", () => { if (!$("#gpv").hidden) sizePreview(); });
  renderSteps(); $("#gpage").replaceChildren(el("p", "muted", "Abrindo…"));        // never a blank screen while loading
  marcas = await api("/api/marcas").catch(() => []);
  await loadProjects();
  const [hn, hs] = decodeURIComponent(location.hash.slice(1)).split("/");
  const want = hn || store.get("cinex.project");
  if (want && projects.some((p) => p.name === want)) await openProject(want, STEPS.some((s) => s.id === hs) ? hs : null);
  else render();
  setInterval(poll, 1500);
}
init();
