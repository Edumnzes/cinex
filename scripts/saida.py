"""Where finished files go and how they are named, so the delivery folder reads at a glance.

    python saida.py                      show the delivery folder
    python saida.py pasta "<folder>"     set it (saved in ~/reels/_config.json, per machine)

Folder: "saida" in <CINEX_ROOT or ~/reels>/_config.json, else ~/Downloads.
Name:   "AAAA-MM-DD Marca - Tema (Formato)", e.g. "2026-11-06 Ynvest - Entrega Euroville (Reels 9x16)".
        The date sorts the folder by production day; companions share the name: " - story 1.mp4".
"""
import datetime, json, os, re, sys
from pathlib import Path

FORMATO = {"vertical": "Reels 9x16", "feed": "Feed 4x5", "quadrado": "Quadrado 1x1", "horizontal": "Horizontal 16x9",
           "4x3": "4x3", "led": "Painel LED 512x384"}


def _config():
    return Path(os.environ.get("CINEX_ROOT") or Path.home() / "reels") / "_config.json"


def pasta():
    try: p = json.loads(_config().read_text(encoding="utf-8")).get("saida")
    except (OSError, ValueError): p = None
    p = Path(p).expanduser() if p else Path.home() / "Downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def nome(titulo, formato="vertical", data=None):
    """Readable file stem: date first (unless the title already starts with one), the title, the format in brackets."""
    t = re.sub(r'[<>:"/\\|?*]+', "-", str(titulo)).replace("_", " ")
    t = re.sub(r"\s+", " ", t).strip(" .-")
    if not re.match(r"\d{4}-\d{2}-\d{2} ", t): t = f"{data or datetime.date.today().isoformat()} {t}"
    return f"{t} ({FORMATO.get(formato, formato)})" if formato else t


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "pasta":
        c = _config(); c.parent.mkdir(parents=True, exist_ok=True)
        cfg = json.loads(c.read_text(encoding="utf-8")) if c.exists() else {}
        cfg["saida"] = str(Path(sys.argv[2]).expanduser()); c.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    elif len(sys.argv) != 1: sys.exit(__doc__)
    print(pasta())
