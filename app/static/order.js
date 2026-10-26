"use strict";
// Cinex app — phrase reordering. `st.order` holds kept segment ids in PLAY order (scripts/app_project.play_order
// does the same fallback on export). A "phrase" is a run of kept clips separated only by short cut pauses,
// so reordering moves whole phrases, not the fragments the pause cut leaves behind.

let playIdx = -1;                    // index in `kept` (play order) of the clip being played

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
const isReordered = () => { const a = playOrder().map((g) => g.id), b = st.segments.filter((g) => g.keep).map((g) => g.id); return a.join() !== b.join(); };

function phrases() {
  const list = playOrder(), out = [];
  for (const g of list) {
    const cur = out.at(-1), last = cur && cur.at(-1);
    // same phrase: the next kept clip in the SOURCE, with only cut pauses (< 1.2 s) in between
    const gap = last ? st.segments.filter((x) => x.s >= last.e - 0.001 && x.e <= g.s + 0.001) : [];
    const joins = last && g.s >= last.e - 0.001 && gap.every((x) => !x.keep && x.reason === "pausa") && g.s - last.e < 1.2;
    joins ? cur.push(g) : out.push([g]);
  }
  return out;
}

function setOrder(ph) {
  st.order = ph.flat().map((g) => g.id);
  buildGroups(); renderTimeline(); renderDur(); save({ order: st.order });
}

function renderOrder() {
  const box = $("#orderlist"); if (!box || !st) return;
  const ph = phrases(), locked = st.cut_locked, origIdx = new Map(phrasesRawFirst().map((id, i) => [id, i]));
  $("#orderreset").disabled = locked || !isReordered();
  box.replaceChildren(...ph.map((p, i) => {
    const r = document.createElement("div"); r.className = "orow" + (origIdx.get(p[0].id) !== i ? " moved" : "");
    r.draggable = !locked; r.dataset.i = i;
    const grip = document.createElement("span"); grip.className = "ograb"; grip.textContent = "⋮⋮";
    const num = document.createElement("b"); num.textContent = i + 1;
    const txt = document.createElement("span"); txt.className = "otext";
    txt.textContent = p.map((g) => g.text).filter(Boolean).join(" ") || "(sem fala)";
    const dur = document.createElement("small"); dur.className = "muted"; dur.textContent = p.reduce((a, g) => a + g.e - g.s, 0).toFixed(1) + " s";
    const btns = document.createElement("span"); btns.className = "obtns";
    const mk = (label, title, fn, dis) => { const b = document.createElement("button"); b.className = "icon"; b.textContent = label; b.title = title;
      b.disabled = locked || dis; b.onclick = (e) => { e.stopPropagation(); fn(); }; return b; };
    btns.append(mk("⇤", "Abrir com esta frase (cold open)", () => setOrder([p, ...ph.filter((x) => x !== p)]), i === 0),
                mk("↑", "Subir", () => { const q = [...ph]; [q[i - 1], q[i]] = [q[i], q[i - 1]]; setOrder(q); }, i === 0),
                mk("↓", "Descer", () => { const q = [...ph]; [q[i + 1], q[i]] = [q[i], q[i + 1]]; setOrder(q); }, i === ph.length - 1));
    r.append(grip, num, txt, dur, btns);
    r.onclick = () => { $("#video").currentTime = p[0].s + 0.01; };
    r.ondragstart = (e) => { e.dataTransfer.setData("text/plain", String(i)); r.classList.add("dragging"); };
    r.ondragend = () => r.classList.remove("dragging");
    r.ondragover = (e) => { e.preventDefault(); r.classList.add("over"); };
    r.ondragleave = () => r.classList.remove("over");
    r.ondrop = (e) => {
      e.preventDefault(); r.classList.remove("over");
      const from = +e.dataTransfer.getData("text/plain"); if (from === i || Number.isNaN(from)) return;
      const q = [...ph]; const [m] = q.splice(from, 1); q.splice(i, 0, m); setOrder(q);
    };
    return r;
  }));
}

function phrasesRawFirst() {          // first clip id of each phrase in the ORIGINAL order (to flag moved ones)
  const was = st.order; st.order = []; const ids = phrases().map((p) => p[0].id); st.order = was; return ids;
}

function phraseNumber() {             // segment id -> phrase number in play order (for the V1 badges)
  const m = new Map(); phrases().forEach((p, i) => p.forEach((g) => m.set(g.id, i + 1))); return m;
}

// playback in play order: at the end of a clip jump to the next one in the order unless it continues seamlessly
function followOrder(v) {
  const t = v.currentTime, i = kept.findIndex((g) => t >= g.s - 0.02 && t < g.e);
  if (i >= 0) {
    playIdx = i;
    const g = kept[i], nx = kept[i + 1];
    if (t >= g.e - 0.035) { if (!nx) v.pause(); else if (Math.abs(nx.s - g.e) > 0.01) v.currentTime = nx.s; }
    return;
  }
  const nx = kept[playIdx + 1] || kept.find((g) => g.s > t);     // in a removed stretch
  if (nx) { v.currentTime = nx.s; playIdx = kept.indexOf(nx); } else v.pause();
}
