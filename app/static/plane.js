"use strict";
// Cinex app — "Texto no cenário (3D)": mark a surface with 4 clicks on the preview and see the text in perspective.
// The quad is stored normalised to the SOURCE frame (m.quad, m.tmark), so the export can track it on the real video
// (scripts/plane_track.py). The preview undoes the CSS camera (object-position + zoom) of app.js camera().
// Loaded before app.js; uses its globals at call time.

let marking = null;          // { m, pts: [] } while the user clicks the 4 corners

function camState() {
  const v = $("#video"), box = $("#phone"); if (!v.videoWidth) return null;
  const bw = box.clientWidth, bh = box.clientHeight, sc = Math.max(bw / v.videoWidth, bh / v.videoHeight);
  const [ox, oy] = (v.style.objectPosition || "0px 0px").split(" ").map(parseFloat);
  const z = parseFloat((v.style.transform.match(/scale\(([\d.]+)\)/) || [0, 1])[1]);
  const [rx, ry] = (v.style.transformOrigin || `${bw / 2}px ${bh / 2}px`).split(" ").map(parseFloat);
  return { Sw: v.videoWidth * sc, Sh: v.videoHeight * sc, ox: ox || 0, oy: oy || 0, z, rx, ry };
}
function rawToBox(x, y, c) { const px = c.ox + x * c.Sw, py = c.oy + y * c.Sh; return [c.rx + (px - c.rx) * c.z, c.ry + (py - c.ry) * c.z]; }
function boxToRaw(bx, by, c) { const px = c.rx + (bx - c.rx) / c.z, py = c.ry + (by - c.ry) / c.z; return [(px - c.ox) / c.Sw, (py - c.oy) / c.Sh]; }

// CSS matrix3d mapping the rectangle (0,0)-(w,h) onto 4 points (clockwise from top-left): solve the 8-unknown homography
function rectToQuad(w, h, q) {
  const src = [[0, 0], [w, 0], [w, h], [0, h]], A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, v] = q[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  for (let c = 0; c < 8; c++) {                       // Gauss-Jordan with partial pivoting
    let p = c; for (let r = c + 1; r < 8; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
    [A[c], A[p]] = [A[p], A[c]]; [b[c], b[p]] = [b[p], b[c]];
    for (let r = 0; r < 8; r++) if (r !== c) { const f = A[r][c] / A[c][c]; for (let k = c; k < 8; k++) A[r][k] -= f * A[c][k]; b[r] -= f * b[c]; }
  }
  const s = b.map((v, i) => v / A[i][i]);
  return `matrix3d(${s[0]},${s[3]},0,${s[6]},${s[1]},${s[4]},0,${s[7]},0,0,1,0,${s[2]},${s[5]},0,1)`;
}

function startMarking(m) {
  if (!st) return; $("#video").pause(); marking = { m, pts: [] };
  $("#phone").classList.add("marking"); planeHint("Clique nos 4 cantos da superfície, começando pelo canto de cima à esquerda, em sentido horário.");
}
function planeHint(t) { const h = $("#planehint"); if (h) { h.textContent = t || ""; h.hidden = !t; } }

function bindPlane() {
  $("#phone").addEventListener("click", (e) => {
    if (!marking) return;
    e.stopPropagation(); e.preventDefault();
    const c = camState(); if (!c) return;
    const r = $("#phone").getBoundingClientRect(), [x, y] = boxToRaw(e.clientX - r.left, e.clientY - r.top, c);
    marking.pts.push([+x.toFixed(4), +y.toFixed(4)]);
    drawMarks();
    if (marking.pts.length === 4) {
      const m = marking.m; m.quad = marking.pts; m.tmark = +$("#video").currentTime.toFixed(2);
      marking = null; $("#phone").classList.remove("marking"); planeHint(""); renderFx(); fxSave();
    } else planeHint(`Canto ${marking.pts.length + 1} de 4…`);
  }, true);
}

function drawMarks() {
  const layer = $("#planemarks"), c = camState(); if (!layer || !c) return;
  layer.replaceChildren(...(marking ? marking.pts : []).map(([x, y]) => {
    const [bx, by] = rawToBox(x, y, c), d = document.createElement("i"); d.style.left = bx + "px"; d.style.top = by + "px"; return d;
  }));
}

function drawPlanes(t, list) {
  const layer = $("#planes"), c = camState(); if (!layer) return;
  if (!c) { layer.replaceChildren(); return; }
  const want = list.filter((m) => m.quad);
  while (layer.children.length > want.length) layer.lastChild.remove();
  want.forEach((m, i) => {
    let d = layer.children[i];
    if (!d) { d = document.createElement("div"); d.className = "planetxt"; layer.append(d); }
    const W = 1600, H = 480;                         // same flat sprite as motion_html "cenario"
    const txt = (m.text || "").toUpperCase();
    if (d.dataset.txt !== txt) {                     // fit to 94% of the sprite width, like the template's JS
      d.dataset.txt = txt; d.style.width = W + "px"; d.style.height = H + "px";
      d.replaceChildren(Object.assign(document.createElement("span"), { textContent: txt }));
      d.style.fontSize = "200px"; d.style.transform = "none";
      const w = d.firstChild.getBoundingClientRect().width || 1;
      d.style.fontSize = Math.min(200 * W * .94 / w, H * .78) + "px";
    }
    d.style.color = st.captions.accent;
    d.style.transform = rectToQuad(W, H, m.quad.map(([x, y]) => rawToBox(x, y, c)));
    d.style.opacity = Math.max(0, Math.min(1, (t - m.t0) / .3, (m.t1 - t) / .25)) * .85;
  });
}
