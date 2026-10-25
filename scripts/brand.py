"""Brand profile shared with the legendas-instagram skill.

One folder per Instagram handle:  ~/instagram-legendas/<handle>/
    perfil.md     business, audience, voice, insights        (written by either skill)
    video.md      Reels analysis + editing direction           (cinex)
    marca.json    machine-readable defaults for project.py     (cinex)
    historico.md  captions delivered                           (legendas-instagram)
    videos.md     reels delivered                              (cinex)

Usage (CLI):
    python brand.py list                    # handles that already have a profile
    python brand.py show <handle>           # which files exist + marca.json
    python brand.py init <handle>           # create marca.json from the template (keeps existing)
    python brand.py log <handle> "<line>"   # append a delivered reel to videos.md
In project.py:
    from brand import load_brand
    B = load_brand("ynvestsolar")           # dict with every key of the template filled in
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
    elif cmd == "log":
        print(log(args[0], " ".join(args[1:])))
    else:
        print(__doc__)
