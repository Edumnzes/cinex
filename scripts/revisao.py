"""Review of an app project for the "AI look" — runs on the project state, no export needed.

    python revisao.py <projeto> [--estilo <id>] [--quadros]

Automatic edits give themselves away by regularity and sameness: every shot the same length, sounds and zooms on
a beat, the same animation over and over, captions always the same size, an effect on every cut. This compares
the edit with editing that was done by people (the style profile chosen in the app, from estilo.py) and with
the editing manual (references/manual-edicao.md), and writes ~/reels/<projeto>/revisao.json:
    {"itens": [{"nivel": "alto|medio|ok", "area": ..., "texto": ..., "sugestao": ...}], "medidas": {...}}
--quadros: if the project has an exported final.mp4, also writes revisao_quadros.jpg (a frame every 0.5 s of the
first 8 s, then every 2 s) for Claude to look at — the things numbers can't see (text over a face, cheap motion).
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import app_project as P  # noqa: E402


def cv(v):
    v = np.array(v, float); return float(v.std() / v.mean()) if len(v) > 2 and v.mean() > 0 else None


def caption_groups(st, kept, words):
    c = st["captions"]; toks = []
    for g in kept:
        for w in P.words_in(words, g["s"], g["e"]): toks.append(w)
    groups, cur = [], []
    for w in toks:
        if cur and (len(cur) >= c["words"] or cur[-1]["w"][-1:] in ",.?!" or w["s"] - cur[-1]["e"] > .4): groups.append(cur); cur = []
        cur.append(w)
    if cur: groups.append(cur)
    return groups


def review(name, estilo_id=None):
    st = P.load(name); d = P.folder(name)
    kept = P.play_order(st); total = sum(g["e"] - g["s"] for g in kept)
    words = json.loads((d / "words_raw.json").read_text(encoding="utf-8"))
    estilo_id = estilo_id or st.get("estilo")
    ref = None
    if estilo_id:
        import estilo
        try: ref = estilo.load(estilo_id)
        except FileNotFoundError: ref = None
    items = []
    add = lambda nivel, area, texto, sugestao="": items.append(dict(nivel=nivel, area=area, texto=texto, sugestao=sugestao))

    # ---- rhythm: shots are the stretches between visible changes; jump cuts inside a phrase count as cuts
    shots = [g["e"] - g["s"] for g in kept]
    m = dict(duracao_s=round(total, 1), cortes=len(kept) - 1, plano_mediano_s=round(float(np.median(shots)), 2) if shots else 0,
             variacao_planos=round(cv(shots) or 0, 2))
    if cv(shots) is not None and cv(shots) < .3:
        add("medio", "ritmo", f"Os cortes têm quase todos a mesma duração (variação {cv(shots):.2f}). Ritmo de máquina.",
            "Deixe planos de ênfase mais longos e acelere nos trechos de lista ou de contexto.")
    if ref:
        r = ref["regras"]["ritmo"]; mr = r.get("plano_mediano_s")
        if mr and m["plano_mediano_s"] > mr * 1.8:
            add("medio", "ritmo", f"Planos bem mais longos que a referência ({m['plano_mediano_s']} s × {mr} s).",
                "Corte mais cedo: tire redundâncias ou use mudança de enquadramento.")
        elif mr and m["plano_mediano_s"] < mr * .5:
            add("medio", "ritmo", f"Planos bem mais curtos que a referência ({m['plano_mediano_s']} s × {mr} s).",
                "Junte trechos: cortes rápidos demais prejudicam a compreensão.")
    tgt = st.get("duration_target")
    if total > 90: add("medio", "duração", f"{total:.0f} s de vídeo.", "Para Reels, procure o essencial; acima de 60–90 s a retenção cai.")

    # ---- motion: amount, sameness, beat
    ms = sorted(st.get("motions", []), key=lambda x: x["t0"])
    cut_t = [P.raw_to_cut(x["t0"], kept) for x in ms]
    per_min = len(ms) / max(total / 60, .1)
    m.update(motions=len(ms), motions_por_min=round(per_min, 1))
    if per_min > 8: add("alto", "motion", f"{len(ms)} elementos ({per_min:.0f} por minuto): tela carregada.",
                        "Mantenha só os que explicam, provam, situam ou chamam para ação.")
    types = [x["type"] for x in ms]
    run = max((len(list(g)) for _, g in __import__("itertools").groupby(types)), default=0)
    if run >= 3: add("medio", "motion", f"{run} elementos iguais em sequência ({types[0] if len(set(types)) == 1 else 'mesmo tipo'}).",
                     "Alterne o tipo ou junte as ideias num só elemento (ex.: tópicos numerados com progresso).")
    gaps = np.diff(cut_t) if len(cut_t) > 2 else []
    if len(gaps) >= 3 and cv(gaps) is not None and cv(gaps) < .25:
        add("medio", "motion", "Os elementos entram em intervalos regulares, como um metrônomo.",
            "Faça cada elemento entrar na palavra que ele ilustra, não a cada X segundos.")
    if ms and sum(1 for x in ms if x.get("sfx")) == len(ms) and len(ms) >= 3:
        add("medio", "som", "Todo elemento de motion tem som.", "Som só nos eventos-chave: gancho, card principal, prova, CTA.")

    # ---- sound effects: density (manual §5) and regularity
    ev = sorted([P.raw_to_cut(s["t"], kept) for s in st.get("sfx", []) if any(g["s"] <= s["t"] < g["e"] for g in kept)]
                + [P.raw_to_cut(x["t0"], kept) for x in ms if x.get("sfx")])
    worst = max((sum(1 for y in ev if t <= y < t + 10) for t in ev), default=0)
    m.update(sons=len(ev), pior_janela_10s=worst)
    if worst > 2: add("alto", "som", f"{worst} sons em 10 s.", "O manual pede no máximo ~2 a cada 10 s.")
    if len(ev) >= 4 and cv(np.diff(ev)) is not None and cv(np.diff(ev)) < .25:
        add("medio", "som", "Sons em intervalos regulares.", "Sons marcam eventos, não um ritmo fixo.")

    # ---- captions
    c = st["captions"]; groups = caption_groups(st, kept, words)
    lens = [len(g) for g in groups]
    m.update(legendas=len(groups), palavras_por_legenda=round(float(np.mean(lens)), 1) if lens else 0)
    if c["enabled"] and c["words"] == 1:
        add("medio", "legenda", "Uma palavra por vez em todo o vídeo.", "Cansa e parece automático: use grupos de 2 a 4 palavras.")
    if c["enabled"] and not st.get("keywords"):
        add("ok" if c["upper"] else "medio", "legenda", "Nenhuma palavra destacada.",
            "Destaque só o que ajuda a entender (números, o problema, o benefício).")
    if ref and ref["regras"].get("legenda"):
        rl = ref["regras"]["legenda"]
        diff = [k for k in ("upper", "words", "lines") if k in rl and rl[k] != c.get(k)]
        if diff: add("medio", "legenda", f"Legenda diferente da referência em: {', '.join(diff)}.", "Aplique o estilo da referência no app.")

    # ---- camera / colour
    cam = st.get("camera", {}); col = st.get("color", {})
    if cam.get("zoom", 1) >= 1.2: add("medio", "câmera", f"Zoom base de {cam['zoom']:.0%}.", "Acima de ~110 % a imagem perde nitidez e fica apertada.")
    if col.get("look") in ("teal_orange", "moody") and not ref:
        add("ok", "cor", f"Look {col['look']} escolhido sem referência.", "Confira se combina com a marca; looks fortes denunciam filtro.")

    # ---- structure (manual §2)
    if ms and ms[-1]["type"] in ("seguir", "salvar") and len(ms) > 1 and P.raw_to_cut(ms[-1]["t0"], kept) < total * .5:
        add("alto", "estrutura", "A chamada para ação aparece antes da metade do vídeo.", "CTA só depois de o benefício estar claro.")
    first = kept[0] if kept else None
    if first and not P.words_in(words, first["s"], first["e"]):
        add("medio", "gancho", "O vídeo abre sem fala.", "Os primeiros segundos precisam de um gancho: promessa, problema ou dado.")

    if not items: add("ok", "geral", "Nada com cara de edição automática nas medidas.", "Confira os quadros: é onde o olho humano pega o resto.")
    out = dict(projeto=name, estilo=estilo_id, medidas=m, itens=items)
    P._write_json(d / "revisao.json", out)
    return out


def frames(name):
    d = P.folder(name); f = d / "final.mp4"
    if not f.exists(): return None
    ff = P._ff(); out = d / "revisao_quadros.jpg"
    dur = P.duration(f)
    sel = "+".join([f"lt(t\\,8)*not(mod(n\\,15))", f"gte(t\\,8)*not(mod(n\\,60))"])
    subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(f), "-vf", f"select='{sel}',scale=180:-2,tile=10x{max(2, int((16 + (dur - 8) / 2) // 10 + 1))}",
                    "-frames:v", "1", "-vsync", "0", str(out)], check=True)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(); ap.add_argument("projeto"); ap.add_argument("--estilo"); ap.add_argument("--quadros", action="store_true")
    a = ap.parse_args()
    r = review(a.projeto, a.estilo)
    print(json.dumps(r["medidas"], ensure_ascii=False))
    for it in r["itens"]: print(f"  [{it['nivel']:5}] {it['area']:10} {it['texto']}  → {it['sugestao']}")
    if a.quadros:
        p = frames(a.projeto); print("quadros:", p or "sem final.mp4 (exporte para a revisão visual)")
