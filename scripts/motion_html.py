"""Motion elements rendered from HTML (HyperFrames + GSAP) as alpha video, composited by the engine as overlays.

Templates: motion_html/templates/<tipo>.html (sections <!--CSS--> <!--BODY--> <!--JS--> merged into _base.html).
Each element renders at its own size (frame width x element height, transparent), so the engine can still place it
away from the face (reels_lib overlays + slot()). Results are cached by content: same text/colour/duration -> no re-render.

    from motion_html import available, render
    path = render(m, FW, FH, accent="#FFD400", dur=3.2, n=1, total=3, cache=Path("~/reels/x/motion_cache"))

Environment (see motion_html/README.md): Node.js 22+, `npm install hyperframes` in CINEX_HF (default ~/cinex-hf),
`npx hyperframes browser ensure`, FFmpeg + FFprobe on PATH. Telemetry is always off.
"""
import hashlib, html, json, os, shutil, subprocess
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
TPL = HERE.parent / "motion_html" / "templates"
ASSETS = HERE.parent / "assets"
HF = Path(os.environ.get("CINEX_HF", Path.home() / "cinex-hf"))
CLI = HF / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
GSAP = next(iter(sorted((HF / "node_modules" / "hyperframes" / "dist" / "vendor" / "npm").glob("gsap@*/dist/gsap.min.js"))), None) \
    if (HF / "node_modules").exists() else None
WINGET = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
SIZES = {"gigante": 560, "titulo": 200, "topico": 340, "nome": 280, "citacao": 600, "frase": 640, "seguir": 240, "salvar": 240}
PREFER = {"gigante": 640, "titulo": 330, "topico": 480, "nome": 1110, "citacao": 520, "frase": 820, "seguir": 420, "salvar": 420}   # 9:16 scale
ICONS = {
    "seguir": '<svg viewBox="0 0 24 24" fill="none" stroke="#0b0b0b" stroke-width="3" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    "salvar": '<svg viewBox="0 0 24 24" fill="none" stroke="#0b0b0b" stroke-width="2.6" stroke-linejoin="round"><path d="M6 3h12v18l-6-4-6 4z"/></svg>',
}


def _env():
    e = dict(os.environ, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    if WINGET.exists(): e["PATH"] = str(WINGET) + os.pathsep + e.get("PATH", "")
    return e


def available():
    """HyperFrames installed + Node + ffprobe reachable."""
    if not (CLI.exists() and GSAP and shutil.which("node")): return False
    return bool(shutil.which("ffprobe", path=_env()["PATH"]))


def _sections(kind):
    s = (TPL / f"{'cta' if kind in ('seguir', 'salvar') else kind}.html").read_text(encoding="utf-8")
    part = lambda a, b: s.split(f"<!--{a}-->")[1].split(f"<!--{b}-->")[0] if b else s.split(f"<!--{a}-->")[1]
    return part("CSS", "BODY"), part("BODY", "JS"), part("JS", None)


def _words(text, hl=()):
    hl = {w.lower().strip(".,!?") for w in hl}
    out = []
    for w in text.split():
        cls = ' class="hl"' if w.lower().strip(".,!?") in hl else ""
        out.append(f'<span class="mask"><span{cls}>{html.escape(w)}</span></span>')
    return " ".join(out)


def build(m, FW, FH, accent, dur, n=0, total=0):
    """HTML of one element (also used by tests / previews)."""
    kind = m["type"]; s = min(FW, FH) / 1080; H = int(round(SIZES[kind] * s / 2) * 2)
    text, text2 = m.get("text", "") or "", m.get("text2", "") or ""
    if kind == "seguir": text = text or "Siga para mais"
    if kind == "salvar": text = text or "Salve para não esquecer"
    v = dict(DUR=f"{dur:.3f}", OUT=f"{max(.9, dur - .4):.3f}", TEXT=html.escape(text), TEXT2=html.escape(text2), N=str(n or 1),
             CHARS="".join(f"<span>{'&nbsp;' if ch == ' ' else html.escape(ch)}</span>" for ch in text.upper()),
             WORDS=_words(text, text2.replace(",", " ").split() if kind == "frase" else ()),
             WORDS_PLAIN=" ".join(f"<span>{html.escape(w)}</span>" for w in text.split()),
             AUTHOR=f'<div id="author">— {html.escape(text2)}</div>' if text2 else "",
             FROM=f"{100 * (n - 1) / total:.1f}" if total else "0", TO=f"{100 * n / total:.1f}" if total else "100",
             ICON=ICONS.get(kind, ""))
    css, body, js = (Template(x).safe_substitute(v) for x in _sections(kind))
    base = (TPL / "_base.html").read_text(encoding="utf-8")
    return Template(base).safe_substitute(W=FW, H=H, DUR=v["DUR"], OUT=v["OUT"], ACCENT=accent, SCALE=f"{s:.4f}",
                                          CSS=css, BODY=body, JS=js), H


def render(m, FW, FH, accent, dur, n=0, total=0, cache=None):
    """Render one element to <cache>/<hash>/out.mov (ProRes 4444 with alpha); cached by content."""
    page, H = build(m, FW, FH, accent, dur, n, total)
    key = hashlib.sha1((page + str(FW) + str(FH)).encode("utf-8")).hexdigest()[:16]
    job = Path(cache) / key; out = job / "out.mov"
    if out.exists() and out.stat().st_size > 0: return out, H
    (job / "fonts").mkdir(parents=True, exist_ok=True)
    for f in ("Montserrat.ttf", "SerifItalic.ttf"): shutil.copy2(ASSETS / f, job / "fonts" / f)
    shutil.copy2(GSAP, job / "gsap.min.js")
    (job / "index.html").write_text(page, encoding="utf-8")
    (job / "hyperframes.json").write_text(json.dumps({"paths": {"assets": "assets"}, "media": {"autoProxy": True}}), encoding="utf-8")
    (job / "meta.json").write_text(json.dumps({"id": key, "name": key}), encoding="utf-8")
    r = subprocess.run(["node", str(CLI), "render", str(job), "--format", "mov", "-o", str(out), "--fps", "30", "--quiet"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=_env(), cwd=str(job),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode or not out.exists():
        raise RuntimeError(f"HyperFrames falhou ({m['type']}): {(r.stderr or r.stdout)[-400:]}")
    return out, H
