"""Brand profile shared with the legendas-instagram skill.

One folder per Instagram handle:  ~/instagram-legendas/<handle>/
    perfil.md     business, audience, voice, insights        (written by either skill)
    video.md      Reels analysis + editing direction           (cinex)
    marca.json    machine-readable defaults for project.py     (cinex)
    historico.md  captions delivered                           (legendas-instagram)
    videos.md     reels delivered                              (cinex)
    referencias.json + referencias/   niche references: links and video files (cinex app)
    desempenho.json / desempenho.md   performance per reel and per style (desempenho.py)

Usage (CLI):
    python brand.py list                    # handles that already have a profile
    python brand.py show <handle>           # which files exist + marca.json
    python brand.py init <handle>           # create marca.json from the template (keeps existing)
    python brand.py log <handle> "<line>"   # append a delivered reel to videos.md
    python brand.py refs <handle>           # niche references (links and videos) of this brand
In project.py:
    from brand import load_brand
    B = load_brand("suamarca")              # dict with every key of the template filled in
"""
import json, sys, datetime
from pathlib import Path

ROOT = Path.home() / "instagram-legendas"
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "marca_template.json"
FILES = ("perfil.md", "video.md", "marca.json", "historico.md", "videos.md")


def norm(handle):
    return handle.strip().lstrip("@").lower()


def folder(handle):
    return ROOT / norm(handle)


def status(handle):
    d = folder(handle)
    return {f: (d / f).exists() for f in FILES}


def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_brand(handle):
    """marca.json merged over the template, so missing keys always have a default."""
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    p = folder(handle) / "marca.json"
    data = _merge(base, json.loads(p.read_text(encoding="utf-8"))) if p.exists() else base
    data["handle"] = data.get("handle") or norm(handle)
    return data


def rgba(hex_or_list, a=255):
    """'#F2B21E' or [242,178,30] -> (r, g, b, a) for reels_lib colours."""
    if isinstance(hex_or_list, (list, tuple)): return tuple(hex_or_list[:3]) + (a,)
    h = hex_or_list.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def init(handle):
    d = folder(handle); d.mkdir(parents=True, exist_ok=True)
    p = d / "marca.json"
    if not p.exists():
        data = json.loads(TEMPLATE.read_text(encoding="utf-8")); data["handle"] = norm(handle)
        data["updated"] = datetime.date.today().isoformat()
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# fields the app's profile form may change: (path in marca.json, kind, max length)
EDITABLE = {"nome": ("nome", str, 80), "descricao": ("descricao", str, 600), "publico": ("publico", str, 400),
            "cta": (("cta", "principal"), str, 120), "contato": (("cta", "contato"), str, 160),
            "destaque": (("cores", "destaque"), "color", 7), "secundaria": (("cores", "secundaria"), "color", 7),
            "legenda": (("edicao", "caption_style"), ("hormozi", "minimal", "cinematic"), 12),
            "termos": ("transcricao_termos", list, 40), "keywords": ("keywords", list, 40)}


def save(handle, fields):
    """Create the profile if needed and apply the form fields (validated against EDITABLE)."""
    import re
    p = init(handle); data = json.loads(p.read_text(encoding="utf-8"))
    for k, v in fields.items():
        if k not in EDITABLE: continue
        path, kind, n = EDITABLE[k]
        if kind is str: v = str(v).strip()[:n]
        elif kind == "color":
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(v)): raise ValueError(f"cor inválida: {v}")
            v = str(v).upper()
        elif kind is list:
            v = [str(x).strip()[:60] for x in (v if isinstance(v, list) else str(v).split(",")) if str(x).strip()][:n]
        elif v not in kind: raise ValueError(f"valor inválido para {k}")
        if isinstance(path, tuple):
            data.setdefault(path[0], {})[path[1]] = v
        else: data[path] = v
    data["updated"] = datetime.date.today().isoformat()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_brand(handle)


REF_EXT = (".mp4", ".mov", ".m4v", ".webm")


def refs(handle):
    """Niche references of this brand: [{id, tipo: link|video, url|arquivo, nota, adicionado, analisado}].
    Video files live in <brand>/referencias/; they are analysed together into the style profile nicho_<handle>."""
    p = folder(handle) / "referencias.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _save_refs(handle, items):
    d = folder(handle); d.mkdir(parents=True, exist_ok=True)
    (d / "referencias.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def add_ref(handle, tipo, valor, nota=""):
    items = refs(handle); nid = max((r["id"] for r in items), default=0) + 1
    e = dict(id=nid, tipo=tipo, nota=nota, adicionado=datetime.date.today().isoformat(), analisado=False)
    e["url" if tipo == "link" else "arquivo"] = valor
    items.append(e); _save_refs(handle, items); return e


def remove_ref(handle, rid):
    items = refs(handle); keep = [r for r in items if r["id"] != rid]
    for r in items:
        if r["id"] == rid and r["tipo"] == "video":
            f = folder(handle) / "referencias" / r["arquivo"]
            if f.exists(): f.rename(f.with_name("_removido_" + f.name))   # kept on disk, out of the analysis
    _save_refs(handle, keep)


def log(handle, line):
    p = folder(handle) / "videos.md"
    if not p.exists(): p.write_text("# Reels entregues\n\n", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- {datetime.date.today().isoformat()} · {line}\n")
    return p


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("list", [])
    if cmd == "list":
        hs = sorted(p.name for p in ROOT.iterdir() if p.is_dir()) if ROOT.exists() else []
        for h in hs: print(h, " ".join(f for f, ok in status(h).items() if ok))
        if not hs: print("(nenhum perfil em", ROOT, ")")
    elif cmd == "show":
        h = args[0]; print("pasta:", folder(h))
        for f, ok in status(h).items(): print(f"  {'OK ' if ok else '-- '} {f}")
        print(json.dumps(load_brand(h), ensure_ascii=False, indent=2))
    elif cmd == "init":
        print(init(args[0]))
    elif cmd == "refs":
        for r in refs(args[0]): print(r)
    elif cmd == "log":
        print(log(args[0], " ".join(args[1:])))
    else:
        print(__doc__)
