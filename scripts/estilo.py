"""Style profiles from reference videos — copy editing DECISIONS (rhythm, look, caption style), never content.

    python estilo.py analisar <video> [<video> ...] --nome <id> [--formato fala_popups] [--link URL] [--sem-fala]
    python estilo.py list
    python estilo.py show <id>
    python estilo.py set <id> <regra> '<json>'      fill a rule after looking at the sheets (legenda, camera, motion, sfx, gancho, notas)
    python estilo.py criar <id> [--formato X] [--link URL ...]   profile from observation only (no files): rules by hand,
                                                    regras.cor.look_base names a built-in look until colour is measured

`analisar` measures what can be measured and writes ~/reels-banco/estilos/<id>/:
    perfil.json      medidas (cut rhythm, colour statistics, loudness, speech pace) + regras (rules the app applies)
    gancho_N.jpg     first 6 s of video N, a frame every 0.25 s (the hook: how fast, what text, which motion)
    folha_N.jpg      the whole video N, a frame per second (rhythm, recurring layouts)
    quadros_N.jpg    8 large frames (read the typography: font, weight, size, case, outline, position, colours)
Typography, motion types and the hook can't be measured reliably without OCR: Claude reads the sheets and fills
regras.legenda / camera / motion / sfx / gancho with `set`, then marks the profile revisado.
"""
import argparse, datetime, json, os, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, cv2, imageio_ffmpeg

HERE = Path(__file__).resolve().parent
BANCO = Path(os.environ.get("REELS_BANCO", Path.home() / "reels-banco"))
ROOT = BANCO / "estilos"
FF = imageio_ffmpeg.get_ffmpeg_exe()
RULES = ("legenda", "cor", "camera", "ritmo", "motion", "sfx", "gancho", "notas")


def _probe(src):
    e = subprocess.run([FF, "-hide_banner", "-i", str(src)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e).groups()
    w, hh = map(int, re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", e).groups())
    fps = re.search(r"([\d.]+) fps", e)
    return int(h) * 3600 + int(m) * 60 + float(s), w, hh, float(fps.group(1)) if fps else 30.0


def _frames(src, fps, w, h, ss=None, dur=None):
    cmd = [FF, "-loglevel", "error"] + (["-ss", str(ss)] if ss else []) + ["-i", str(src)] + (["-t", str(dur)] if dur else []) \
          + ["-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE); n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)


def cuts(src, vw, vh):
    """Shot changes from frame differences (same idea as detect_cuts.py), at 30 fps on a tiny frame."""
    w, h = (90, 160) if vh >= vw else (160, 90)
    prev, d = None, []
    for f in _frames(src, 30, w, h):
        g = f.mean(axis=2)
        if prev is not None: d.append(float(np.abs(g - prev).mean()))
        prev = g
    d = np.array(d); base = float(np.median(d)) if len(d) else 0
    out = [round((k + 1) / 30, 2) for k in range(len(d)) if d[k] > max(18, base * 4) and d[k] >= d[max(0, k - 3):k + 4].max()]
    return out


def colour(src, dur, vw, vh):
    """Colour statistics of ~24 frames: Lab mean/std (for a statistical look transfer), saturation, contrast,
    black/white levels, warmth, vignetting."""
    w, h = (270, 480) if vh >= vw else (480, 270)
    n = 24; fps = n / max(dur - .6, 1)
    labs, sats, lum = [], [], []
    vig = []
    for f in _frames(src, f"{fps:.4f}", w, h, ss=.3):
        lab = cv2.cvtColor(f, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
        labs.append(lab[::7]); sats.append(cv2.cvtColor(f, cv2.COLOR_RGB2HSV)[..., 1].mean() / 255)
        y = f @ np.float32([.299, .587, .114]) / 255; lum.append(y.ravel()[::7])
        c = y[h // 3:2 * h // 3, w // 3:2 * w // 3].mean(); k = y[:h // 6, :w // 6].mean() + y[-h // 6:, -w // 6:].mean()
        vig.append(k / 2 / max(c, 1e-3))
    lab = np.concatenate(labs); y = np.concatenate(lum)
    return dict(lab_mean=[round(float(v), 2) for v in lab.mean(0)], lab_std=[round(float(v), 2) for v in lab.std(0)],
                saturacao=round(float(np.mean(sats)), 3), contraste=round(float(y.std()), 3),
                preto=round(float(np.percentile(y, 2)), 3), meio=round(float(np.median(y)), 3), branco=round(float(np.percentile(y, 98)), 3),
                quente=round(float(lab[:, 2].mean() - 128), 2), vinheta=round(float(np.median(vig)), 3))


def loudness(src):
    e = subprocess.run([FF, "-hide_banner", "-i", str(src), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
    return float(m[-1]) if m else None


def speech(src):
    out = Path(tempfile.gettempdir()) / "cinex_estilo_words.json"
    r = subprocess.run([sys.executable, str(HERE / "transcribe.py"), str(src), str(out), "--model", "small"], capture_output=True)
    if r.returncode or not out.exists(): return None
    w = json.loads(out.read_text(encoding="utf-8"))
    if len(w) < 3: return dict(palavras=len(w))
    span = w[-1]["e"] - w[0]["s"]; gaps = [b["s"] - a["e"] for a, b in zip(w, w[1:])]
    return dict(palavras=len(w), palavras_por_s=round(len(w) / max(span, .1), 2), primeira_fala_s=round(w[0]["s"], 2),
                pausas_longas=sum(g > .5 for g in gaps), pausa_media=round(float(np.mean([g for g in gaps if g > .15] or [0])), 2))


def sheets(src, folder, i, dur, vw, vh):
    tw, th = (180, 320) if vh >= vw else (320, 180)
    def tile(frames, cols, path, step, t0=0.0):
        frames = list(frames)
        if not frames: return
        th, tw = frames[0].shape[:2]
        rows = -(-len(frames) // cols); sheet = np.zeros((rows * th, cols * tw, 3), np.uint8)
        for k, f in enumerate(frames):
            f = f.copy(); cv2.putText(f, f"{t0 + k * step:.2f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 0), 1, cv2.LINE_AA)
            sheet[(k // cols) * th:(k // cols + 1) * th, (k % cols) * tw:(k % cols + 1) * tw] = f
        cv2.imwrite(str(path), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    tile(_frames(src, 4, tw, th, dur=min(6, dur)), 8, folder / f"gancho_{i}.jpg", .25)
    tile(_frames(src, 1, tw, th), 10, folder / f"folha_{i}.jpg", 1.0)
    bw, bh = (360, 640) if vh >= vw else (640, 360)
    tile(_frames(src, f"{8 / max(dur, 1):.4f}", bw, bh), 4 if vh >= vw else 2, folder / f"quadros_{i}.jpg", dur / 8)


def summary(vals):
    v = np.array(vals, float)
    if not len(v): return {}
    return dict(media=round(float(v.mean()), 2), mediana=round(float(np.median(v)), 2), p10=round(float(np.percentile(v, 10)), 2),
                p90=round(float(np.percentile(v, 90)), 2), variacao=round(float(v.std() / max(v.mean(), 1e-3)), 2))


def css_preview(c):
    """Rough CSS filter so the app's live preview resembles the reference look (the export uses the Lab transfer)."""
    k = .6                                           # same partial strength as the export's transfer
    sat = 1 + k * (min(1.5, max(.6, c["saturacao"] / .32)) - 1); con = 1 + k * (min(1.4, max(.75, c["contraste"] / .22)) - 1)
    bri = 1 + k * (min(1.25, max(.75, c["meio"] / .45)) - 1); warm = max(0, min(.25, k * c["quente"] / 40))
    return f"saturate({sat:.2f}) contrast({con:.2f}) brightness({bri:.2f})" + (f" sepia({warm:.2f})" if warm > .02 else "")


def analyse(videos, nome, formato=None, link=None, fala=True):
    folder = ROOT / nome; folder.mkdir(parents=True, exist_ok=True)
    per, shots, hooks = [], [], []
    for i, v in enumerate(videos, 1):
        v = Path(v).expanduser().resolve(); dur, vw, vh, fps = _probe(v)
        print(f"[{i}/{len(videos)}] {v.name}: {dur:.1f} s {vw}x{vh}", flush=True)
        cs = cuts(v, vw, vh); bounds = [0.0] + cs + [dur]; sh = [round(b - a, 2) for a, b in zip(bounds, bounds[1:]) if b - a > .05]
        shots += sh; hooks.append(sum(c < 3 for c in cs))
        m = dict(arquivo=v.name, duracao=round(dur, 2), formato="9:16" if vh > vw else "16:9" if vw > vh else "1:1",
                 cortes=len(cs), cortes_por_10s=round(len(cs) / dur * 10, 2), cortes_nos_3s=hooks[-1], planos=summary(sh),
                 cor=colour(v, dur, vw, vh), lufs=loudness(v))
        if fala: m["fala"] = speech(v)
        sheets(v, folder, i, dur, vw, vh); per.append(m)
    cor = {k: (round(float(np.mean([p["cor"][k] for p in per])), 3) if not isinstance(per[0]["cor"][k], list)
               else [round(float(np.mean([p["cor"][k][j] for p in per])), 2) for j in range(3)]) for k in per[0]["cor"]}
    pf = folder / "perfil.json"
    old = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
    regras = old.get("regras") or {k: None for k in RULES}
    regras["ritmo"] = dict(plano_mediano_s=summary(shots).get("mediana"), plano_max_s=summary(shots).get("p90"),
                           cortes_por_10s=round(float(np.mean([p["cortes_por_10s"] for p in per])), 2),
                           cortes_nos_3s=round(float(np.mean(hooks)), 1), variacao=summary(shots).get("variacao"))
    regras["cor"] = dict(look="ref", lab_mean=cor["lab_mean"], lab_std=cor["lab_std"], forca=.6, css=css_preview(cor))
    perfil = dict(id=nome, criado=old.get("criado") or datetime.date.today().isoformat(), atualizado=datetime.date.today().isoformat(),
                  formato=formato or old.get("formato"), links=[l for l in [*(old.get("links") or []), link] if l],
                  medidas=dict(videos=per, cor=cor, planos=summary(shots)), regras=regras, revisado=False)
    pf.write_text(json.dumps(perfil, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"perfil: {pf}\nfolhas: {', '.join(sorted(p.name for p in folder.glob('*.jpg')))}")
    print("Falta ler as folhas e preencher: legenda, camera, motion, sfx, gancho, notas (estilo.py set).")
    return pf


def profiles():
    out = []
    for p in sorted(ROOT.glob("*/perfil.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8")); out.append(d)
        except Exception: pass
    return out


def load(nome):
    return json.loads((ROOT / nome / "perfil.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("args", nargs="*")
    ap.add_argument("--nome"); ap.add_argument("--formato"); ap.add_argument("--link"); ap.add_argument("--sem-fala", action="store_true")
    a = ap.parse_args()
    if a.cmd == "analisar":
        if not a.nome or not re.fullmatch(r"[a-z0-9_-]{1,40}", a.nome): sys.exit("--nome obrigatório: minúsculas, números, _ ou -")
        analyse(a.args, a.nome, a.formato, a.link, not a.sem_fala)
    elif a.cmd == "criar":
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", a.args[0]): sys.exit("id: minúsculas, números, _ ou -")
        f = ROOT / a.args[0]; f.mkdir(parents=True, exist_ok=True); p = f / "perfil.json"
        if p.exists(): sys.exit(f"{p} já existe")
        p.write_text(json.dumps(dict(id=a.args[0], criado=datetime.date.today().isoformat(), atualizado=datetime.date.today().isoformat(),
                                     formato=a.formato, links=[a.link] if a.link else [], medidas=dict(videos=[], cor=None, planos={}),
                                     regras={k: None for k in RULES}, revisado=False, origem="observação"), ensure_ascii=False, indent=1), encoding="utf-8")
        print(p)
    elif a.cmd == "list":
        for d in profiles():
            r = d["regras"]; print(f"{d['id']:20} {'revisado' if d.get('revisado') else 'medido  '} {len(d['medidas']['videos'])} vídeo(s) "
                                   f"· plano {(r.get('ritmo') or {}).get('plano_mediano_s', '?')} s · legenda {'ok' if r.get('legenda') else '—'}")
    elif a.cmd == "show": print(json.dumps(load(a.args[0]), ensure_ascii=False, indent=1))
    elif a.cmd == "set":
        nome, regra, val = a.args[0], a.args[1], json.loads(a.args[2])
        if regra not in RULES + ("revisado",): sys.exit(f"regra deve ser uma de {RULES}")
        d = load(nome)
        if regra == "revisado": d["revisado"] = bool(val)
        else: d["regras"][regra] = val
        (ROOT / nome / "perfil.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); print("ok")
    else: print(__doc__)
