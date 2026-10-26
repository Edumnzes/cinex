"""Brand performance: which formats and styles bring views, retention and clients — per Instagram profile.

Data lives with the brand profile (shared with legendas-instagram): ~/instagram-legendas/<handle>/
    desempenho.json   one entry per reel/post: metrics read from Instagram (Insights when logged in as the brand)
                      + tags (formato, estilo, gancho, legenda, motion, duracao...) used to compare
    desempenho.md     the latest report (ranking per tag, what to do more / less)

    python desempenho.py set <handle> '<json>'          add/update a reel by "codigo" (metrics and/or tags)
    python desempenho.py tag <handle> <codigo> '<json>' set tags of a reel
    python desempenho.py relatorio <handle>             ranking per tag -> desempenho.md (+ JSON on stdout with --json)
    python desempenho.py aplicar <handle>               write the winners into marca.json (formatos_preferidos, estilos_preferidos,
                                                        edicao.duracao_alvo_s) — only groups with >= 3 reels count

Metrics (any can be missing): views, alcance, nao_seg_pct, tempo_medio_s, duracao_s, retencao_3s_pct, curtidas,
comentarios, compart, salvos, seguiu, visitas. Retention = tempo_medio_s / duracao_s. Read-only collection: Claude
reads the grid and "Ver insights" in the browser with the user's own login; never types credentials.
"""
import datetime, json, statistics, sys
from pathlib import Path

ROOT = Path.home() / "instagram-legendas"
TAGS = ("formato", "estilo", "gancho", "legenda", "motion", "tema", "editado_cinex", "duracao", "postagem", "turbinado")


def folder(h):
    h = h.strip().lstrip("@").lower()
    if not h or "/" in h or "\\" in h or h.startswith("."): raise ValueError("arroba inválido")
    return ROOT / h


def load(h):
    p = folder(h) / "desempenho.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else dict(atualizado=None, reels=[])


def save(h, d):
    d["atualizado"] = datetime.date.today().isoformat()
    p = folder(h) / "desempenho.json"; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def upsert(h, entry):
    d = load(h); code = entry["codigo"]
    cur = next((r for r in d["reels"] if r["codigo"] == code), None)
    if cur:
        tags = {**cur.get("tags", {}), **entry.pop("tags", {})}; cur.update(entry); cur["tags"] = tags
    else:
        entry.setdefault("tags", {}); d["reels"].append(entry)
    save(h, d)


def duration_band(s):
    if not s: return None
    return "até 30 s" if s <= 30 else "30–60 s" if s <= 60 else "60–90 s" if s <= 90 else "90 s +"


def derived(r):
    v = r.get("views") or 0
    out = dict(views=v)
    if r.get("tempo_medio_s") and r.get("duracao_s"): out["retencao"] = min(1.0, r["tempo_medio_s"] / r["duracao_s"])
    if v and (r.get("curtidas") is not None or r.get("comentarios") is not None):    # public numbers (no login needed)
        out["engajamento_1k"] = 1000 * ((r.get("curtidas") or 0) + 3 * (r.get("comentarios") or 0)) / v
    if v and (r.get("compart") is not None or r.get("salvos") is not None):       # Insights (brand login)
        out["compart_salvos_1k"] = 1000 * ((r.get("compart") or 0) + (r.get("salvos") or 0)) / v
    if v and (r.get("visitas") is not None or r.get("seguiu") is not None):
        out["clientes_1k"] = 1000 * ((r.get("visitas") or 0) + 3 * (r.get("seguiu") or 0)) / v   # follows weigh more than visits
    if r.get("nao_seg_pct") is not None: out["nao_seg_pct"] = r["nao_seg_pct"]
    return out


def report(h):
    d = load(h); reels = [r for r in d["reels"] if r.get("views")]
    for r in reels: r.setdefault("tags", {})["duracao"] = r["tags"].get("duracao") or duration_band(r.get("duracao_s"))
    base = {k: statistics.median([derived(r)[k] for r in reels if k in derived(r)]) for k in ("views", "retencao", "engajamento_1k", "compart_salvos_1k", "clientes_1k")
            if any(k in derived(r) for r in reels)}
    groups = {}
    for r in reels:
        for k in TAGS:
            v = r["tags"].get(k)
            for val in (v if isinstance(v, list) else [v]):
                if val in (None, ""): continue
                groups.setdefault(k, {}).setdefault(str(val), []).append(r)
    ranking = {}
    for k, vals in groups.items():
        rows = []
        for val, rs in vals.items():
            m = {key: statistics.median([derived(x)[key] for x in rs if key in derived(x)]) for key in base if any(key in derived(x) for x in rs)}
            # score: each metric relative to the profile's median. Followers (+ profile visits) and shares/saves weigh most:
            # they bring clients; views and retention still count, likes least (owner's rule, 2026-10-26)
            w = dict(clientes_1k=.35, compart_salvos_1k=.30, views=.15, retencao=.15, engajamento_1k=.05)
            sc = sum(w[key] * (m[key] / base[key] if base.get(key) else 1) for key in m) / sum(w[key] for key in m) if m else 0
            rows.append(dict(valor=val, n=len(rs), score=round(sc, 2), **{key: round(x, 3 if key == "retencao" else 1) for key, x in m.items()}))
        ranking[k] = sorted(rows, key=lambda x: -x["score"])
    best = [r for r in sorted(reels, key=lambda r: -derived(r)["views"])[:5]]
    out = dict(handle=folder(h).name, atualizado=d.get("atualizado"), reels=len(reels), mediana=base, ranking=ranking,
               melhores=[dict(codigo=r["codigo"], titulo=r.get("titulo"), url=r.get("url"), **derived(r)) for r in best])
    write_md(h, out)
    return out


def write_md(h, rep):
    L = [f"# Desempenho — @{rep['handle']}", "",
         f"_Atualizado em {rep['atualizado']} · {rep['reels']} publicações com números · mediana do perfil: "
         + ", ".join(f"{k} {v:.2f}" if k == "retencao" else f"{k} {v:.1f}" for k, v in rep["mediana"].items()) + "_", "",
         "Score = média ponderada em relação à mediana do perfil (1,00 = igual; seguidores e compartilhamentos pesam mais; depois views e retenção).", ""]
    for k, rows in rep["ranking"].items():
        L += [f"## Por {k}", "", "| Valor | n | Score | Views | Retenção | Engaj./1k | Compart.+salv./1k | Clientes/1k |", "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['valor']} | {r['n']} | {r['score']:.2f} | {r.get('views', '—')} | "
                     f"{(str(round(100 * r['retencao'])) + '%') if 'retencao' in r else '—'} | {r.get('engajamento_1k', '—')} | {r.get('compart_salvos_1k', '—')} | {r.get('clientes_1k', '—')} |")
        L.append("")
    (folder(h) / "desempenho.md").write_text("\n".join(L), encoding="utf-8")


def apply(h):
    rep = report(h); p = folder(h) / "marca.json"
    m = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    good = lambda k: [r["valor"] for r in rep["ranking"].get(k, []) if r["n"] >= 3 and r["score"] >= 1.0]
    if good("formato"): m["formatos_preferidos"] = good("formato")
    if good("estilo"): m["estilos_preferidos"] = good("estilo")
    band = next(iter(good("duracao")), None)
    if band:
        m.setdefault("edicao", {})["duracao_alvo_s"] = {"até 30 s": [15, 30], "30–60 s": [30, 60], "60–90 s": [45, 90], "90 s +": [60, 120]}[band]
    m["updated"] = datetime.date.today().isoformat(); m.setdefault("handle", folder(h).name)
    p.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(formatos_preferidos=m.get("formatos_preferidos"), estilos_preferidos=m.get("estilos_preferidos"),
                duracao_alvo_s=m.get("edicao", {}).get("duracao_alvo_s"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "set": upsert(args[0], json.loads(args[1])); print("ok")
    elif cmd == "tag": upsert(args[0], dict(codigo=args[1], tags=json.loads(args[2]))); print("ok")
    elif cmd == "relatorio":
        r = report(args[0])
        if "--json" in args: print(json.dumps(r, ensure_ascii=False, indent=1))
        else: print((folder(args[0]) / "desempenho.md").read_text(encoding="utf-8"))
    elif cmd == "aplicar": print(json.dumps(apply(args[0]), ensure_ascii=False))
    else: print(__doc__)
