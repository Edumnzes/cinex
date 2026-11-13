"""Where finished files go and how they are named, so the delivery folder reads at a glance.

    python saida.py                      show the delivery folder
    python saida.py pasta "<folder>"     set it (saved in ~/reels/_config.json, per machine)
    python saida.py nome "Marca - Tema" [--formato vertical] [--seq 3] [--plataforma Instagram]   preview a name

Folder: "saida" in <CINEX_ROOT or ~/reels>/_config.json, else ~/Downloads.
Name (owner's rule entrega.nome, 2026-11-13):  "Marca - Tema - NN - Formato Plataforma"
        e.g. "Ynvest - Entrega Euroville - 04 - Reels 9x16 Instagram". NN is the publishing sequence of that brand:
        given with seq=, or the same number when this brand+theme was already delivered (a new version keeps it),
        or the brand's next free number in the delivery folder. Companions add a suffix: " - story 1.mp4".
"""
import json, os, re, sys
from pathlib import Path

FORMATO = {"vertical": "Reels 9x16", "feed": "Feed 4x5", "quadrado": "Quadrado 1x1", "horizontal": "Horizontal 16x9",
           "4x3": "4x3", "led": "Painel LED 512x384"}
PLATAFORMA = {"vertical": "Instagram", "feed": "Instagram", "quadrado": "Instagram", "horizontal": "YouTube",
              "4x3": "Telão", "led": "Feira"}


def _config():
    return Path(os.environ.get("CINEX_ROOT") or Path.home() / "reels") / "_config.json"


def pasta():
    try: p = json.loads(_config().read_text(encoding="utf-8")).get("saida")
    except (OSError, ValueError): p = None
    p = Path(p).expanduser() if p else Path.home() / "Downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _limpa(s):
    s = re.sub(r'[<>:"/\\|?*]+', "-", str(s)).replace("_", " ")
    return re.sub(r"\s+", " ", s).strip(" .-")


def sequencia(titulo, folder=None):
    """Publishing number for this brand: reuse the theme's number if it was delivered before, else the next free one."""
    folder = Path(folder) if folder else pasta(); titulo = _limpa(titulo)
    marca = titulo.split(" - ")[0]
    nums, same = [], None
    for f in folder.iterdir() if folder.exists() else []:
        m = re.match(r"(.+?) - (\d{2,3}) - ", f.stem)
        if not m: continue
        if m[1] == titulo: same = int(m[2])
        if m[1].split(" - ")[0] == marca: nums.append(int(m[2]))
    return same if same is not None else max(nums, default=0) + 1


def nome(titulo, formato="vertical", seq=None, plataforma=None, folder=None):
    """'Marca - Tema - NN - Formato Plataforma' (file stem, no extension)."""
    t = _limpa(titulo)
    n = seq if seq is not None else sequencia(t, folder)
    fmt = FORMATO.get(formato, formato) if formato else ""
    plat = plataforma if plataforma is not None else PLATAFORMA.get(formato, "")
    tail = " ".join(x for x in (fmt, plat) if x)
    return f"{t} - {int(n):02d}" + (f" - {tail}" if tail else "")


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
    if len(a) == 2 and a[0] == "pasta":
        c = _config(); c.parent.mkdir(parents=True, exist_ok=True)
        cfg = json.loads(c.read_text(encoding="utf-8")) if c.exists() else {}
        cfg["saida"] = str(Path(a[1]).expanduser()); c.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    elif a and a[0] == "nome":
        sys.stdout.reconfigure(encoding="utf-8")
        s = opt("--seq"); print(nome(a[1], opt("--formato", "vertical"), int(s) if s else None, opt("--plataforma"))); sys.exit()
    elif a: sys.exit(__doc__)
    print(pasta())
