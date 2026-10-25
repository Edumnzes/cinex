"""User asset bank: references per format, fonts, motions (animated overlays) and sound effects.

Lives OUTSIDE the git repo (licensed files can't be redistributed):  ~/reels-banco  (or env REELS_BANCO)
    referencias/<formato>/referencias.md   links + what to copy from each reference (one folder per format id)
    fontes/        *.ttf|*.otf  + fontes.json (optional index: familia, arquivo, licenca, uso)
    motions/<categoria>/  alpha video (.mov ProRes 4444 / .webm VP9), .gif, or a folder of PNGs  + motions.json (optional)
    sfx/<categoria>/      *.wav|*.mp3  (pop, whoosh, click, ding, riser, impact, flash, tick, error...)

Usage:
    python banco.py init                 # create the structure + templates (never overwrites)
    python banco.py status               # what is in the bank, what is missing (licences, SFX categories)
    python banco.py check                # every font loads, every motion decodes WITH transparency, every SFX reads
    python banco.py list fontes|motions|sfx|referencias
In code: reels_lib registers the bank fonts automatically (T(..., family="<familia>")); the Reel's
overlays=[dict(id="seta_curva", t0=3.2, cx=540, cy=700, w=360)] use motions; sfx=[(t, "pop", -12)] use sfx/pop/.
"""
import json, os, re, subprocess, sys
from pathlib import Path

BANCO = Path(os.environ.get("REELS_BANCO", Path.home() / "reels-banco"))
FORMATOS = ["fala_popups", "dicas_rapidas", "historia", "depoimento", "react", "clone", "frase_identificacao",
            "conteudo_legenda", "voiceover", "serie", "gancho_visual", "multitarefa", "motion_explicativo"]
SFX_CATS = ["pop", "whoosh", "click", "ding", "riser", "impact", "flash", "tick", "error"]
MOTION_CATS = ["setas", "sublinhados", "circulos", "stickers", "transicoes", "fundos", "icones"]
FONT_EXT, AUDIO_EXT = (".ttf", ".otf"), (".wav", ".mp3", ".ogg", ".m4a")
VIDEO_EXT = (".mov", ".webm", ".gif", ".mp4")

REF_TEMPLATE = """# Referências — {nome}

Cole aqui os vídeos que mostram como ESTE formato deve ficar. A skill lê este arquivo quando o formato é
escolhido e segue o padrão (não copia o conteúdo de ninguém — copia a estrutura e as decisões de edição).

| Link | Perfil | O que copiar | Observações |
|---|---|---|---|
| https://www.instagram.com/reel/... | @perfil | gancho / ritmo / texto na tela / motion / áudio / cor | o que NÃO copiar, duração, etc. |

## Padrões que se repetem (preencha ou peça para a skill preencher após analisar os links)
- Gancho (primeiros 3 s):
- Ritmo (troca de plano a cada ~ s):
- Texto na tela (fonte, tamanho, posição, cor):
- Motions usados:
- Efeitos sonoros:
- Duração típica:
- CTA:
"""
README = """# Banco da skill Cinex

Pasta lida pela skill `cinex` (fora do Git de propósito: arquivos licenciados não podem ser redistribuídos).

| Pasta | O que colocar | Como a skill usa |
|---|---|---|
| `referencias/<formato>/` | `referencias.md` com links e o que copiar; prints/vídeos opcionais | lida quando o formato é escolhido; vira o padrão do plano editorial |
| `fontes/` | `.ttf` / `.otf` + licença; opcional `fontes.json` | registradas automaticamente; a marca escolhe no `marca.json → fontes` |
| `motions/<categoria>/` | vídeo com transparência (`.mov` ProRes 4444 ou `.webm` VP9), `.gif` ou pasta de PNGs | sobrepostos no vídeo (`overlays=[...]`) |
| `sfx/<categoria>/` | `.wav` / `.mp3` (pop, whoosh, click, ding, riser, impact, flash, tick, error) | `sfx=[(t, "pop", -12)]`; varia entre os arquivos da categoria |

Verifique tudo com:  python ~/.claude/skills/cinex/scripts/banco.py check

## Licenças
Guarde junto de cada item a origem e a licença (arquivo `licenca.txt` na pasta ou campo `licenca` nos índices).
- Fontes: só com licença de uso em vídeo/comercial (Google Fonts/OFL é livre; Cocogoose, Fixture etc. exigem compra).
- Motion Array / Envato / Artlist: uso enquanto a assinatura permitir e conforme o registro de projeto de cada banco.
- Mixkit / Pixabay: uso comercial livre. Freesound: confira CC0 / CC-BY (crédito) / NC (não comercial — evitar).

## Motions que não abrem direto
- `.mogrt` / `.aep` (Premiere/After Effects): exporte do Adobe como **QuickTime ProRes 4444 com canal alfa** (.mov).
- Lottie (`.json`): exporte como `.webm` com transparência (LottieFiles → Download → WebM) ou GIF.
- Vídeo com fundo verde/preto (sem alfa): avise a skill — dá para usar chroma key / modo "screen", mas é um
  tratamento por arquivo.
"""


ENTRADA_TXT = """Coloque aqui os efeitos sonoros que você baixar (Pixabay, Mixkit, Motion Array...), com qualquer nome.
Depois peça ao Claude para organizar os sons, ou rode:
  python ~/.claude/skills/cinex/scripts/sfx_ingest.py --origem Pixabay
Cada som é classificado (click, pop, whoosh, ding, riser, impact, flash, tick, error), tem o silêncio
cortado, o volume igualado e vai para a pasta da categoria. Os originais ficam em _processados.
O que não der para classificar vai para sfx/_revisar.
"""


def _write(p, text):
    if p.exists(): return False
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8"); return True


def init():
    made = []
    if _write(BANCO / "README.md", README): made.append("README.md")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from formats import formats; nomes = {k: v["nome"] for k, v in formats().items()}
    except Exception: nomes = {}
    for f in FORMATOS:
        if _write(BANCO / "referencias" / f / "referencias.md", REF_TEMPLATE.format(nome=nomes.get(f, f))): made.append(f"referencias/{f}")
    (BANCO / "fontes").mkdir(parents=True, exist_ok=True)
    _write(BANCO / "fontes" / "fontes.json", json.dumps([{"familia": "exemplo", "arquivo": "Exemplo-Bold.ttf",
                                                           "licenca": "OFL / comprada / ...", "uso": "titulos | destaque | legenda"}],
                                                         ensure_ascii=False, indent=2))
    for c in MOTION_CATS: (BANCO / "motions" / c).mkdir(parents=True, exist_ok=True)
    _write(BANCO / "motions" / "motions.json", json.dumps([{"id": "exemplo_seta", "arquivo": "setas/seta_curva.webm",
                                                            "uso": "apontar para um detalhe", "licenca": "Motion Array",
                                                            "ancora": [0.5, 0.5]}], ensure_ascii=False, indent=2))
    for c in SFX_CATS: (BANCO / "sfx" / c).mkdir(parents=True, exist_ok=True)
    (BANCO / "sfx" / "_entrada").mkdir(parents=True, exist_ok=True)      # drop downloads here, then run sfx_ingest.py
    _write(BANCO / "sfx" / "_entrada" / "LEIA-ME.txt", ENTRADA_TXT)
    print("banco em", BANCO, "· criados:", ", ".join(made) or "nada (já existia)")


# ---------------------------------------------------------------- discovery
def fonts():
    """[{familia, path, licenca, uso}] — index entries first, then any other font file found."""
    d = BANCO / "fontes"; out, seen = [], set()
    if not d.exists(): return out
    idx = d / "fontes.json"
    if idx.exists():
        for e in json.loads(idx.read_text(encoding="utf-8")):
            p = d / e.get("arquivo", "")
            if p.is_file(): out.append(dict(e, path=str(p))); seen.add(p.resolve())
    for p in sorted(x for x in d.rglob("*") if x.suffix.lower() in FONT_EXT):
        if p.resolve() not in seen: out.append({"familia": re.sub(r"[^a-z0-9]+", "_", p.stem.lower()).strip("_"), "path": str(p)})
    return out


def register_fonts(FONTS, DEFAULT_W):
    """Called by reels_lib on import: adds every bank font as a family (absolute path, no variation axis)."""
    for f in fonts():
        fam = f["familia"]
        if fam not in FONTS: FONTS[fam] = f["path"]; DEFAULT_W[fam] = None


def motions():
    """{id: {path, kind, ...}} — kind: video | gif | png_seq."""
    d = BANCO / "motions"; out = {}
    if not d.exists(): return out
    idx = d / "motions.json"; meta = {}
    if idx.exists():
        for e in json.loads(idx.read_text(encoding="utf-8")):
            meta[(d / e.get("arquivo", "")).resolve()] = e
    for p in sorted(d.rglob("*")):
        kind = None
        if p.is_file() and p.suffix.lower() in VIDEO_EXT: kind = "gif" if p.suffix.lower() == ".gif" else "video"
        elif p.is_dir() and len(list(p.glob("*.png"))) >= 2: kind = "png_seq"
        if not kind: continue
        e = meta.get(p.resolve(), {}); mid = e.get("id") or re.sub(r"[^a-z0-9]+", "_", p.stem.lower()).strip("_")
        out[mid] = dict(e, id=mid, path=str(p), kind=kind, categoria=p.relative_to(d).parts[0] if len(p.relative_to(d).parts) > 1 else "")
    return out


def sfx():
    """{categoria: [paths]} from sfx/<cat>/ folders and sfx/<cat>_*.wav files."""
    d = BANCO / "sfx"; out = {}
    if not d.exists(): return out
    for p in sorted(d.rglob("*")):
        if p.suffix.lower() not in AUDIO_EXT or any(part.startswith("_") for part in p.relative_to(d).parts): continue   # _entrada, _revisar
        cat = p.parent.name if p.parent != d else re.split(r"[_\-\d]", p.stem.lower())[0]
        out.setdefault(cat, []).append(str(p))
    return out


# Useful length of each kind of sound in a reel (s). Files inside the range are preferred by the engine;
# longer ones stay in the bank ("longo") and are only used when nothing ideal exists, cut to SFX_CAP.
SFX_IDEAL = {"click": (0, .45), "pop": (0, .7), "ding": (.15, 1.7), "whoosh": (.25, 1.9), "impact": (.2, 3.0),
             "flash": (0, .7), "tick": (0, 2.2), "riser": (1.0, 4.6), "error": (.1, 1.6)}
SFX_CAP = {"click": .6, "pop": .9, "ding": 2.2, "whoosh": 2.4, "impact": 3.2, "flash": .9, "tick": 1.8, "riser": 4.5, "error": 1.8}


def sfx_index():
    """{absolute path: entry of sfx.json} written by sfx_ingest.py (duration, origin, licence...)."""
    p = BANCO / "sfx" / "sfx.json"
    if not p.exists(): return {}
    return {str((BANCO / "sfx" / e["arquivo"]).resolve()): e for e in json.loads(p.read_text(encoding="utf-8")) if e.get("arquivo")}


def sfx_use(cat, dur):
    lo, hi = SFX_IDEAL.get(cat, (0, 3)); return "ideal" if lo <= dur <= hi else ("longo" if dur > hi else "curto")


def sfx_file(name, t=0.0):
    """A file for SFX category `name`: prefers files of ideal length, and varies between them (by time) so
    repeats don't sound identical."""
    files = sfx().get(name, [])
    if not files: return None
    idx = sfx_index(); ideal = [f for f in files if idx.get(str(Path(f).resolve()), {}).get("uso", "ideal") == "ideal"]
    pool = ideal or files
    return Path(pool[int(t * 7) % len(pool)])


def referencias(fmt_id):
    p = BANCO / "referencias" / fmt_id / "referencias.md"
    if not p.exists(): return None
    txt = p.read_text(encoding="utf-8"); links = re.findall(r"https?://\S+", txt)
    links = [l.rstrip("|)") for l in links if "instagram.com/reel/..." not in l]
    return {"path": str(p), "links": links, "texto": txt}


# ---------------------------------------------------------------- checks
def _ffmpeg():
    import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()


def motion_has_alpha(m):
    """Decode one frame as RGBA and check that some pixels are transparent."""
    import numpy as np
    FF = _ffmpeg(); src = m["path"]; pre = []
    if m["kind"] == "png_seq":
        pngs = sorted(Path(src).glob("*.png")); src = str(pngs[0])
    elif src.lower().endswith(".webm"): pre = ["-c:v", "libvpx-vp9"]      # the native decoder drops VP9 alpha
    r = subprocess.run([FF, "-loglevel", "error", *pre, "-i", src, "-frames:v", "1", "-vf", "scale=64:-2", "-f", "rawvideo",
                        "-pix_fmt", "rgba", "-"], capture_output=True)
    if not r.stdout: return None
    a = np.frombuffer(r.stdout, np.uint8)[3::4]
    return bool((a < 250).mean() > .02)


def check():
    from PIL import ImageFont
    ok = True
    for f in fonts():
        try: ImageFont.truetype(f["path"], 40); print(f"  fonte OK   {f['familia']:22} {Path(f['path']).name}" + ("" if f.get("licenca") else "   (sem licença registrada)"))
        except Exception as e: ok = False; print(f"  fonte ERRO {f['familia']}: {e}")
    for mid, m in motions().items():
        al = motion_has_alpha(m)
        msg = "transparência OK" if al else ("SEM transparência (fundo opaco — exporte com alfa)" if al is False else "não abriu")
        if not al: ok = False
        print(f"  motion {'OK  ' if al else 'ERRO'} {mid:22} {m['kind']:8} {msg}")
    for cat, files in sfx().items():
        print(f"  sfx    OK   {cat:22} {len(files)} arquivo(s)")
    print("banco:", "tudo certo" if ok else "há itens para corrigir")
    return ok


def status():
    print("banco:", BANCO, "(não existe — rode: banco.py init)" if not BANCO.exists() else "")
    if not BANCO.exists(): return
    refs = {f: referencias(f) for f in FORMATOS}
    print("referências por formato:")
    for f, r in refs.items(): print(f"  {f:22} {len(r['links']) if r else 0} link(s)")
    fs = fonts(); print(f"fontes: {len(fs)} ·", ", ".join(x["familia"] for x in fs) or "-")
    ms = motions(); print(f"motions: {len(ms)} ·", ", ".join(ms) or "-")
    sx = sfx(); print("sfx:", ", ".join(f"{k}({len(v)})" for k, v in sx.items()) or "-")
    falta = [c for c in SFX_CATS if c not in sx]
    if falta: print("  categorias de SFX ainda vazias:", ", ".join(falta))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:] or ["status"]
    if a[0] == "init": init()
    elif a[0] == "status": status()
    elif a[0] == "check": sys.exit(0 if check() else 1)
    elif a[0] == "list":
        what = a[1] if len(a) > 1 else "motions"
        data = {"fontes": fonts(), "motions": motions(), "sfx": sfx(),
                "referencias": {f: referencias(f) and referencias(f)["links"] for f in FORMATOS}}[what]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else: print(__doc__)
