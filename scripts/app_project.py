"""Cinex app projects: the state shared by the local app (app/server.py) and Claude Code.

One folder per video in ~/reels/<name>/ with:
    cinex.json     segments (keep / cut + reason), caption settings, chat, rev   <- the shared state
    preview.mp4    light H.264 proxy the browser can play (phones record HEVC .MOV)
    words_raw.json transcription of the source (transcribe.py)
    waveform.json  audio peaks for the timeline
    prep.json / export.json   progress of the background jobs

Claude Code is the brain: it reads the state, answers the chat and edits the cut. CLI:
    python app_project.py new <video> [--name X] [--prompt "brand terms"]   analyse + propose the cut
    python app_project.py list
    python app_project.py show <name>                    segments with text, captions, unread chat
    python app_project.py wait <name> [--timeout 900]    block until the user writes in the app's chat
    python app_project.py say <name> "<message>"         answer in the app's chat
    python app_project.py seg <name> <id|s-e> keep|cut ["reason"]   change one segment (or a time range)
    python app_project.py lock <name> on|off             approve / reopen the cut
    python app_project.py export <name>                  cut + captions + loudness -> Downloads
"""
import json, os, re, shutil, subprocess, sys, time, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / "reels"
PY = sys.executable
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
CAPTIONS = {"enabled": True, "font": "sans", "weight": "Black", "color": "#FFFFFF", "accent": "#FFD400", "size": 62,
            "stroke": 6, "lines": 1, "words": 3, "upper": True, "y": 1300}


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def folder(name):
    if not NAME_RE.match(name or ""): raise ValueError(f"nome de projeto inválido: {name!r}")
    return ROOT / name


def _now(): return datetime.datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------ state file (read-modify-write under a lock)
def load(name):
    return json.loads((folder(name) / "cinex.json").read_text(encoding="utf-8"))


def _write_json(p, data):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def update(name, fn):
    """Apply fn(state) under a lock file so the app and Claude never overwrite each other."""
    d = folder(name); lock = d / ".cinex.lock"
    for _ in range(200):
        try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); break
        except FileExistsError:
            if time.time() - lock.stat().st_mtime > 10: lock.unlink(missing_ok=True)   # stale lock
            time.sleep(.05)
    else: raise TimeoutError("projeto ocupado")
    try:
        st = load(name); fn(st); st["rev"] = st.get("rev", 0) + 1; _write_json(d / "cinex.json", st); return st
    finally:
        os.close(fd); lock.unlink(missing_ok=True)


def job(name, kind, **kw):
    """prep.json / export.json: progress of background jobs, written only by the job itself."""
    p = folder(name) / f"{kind}.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.update(kw, t=_now()); _write_json(p, data)


def read_job(name, kind):
    p = folder(name) / f"{kind}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ------------------------------------------------------------ helpers
def duration(src):
    e = subprocess.run([_ff(), "-hide_banner", "-i", str(src)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def words_in(words, s, e):
    return [w for w in words if s <= (w["s"] + w["e"]) / 2 < e]


def segments_from_keep(keep, dur, words):
    """Contiguous segments covering 0..dur: the kept stretches plus the pauses between them."""
    segs, cur = [], 0.0
    for s, e in sorted(keep):                        # the app plays in recorded order (no reordering yet)
        if s - cur > .05: segs.append(dict(s=round(cur, 2), e=round(s, 2), keep=False))
        segs.append(dict(s=round(max(s, cur), 2), e=round(e, 2), keep=True, reason=""))
        cur = max(cur, e)
    if dur - cur > .05: segs.append(dict(s=round(cur, 2), e=round(dur, 2), keep=False))
    for i, g in enumerate(segs):
        g["id"] = i + 1; g["text"] = " ".join(w["w"] for w in words_in(words, g["s"], g["e"]))
        g.setdefault("reason", "fala cortada" if g["text"] else "pausa")
    return segs


def waveform(src, out, step=.02):
    import numpy as np
    raw = subprocess.run([_ff(), "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.abs(np.frombuffer(raw, np.int16).astype(np.float32)); n = int(8000 * step)
    pk = x[: len(x) // n * n].reshape(-1, n).max(axis=1) if len(x) >= n else np.zeros(1)
    pk = pk / (np.percentile(pk, 99) or 1)
    _write_json(out, {"step": step, "peaks": [round(float(min(v, 1)), 3) for v in pk]})


# ------------------------------------------------------------ new project: proxy, transcription, proposed cut
def new(src, name=None, prompt=None):
    src = Path(src).expanduser().resolve()
    if not src.is_file(): raise FileNotFoundError(f"vídeo não encontrado: {src}")
    name = name or re.sub(r"[^A-Za-z0-9_.-]", "_", src.stem)[:64]
    d = folder(name); d.mkdir(parents=True, exist_ok=True)
    if not (d / "cinex.json").exists():
        _write_json(d / "cinex.json", dict(version=1, rev=0, name=name, src=str(src), duration=round(duration(src), 2),
                                           segments=[], cut_locked=False, captions=dict(CAPTIONS), keywords=[], fix={},
                                           chat=[], created=_now()))
    prepare(name, prompt)
    return name


def prepare(name, prompt=None):
    d = folder(name); st = load(name); src = st["src"]
    try:
        if not (d / "preview.mp4").exists():
            job(name, "prep", step="Gerando prévia", pct=5, done=False, error=None)
            subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", src, "-vf", "scale=-2:960", "-c:v", "libx264", "-preset",
                            "veryfast", "-crf", "26", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
                            str(d / "preview.mp4")], check=True)
        if not (d / "waveform.json").exists():
            job(name, "prep", step="Lendo o áudio", pct=20); waveform(src, d / "waveform.json")
        if not (d / "words_raw.json").exists():
            job(name, "prep", step="Transcrevendo (pode levar alguns minutos)", pct=30)
            subprocess.run([PY, str(HERE / "transcribe.py"), src, str(d / "words_raw.json")]
                           + (["--prompt", prompt] if prompt else []), check=True, capture_output=True)
        if not st["segments"]:
            job(name, "prep", step="Propondo o corte", pct=85)
            if not (d / "keep.json").exists():
                _write_json(d / "phrases.json", [[0, st["duration"]]])
                subprocess.run([PY, str(HERE / "plan_cut.py"), src, str(d / "phrases.json"), str(d / "keep.json")],
                               check=True, capture_output=True)
            words = json.loads((d / "words_raw.json").read_text(encoding="utf-8"))
            segs = segments_from_keep(json.loads((d / "keep.json").read_text()), st["duration"], words)
            update(name, lambda s: s.update(segments=segs))
        job(name, "prep", step="Pronto", pct=100, done=True, error=None)
    except Exception as e:
        job(name, "prep", step="Erro", done=True, error=str(e)[-500:]); raise


def projects():
    out = []
    for p in sorted(ROOT.glob("*/cinex.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
            out.append(dict(name=st["name"], duration=st["duration"], kept=round(sum(g["e"] - g["s"] for g in st["segments"] if g["keep"]), 1),
                            locked=st["cut_locked"], prep=read_job(st["name"], "prep")))
        except Exception: pass
    return out


# ------------------------------------------------------------ chat + edits (used by Claude through the CLI)
def say(name, text, who="cinex"):
    update(name, lambda s: s["chat"].append(dict(who=who, text=text, t=_now(), seen=who != "user")))


def unread(name):
    return [m for m in load(name)["chat"] if m["who"] == "user" and not m.get("seen")]


def mark_seen(name):
    update(name, lambda s: [m.update(seen=True) for m in s["chat"] if m["who"] == "user"])


def set_seg(name, ref, keep, reason=None):
    def fn(st):
        if re.fullmatch(r"\d+", ref):
            hit = [g for g in st["segments"] if g["id"] == int(ref)]
        else:                                           # "12.3-14.0": cut/keep a time range, splitting segments
            a, b = map(float, ref.split("-")); hit = []
            words = json.loads((folder(name) / "words_raw.json").read_text(encoding="utf-8"))
            new = []
            for g in st["segments"]:
                parts = [(g["s"], min(g["e"], a)), (max(g["s"], a), min(g["e"], b)), (max(g["s"], b), g["e"])]
                for i, (s, e) in enumerate(parts):
                    if e - s > .01:
                        ng = dict(g, s=round(s, 2), e=round(e, 2)); new.append(ng)
                        if i == 1: hit.append(ng)
            for i, g in enumerate(new):
                g["id"] = i + 1; g["text"] = " ".join(w["w"] for w in words_in(words, g["s"], g["e"]))
            st["segments"] = new
        if not hit: raise KeyError(f"segmento {ref} não encontrado")
        for g in hit:
            g["keep"] = keep
            if reason is not None: g["reason"] = reason
    return update(name, fn)


# ------------------------------------------------------------ export: cut -> captions -> loudness -> Downloads
def remap_words(words, segs):
    out, off = [], 0.0
    for g in segs:
        for w in words_in(words, g["s"], g["e"]):
            out.append(dict(w, s=round(off + max(0, w["s"] - g["s"]), 3), e=round(off + min(g["e"], w["e"]) - g["s"], 3)))
        off += g["e"] - g["s"]
    return out


def rgba(h, a=255):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def export(name):
    """Runs in its own process (the app starts `app_project.py export <name>`); progress goes to export.json."""
    d = folder(name); st = load(name); c = st["captions"]; os.chdir(d)
    try:
        kept = [g for g in st["segments"] if g["keep"]]
        if not kept: raise ValueError("nenhum trecho mantido no corte")
        job(name, "export", step="Cortando", pct=3, done=False, error=None, out=None)
        _write_json(d / "keep.json", [[g["s"], g["e"]] for g in kept])
        subprocess.run([PY, str(HERE / "cut.py"), st["src"], "keep.json", "cut.mp4", "--size", "1080x1920", "--crf", "16"],
                       check=True, capture_output=True)
        words = json.loads((d / "words_raw.json").read_text(encoding="utf-8"))
        _write_json(d / "words.json", remap_words(words, kept))
        job(name, "export", step="Encontrando rostos", pct=15)
        subprocess.run([PY, str(HERE / "faces.py"), "cut.mp4", "faces.json"], check=True, capture_output=True)
        job(name, "export", step="Desenhando legendas", pct=25)
        sys.path.insert(0, str(HERE)); import reels_lib as R
        fam = c["font"]
        if fam not in R.FONTS:                          # a font file the user picked in the app (project fonts/)
            fp = d / "fonts" / fam
            if not fp.is_file(): raise FileNotFoundError(f"fonte {fam} não encontrada")
            R.FONTS[fam] = str(fp); R.DEFAULT_W[fam] = None
        w = c["weight"] if R.DEFAULT_W.get(fam) else None
        R.CAPTION_STYLES["app"] = dict(upper=c["upper"], fam=fam, w=w, size=int(c["size"]), stroke=int(c["stroke"]), kfam=fam, kw=w,
                                       ksize=int(c["size"]), glow=False, max_words=int(c["words"]), max_chars=999,
                                       lines=int(c["lines"]), color=rgba(c["color"]))
        dur = duration(d / "cut.mp4")
        reel = R.Reel("cut.mp4", "words.json", "faces.json", [(0, dur + 1, 1.0, 1.0, R.eio)], ranges=[(0, dur + 1, "big")],
                      keywords=st.get("keywords", []), fix=st.get("fix", {}), caption_style="app", accent=rgba(c["accent"]),
                      look="none", jumpcuts=[], cuts=[], correct=False, cap_y=int(c["y"]))
        if not c["enabled"]: reel.groups = []
        reel.render("render.mp4", lambda f: job(name, "export", step="Renderizando", pct=25 + int(f * 65)))
        job(name, "export", step="Ajustando o volume (-14 LUFS)", pct=92)
        subprocess.run([PY, str(HERE / "mix_audio.py"), "render.mp4", "render.mp4", "final.mp4"], check=True, capture_output=True)
        out = Path.home() / "Downloads" / f"{name}_cinex.mp4"
        shutil.copy2(d / "final.mp4", out)
        job(name, "export", step="Pronto", pct=100, done=True, out=str(out))
        say(name, f"Vídeo exportado: {out.name} ({dur:.1f} s), na pasta Downloads.")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or b"").decode("utf-8", "replace")[-400:] if isinstance(e.stderr, bytes) else str(e.stderr)[-400:]
        job(name, "export", step="Erro", done=True, error=f"{Path(e.cmd[1]).name}: {msg}"); raise
    except Exception as e:
        job(name, "export", step="Erro", done=True, error=str(e)[-500:]); raise


# ------------------------------------------------------------ CLI
def _show(name):
    st = load(name)
    kept = sum(g["e"] - g["s"] for g in st["segments"] if g["keep"])
    print(f"{name}: {st['duration']:.1f} s -> {kept:.1f} s mantidos · corte {'TRAVADO' if st['cut_locked'] else 'aberto'} · rev {st['rev']}")
    for g in st["segments"]:
        print(f"  #{g['id']:<3} {g['s']:7.2f}-{g['e']:7.2f}  {'KEEP' if g['keep'] else 'cut '}  {g['reason'][:30]:30}  {g['text'][:90]}")
    print("legendas:", json.dumps(st["captions"], ensure_ascii=False))
    for m in unread(name): print(f"  [não lida] {m['t']} {m['text']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("args", nargs="*")
    ap.add_argument("--name"); ap.add_argument("--prompt"); ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    if a.cmd == "new": n = new(a.args[0], a.name, a.prompt); _show(n)
    elif a.cmd == "prepare": prepare(a.args[0], a.prompt)
    elif a.cmd == "list":
        for p in projects(): print(f"{p['name']:24} {p['duration']:6.1f}s -> {p['kept']:6.1f}s {'travado' if p['locked'] else ''}")
    elif a.cmd == "show": _show(a.args[0])
    elif a.cmd == "wait":                              # Claude: run in background, re-invoked when the user writes
        t0 = time.time()
        while time.time() - t0 < a.timeout:
            msgs = unread(a.args[0])
            if msgs:
                mark_seen(a.args[0])
                for m in msgs: print(f"[{m['t']}] usuário: {m['text']}")
                break
            time.sleep(1.5)
        else: print("(sem mensagens novas)")
    elif a.cmd == "say": say(a.args[0], " ".join(a.args[1:]))
    elif a.cmd == "seg": set_seg(a.args[0], a.args[1], a.args[2] == "keep", " ".join(a.args[3:]) or None); _show(a.args[0])
    elif a.cmd == "lock": update(a.args[0], lambda s: s.update(cut_locked=a.args[1] == "on"))
    elif a.cmd == "export": export(a.args[0])
    else: print(__doc__)
