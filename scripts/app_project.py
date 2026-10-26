"""Cinex app projects: the state shared by the local app (app/server.py) and Claude Code.

One folder per video in ~/reels/<name>/ with:
    cinex.json     segments (keep / cut + reason), caption settings, chat, rev   <- the shared state
    preview.mp4    light H.264 proxy the browser can play (phones record HEVC .MOV)
    clips/<id>/    speech clips of a multi-clip project (talk, event): normalised proxy, words, waveform, faces;
                   st["clips"] = [{id, name, src, off, dur}] laid end to end = ONE timeline in "raw" seconds
    media/         B-roll clips: <id>.mp4 proxy + <id>.jpg filmstrip (+ uploaded files); st["media"] / st["broll"]
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
    python app_project.py order <name> <id> <id> ...      play order of kept segments (reorder phrases)
    python app_project.py clips <name> <video|folder> ...  add speech clips: transcribed, cut, appended to the timeline
    python app_project.py media <name> <video>           add a clip to the project's media (B-roll): proxy + filmstrip
    python app_project.py broll <name> <media_id> <t0> <t1> [ss] [full|card]   B-roll over the speech (raw seconds)
    python app_project.py export <name>                  cut + captions + loudness -> Downloads
"""
import json, os, re, shutil, subprocess, sys, time, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import hdr as HDR    # HLG/PQ phone footage → SDR
ROOT = Path.home() / "reels"
PY = sys.executable
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
FORMATS = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}    # Mobile 9:16 / Desktop 16:9
CAMERA = {"follow": True, "zoom": 1.0, "punch": True}     # follow the face, base zoom, zoom step on jump cuts
COLOR = {"correct": True, "look": "natural"}              # automatic correction per shot, then a look
CAPTIONS = {"enabled": True, "font": "sans", "weight": "Black", "color": "#FFFFFF", "accent": "#FFD400", "size": 62,
            "stroke": 6, "lines": 1, "words": 3, "upper": True, "y": 1300,
            "kfont": "", "kscale": 1.0}                          # emphasis word: own font ("" = same) and size


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


def segments_from_keep(keep, dur, words, start=0.0):
    """Contiguous segments covering start..dur: the kept stretches plus the pauses between them."""
    segs, cur = [], start
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
                                           segments=[], cut_locked=False, captions=dict(CAPTIONS), camera=dict(CAMERA), color=dict(COLOR), motions=[], motion_engine="html", sfx=[], format="vertical", keywords=[], fix={},
                                           chat=[], created=_now(), prompt=prompt or ""))
    prepare(name, prompt)
    return name


def prepare(name, prompt=None):
    d = folder(name); st = load(name); src = st["src"]
    try:
        if not (d / "preview.mp4").exists():
            job(name, "prep", step="Gerando prévia", pct=5, done=False, error=None)
            subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", src, "-vf", HDR.vf(src, "scale=-2:960"), "-c:v", "libx264", "-preset",
                            "veryfast", "-crf", "26", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
                            str(d / "preview.mp4")], check=True)
        if not (d / "waveform.json").exists():
            job(name, "prep", step="Lendo o áudio", pct=20); waveform(src, d / "waveform.json")
        if not (d / "faces_preview.json").exists():
            job(name, "prep", step="Encontrando rostos", pct=25)
            subprocess.run([PY, str(HERE / "faces.py"), str(d / "preview.mp4"), str(d / "faces_preview.json")],
                           check=True, capture_output=True)
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
            seen, nxt = set(), max((g["id"] for g in st["segments"]), default=0) + 1
            for g in new:                                # the first piece keeps the id, later pieces get new ones
                if g["id"] in seen: g["id"] = nxt; nxt += 1
                seen.add(g["id"]); g["text"] = " ".join(w["w"] for w in words_in(words, g["s"], g["e"]))
            st["segments"] = new
        if not hit: raise KeyError(f"segmento {ref} não encontrado")
        for g in hit:
            g["keep"] = keep
            if reason is not None: g["reason"] = reason
    return update(name, fn)


# ------------------------------------------------------------ speech clips: several videos on one timeline
# Each clip gets a proxy normalised to the project canvas (same size, 30 fps, 48 kHz stereo) so the proxies join
# without re-encoding into preview.mp4; words / waveform / faces are joined with the clip's offset. Segments, motions,
# B-roll and SFX keep working in "raw" seconds of that joined timeline; the export maps every kept segment back to
# (clip, local time) with cut_list() and cut.py's multi-source mode.
def clips_of(st):
    return st.get("clips") or [dict(id=1, name=Path(st["src"]).name, src=st["src"], off=0.0, dur=st["duration"])]


def _has_audio(src):
    return "Audio:" in subprocess.run([_ff(), "-hide_banner", "-i", str(src)], capture_output=True, text=True,
                                      encoding="utf-8", errors="replace").stderr


def _clip_proxy(src, out, canvas):
    cw, ch = canvas
    vf = HDR.vf(src, f"scale={cw}:{ch}:force_original_aspect_ratio=decrease:force_divisible_by=2",
                f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2", "setsar=1", "fps=30")
    audio = [] if _has_audio(src) else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]   # silent clip
    subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", str(src), *audio, "-vf", vf, "-ar", "48000", "-ac", "2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)], check=True, capture_output=True)
    return duration(out)


def _replace(tmp, dst):
    """os.replace with retries: on Windows the server may be streaming the old file to the browser."""
    for _ in range(100):
        try: os.replace(tmp, dst); return
        except PermissionError: time.sleep(.2)
    raise PermissionError(f"não consegui substituir {dst.name} (arquivo em uso)")


def _rebuild(name):
    """Join the clips' proxies, words, waveform and faces into the project files the app reads."""
    d = folder(name); cl = load(name)["clips"]
    lst = d / "clips" / "list.txt"
    lst.write_text("".join(f"file '{(d / 'clips' / str(c['id']) / 'preview.mp4').as_posix()}'\n" for c in cl), encoding="utf-8")
    subprocess.run([_ff(), "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    "-movflags", "+faststart", str(d / "preview.new.mp4")], check=True, capture_output=True)
    words, peaks, faces, step = [], [], [], .02
    for c in cl:
        cd = d / "clips" / str(c["id"])
        words += [dict(w, s=round(w["s"] + c["off"], 3), e=round(w["e"] + c["off"], 3))
                  for w in json.loads((cd / "words.json").read_text(encoding="utf-8"))]
        pk = json.loads((cd / "waveform.json").read_text(encoding="utf-8"))["peaks"]; n = round(c["dur"] / step)
        peaks += (pk + [0] * n)[:n]                      # exact length per clip keeps the next clip aligned
        fs = json.loads((cd / "faces.json").read_text(encoding="utf-8")); n = round(c["dur"] * 10)
        faces += [dict(t=round(c["off"] + i / 10, 1), f=(fs[i]["f"] if i < len(fs) else [])) for i in range(n)]
    _write_json(d / "words_raw.new.json", words); _replace(d / "words_raw.new.json", d / "words_raw.json")
    _write_json(d / "waveform.json", {"step": step, "peaks": peaks})
    (d / "faces_preview.json").write_text(json.dumps(faces), encoding="utf-8")
    _replace(d / "preview.new.mp4", d / "preview.mp4")


def _upgrade(name):
    """First extra clip on a single-video project: clip 1 = the original video, re-proxied to the canvas."""
    d = folder(name); st = load(name)
    if st.get("clips"): return
    e = subprocess.run([_ff(), "-hide_banner", "-i", str(d / "preview.mp4")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    canvas = tuple(int(v) // 2 * 2 for v in re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", e).groups())
    c1 = d / "clips" / "1"; c1.mkdir(parents=True, exist_ok=True)
    job(name, "prep", step=f"Preparando {Path(st['src']).name}", pct=3, done=False, error=None)
    dur = _clip_proxy(st["src"], c1 / "preview.mp4", canvas)
    shutil.copy2(d / "words_raw.json", c1 / "words.json"); shutil.copy2(d / "waveform.json", c1 / "waveform.json")
    subprocess.run([PY, str(HERE / "faces.py"), str(c1 / "preview.mp4"), str(c1 / "faces.json")], check=True, capture_output=True)
    update(name, lambda s: s.update(canvas=list(canvas), duration=round(dur, 3),
                                    clips=[dict(id=1, name=Path(s["src"]).name, src=s["src"], off=0.0, dur=round(dur, 3), sdur=s["duration"])]))


def add_clips(name, paths):
    """Append speech clips (files, or folders = their videos in name order) to the timeline: proxy, waveform, faces,
    transcription and the automatic pause cut for each, then one rebuild of the joined files."""
    files = []
    for p in paths:
        p = Path(p).expanduser().resolve()
        if p.is_dir(): files += sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXT)
        elif p.is_file() and p.suffix.lower() in VIDEO_EXT: files.append(p)
        else: raise FileNotFoundError(f"vídeo não encontrado: {p}")
    if not files: raise FileNotFoundError("nenhum vídeo encontrado")
    d = folder(name); added = 0
    try:
        _upgrade(name)
        for i, src in enumerate(files):
            st = load(name); cid = max(c["id"] for c in st["clips"]) + 1
            cd = d / "clips" / str(cid); cd.mkdir(parents=True, exist_ok=True)
            tag = f"Clipe {i + 1}/{len(files)} ({src.name})"
            pct = lambda k: 5 + int(90 * (i + k) / len(files))
            job(name, "prep", step=f"{tag}: prévia", pct=pct(0), done=False, error=None)
            dur = _clip_proxy(src, cd / "preview.mp4", tuple(st["canvas"]))
            job(name, "prep", step=f"{tag}: áudio e rostos", pct=pct(.15))
            waveform(src, cd / "waveform.json")
            subprocess.run([PY, str(HERE / "faces.py"), str(cd / "preview.mp4"), str(cd / "faces.json")], check=True, capture_output=True)
            if _has_audio(src):
                job(name, "prep", step=f"{tag}: transcrevendo", pct=pct(.3))
                prompt = st.get("prompt") or ""
                _run(tag, [PY, str(HERE / "transcribe.py"), str(src), str(cd / "words.json")] + (["--prompt", prompt] if prompt else []))
                job(name, "prep", step=f"{tag}: propondo o corte", pct=pct(.85))
                _write_json(cd / "phrases.json", [[0, dur]])
                _run(tag, [PY, str(HERE / "plan_cut.py"), str(src), str(cd / "phrases.json"), str(cd / "keep.json")])
            else:                                        # no audio (pure image): nothing to transcribe, keep it whole
                _write_json(cd / "words.json", []); _write_json(cd / "keep.json", [[0, dur]])
            off = sum(c["dur"] for c in st["clips"])
            words = [dict(w, s=w["s"] + off, e=w["e"] + off) for w in json.loads((cd / "words.json").read_text(encoding="utf-8"))]
            keep = [[max(0, a) + off, min(b, dur) + off] for a, b in json.loads((cd / "keep.json").read_text())]
            segs = segments_from_keep(keep, off + dur, words, start=off)
            def fn(s, cid=cid, src=src, off=off, dur=dur, segs=segs):
                nxt = max((g["id"] for g in s["segments"]), default=0) + 1
                for k, g in enumerate(segs): g["id"] = nxt + k
                s["segments"] += segs
                s["clips"].append(dict(id=cid, name=src.name, src=str(src), off=round(off, 3), dur=round(dur, 3)))
                s["duration"] = round(off + dur, 3)
            update(name, fn); added += 1
        job(name, "prep", step="Juntando os clipes", pct=97)
        _rebuild(name)
        update(name, lambda s: None)                    # bump rev: the app reloads the joined preview
        job(name, "prep", step="Pronto", pct=100, done=True, error=None)
    except Exception as e:
        if added:                                        # the clips that made it are in the state: keep the preview in step
            try: _rebuild(name); update(name, lambda s: None)
            except Exception: pass
        job(name, "prep", step="Erro", done=True, error=str(e)[-400:]); raise


def _run(tag, cmd):
    """Run a helper script; on failure raise with its last error line (not the whole traceback)."""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        last = [ln for ln in (r.stderr or r.stdout).strip().splitlines() if ln.strip()][-1:] or ["erro desconhecido"]
        raise RuntimeError(f"{tag}: {Path(cmd[1]).name} falhou — {last[0][-300:]}")


def cut_list(st, kept):
    """Kept segments in play order -> keep.json for cut.py: [[s, e]] (one video) or [[s, e, source]] (clips)."""
    if not st.get("clips"): return [[g["s"], g["e"]] for g in kept]
    out = []
    for g in kept:                                       # a segment never spans two clips (each clip is cut on its own)
        c = next((c for c in st["clips"] if c["off"] - .01 <= g["s"] < c["off"] + c["dur"]), st["clips"][-1])
        a, b = max(0.0, g["s"] - c["off"]), g["e"] - c["off"]
        if c.get("sdur"): b = min(b, c["sdur"])
        if b - a > .02: out.append([round(a, 3), round(b, 3), c["src"]])
    return out


# ------------------------------------------------------------ media (B-roll clips) + B-roll windows
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".webm", ".avi", ".mts"}
STRIP_H = 96                                             # filmstrip frame height (app media list + "entrada" picker)


def add_media(name, src):
    """Register a clip (the original file stays where it is) and build a light proxy + filmstrip for the app.
    Returns the media id. The entry shows up at once with ready=False; the app polls until it's ready."""
    src = Path(src).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() not in VIDEO_EXT: raise FileNotFoundError(f"vídeo não encontrado: {src}")
    d = folder(name) / "media"; d.mkdir(exist_ok=True)
    holder = {}
    def reg(st):
        st.setdefault("media", [])
        mid = max((m["id"] for m in st["media"]), default=0) + 1; holder["id"] = mid
        st["media"].append(dict(id=mid, name=src.name, src=str(src), dur=0, ready=False, error=None))
    update(name, reg); mid = holder["id"]
    try:
        dur = duration(src); n = max(1, min(40, round(dur)))
        subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", str(src), "-an", "-vf", HDR.vf(src, "scale=-2:720"),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-g", "15", "-movflags", "+faststart",
                        str(d / f"{mid}.mp4")], check=True, capture_output=True)
        subprocess.run([_ff(), "-loglevel", "error", "-y", "-i", str(src), "-vf",
                        HDR.vf(src, f"fps={n / dur:.5f},scale=-2:{STRIP_H}", ) + f",tile={n}x1", "-frames:v", "1", "-q:v", "4",
                        str(d / f"{mid}.jpg")], check=True, capture_output=True)
        upd = dict(dur=round(dur, 2), strip=n, hdr=HDR.is_hdr(src), ready=True)
    except Exception as e:
        upd = dict(error=str(getattr(e, "stderr", b"") or e)[-300:], ready=False)
    update(name, lambda st: next(m for m in st["media"] if m["id"] == mid).update(upd))
    return mid


def remove_media(name, mid):
    """Drop a clip and the B-roll that uses it. Deletes only the app's own files (proxy, filmstrip, uploaded copy)."""
    d = folder(name) / "media"
    def fn(st):
        m = next((x for x in st.get("media", []) if x["id"] == mid), None)
        if not m: raise KeyError(f"mídia {mid} não encontrada")
        st["media"].remove(m); st["broll"] = [b for b in st.get("broll", []) if b["media"] != mid]
        if Path(m["src"]).parent.resolve() == d.resolve(): Path(m["src"]).unlink(missing_ok=True)   # uploaded into the project
    update(name, fn)
    for ext in ("mp4", "jpg"): (d / f"{mid}.{ext}").unlink(missing_ok=True)


def add_broll(name, mid, t0, t1, ss=0.0, mode="full"):
    def fn(st):
        if not any(m["id"] == mid for m in st.get("media", [])): raise KeyError(f"mídia {mid} não encontrada")
        st.setdefault("broll", [])
        st["broll"].append(dict(id=max((b["id"] for b in st["broll"]), default=0) + 1, media=mid, t0=round(t0, 2), t1=round(t1, 2),
                                ss=round(ss, 2), mode=mode, zoom=True))
    return update(name, fn)


def broll_windows(st, kept, FH):
    """B-roll of the app (raw seconds over the speech) -> reels_lib `broll=` windows on the cut timeline."""
    media = {m["id"]: m for m in st.get("media", []) if m.get("ready")}; out = []
    for b in sorted(st.get("broll", []), key=lambda b: b["t0"]):
        m = media.get(b["media"])
        if not m: continue
        c0, c1 = raw_to_cut(b["t0"], kept), raw_to_cut(b["t1"], kept, end=True)
        if c1 - c0 < .2:                                  # crosses into a reordered phrase: keep its own length
            if any(g["s"] <= b["t0"] < g["e"] for g in kept): c1 = c0 + (b["t1"] - b["t0"])
            else: continue                                # entirely inside a removed stretch
        out.append(dict(t0=c0, t1=c1, src=m["src"], ss=float(b.get("ss", 0)), mode=b.get("mode", "full"),
                        zoom=(1.0, 1.08) if b.get("zoom", True) else (1.0, 1.0), prefer=700 * FH / 1920))
    return out


# ------------------------------------------------------------ export: cut -> captions -> loudness -> Downloads
def play_order(st):
    """Kept segments in PLAY order. `order` lists segment ids (set by the app when phrases are reordered);
    a kept segment missing from it (new cut, range edit) goes right after its kept predecessor in the source."""
    kept = [g for g in st["segments"] if g["keep"]]; by = {g["id"]: g for g in kept}
    out = [i for i in st.get("order", []) if i in by]; out = list(dict.fromkeys(out))
    for j, g in enumerate(kept):
        if g["id"] in out: continue
        prev = next((k["id"] for k in reversed(kept[:j]) if k["id"] in out), None)
        out.insert(out.index(prev) + 1 if prev is not None else 0, g["id"])
    return [by[i] for i in out]


def raw_to_cut(t, segs, end=False):
    """Raw-source time -> cut timeline for segments in play order (they may be reordered). A time inside a
    removed stretch snaps to the next kept clip in the source (or, for an end time, the end of the previous one)."""
    off, starts = 0.0, {}
    for g in segs:
        if g["s"] <= t < g["e"]: return off + t - g["s"]
        starts[g["id"]] = off; off += g["e"] - g["s"]
    if end:
        prev = max((g for g in segs if g["e"] <= t), key=lambda g: g["e"], default=None)
        return starts[prev["id"]] + prev["e"] - prev["s"] if prev else 0.0
    nxt = min((g for g in segs if g["s"] > t), key=lambda g: g["s"], default=None)
    return starts[nxt["id"]] if nxt else off


# motion templates of the app -> formats.py (one function each; the engine places them away from faces)
MOTIONS = {
    "titulo": "Título / capítulo", "topico": "Tópico numerado", "nome": "Nome de quem fala", "citacao": "Citação",
    "frase": "Frase grande", "seguir": "Chamada: seguir", "salvar": "Chamada: salvar",
    "gigante": "Palavra gigante (atrás da pessoa)", "cenario": "Texto no cenário (3D)",
}


def motion_fn(F, m, c0, c1, accent, n, total):
    tx, t2 = m.get("text", ""), m.get("text2", "")
    k = m["type"]
    if k == "titulo": return lambda ov, t: F.chapter_label(ov, t, c0, c1, tx.upper(), accent)
    if k == "topico": return lambda ov, t: F.tip_card(ov, t, c0, c1, n, total, tx, accent)
    if k == "nome": return lambda ov, t: F.name_card(ov, t, c0, c1, tx, t2, accent)
    if k == "citacao": return lambda ov, t: F.quote_card(ov, t, c0, c1, tx, t2, accent)
    if k == "frase": return lambda ov, t: F.big_phrase(ov, t, c0, c1, tx, [w for w in t2.replace(",", " ").split() if w], accent)
    if k == "gigante": return lambda ov, t: F.big_phrase(ov, t, c0, c1, tx.upper(), tx.split(), accent)   # classic: no matte
    if k == "cenario": return lambda ov, t: F.big_phrase(ov, t, c0, c1, tx.upper(), tx.split(), accent)   # classic: not tracked
    if k == "seguir": return lambda ov, t: F.cta_follow(ov, t, c0, c1, tx or "Siga para mais", accent)
    if k == "salvar": return lambda ov, t: F.cta_save(ov, t, c0, c1, tx or "Salve para não esquecer", accent)
    raise ValueError(f"motion desconhecido: {k}")


def remap_words(words, segs):
    out, off = [], 0.0
    for g in segs:
        for w in words_in(words, g["s"], g["e"]):
            out.append(dict(w, s=round(off + max(0, w["s"] - g["s"]), 3), e=round(off + min(g["e"], w["e"]) - g["s"], 3)))
        off += g["e"] - g["s"]
    return out


def source_is_vertical(d):
    """From the preview proxy, which already has the phone rotation applied."""
    e = subprocess.run([_ff(), "-hide_banner", "-i", str(d / "preview.mp4")], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    w, h = map(int, re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", e).groups())
    return h > w


def rgba(h, a=255):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def export(name):
    """Runs in its own process (the app starts `app_project.py export <name>`); progress goes to export.json."""
    d = folder(name); st = load(name); c = st["captions"]; os.chdir(d)
    fmt = st.get("format", "vertical"); FW, FH = FORMATS[fmt]
    try:
        kept = play_order(st)                            # play order (phrases may be reordered)
        if not kept: raise ValueError("nenhum trecho mantido no corte")
        job(name, "export", step="Cortando", pct=3, done=False, error=None, out=None)
        _write_json(d / "keep.json", cut_list(st, kept))
        cam = {**CAMERA, **st.get("camera", {})}; col = {**COLOR, **st.get("color", {})}
        vert_src = source_is_vertical(d)
        if fmt == "horizontal" and vert_src: fit, base = "blur", (FW, FH)              # whole picture on a blurred fill
        elif fmt == "vertical" and vert_src: fit, base = "keep", (1440, 2560)        # room for zoom, stays sharp
        elif fmt == "vertical": fit, base = "keep", (1080, 1920)                     # wide shot: the camera picks a 9:16 window
        else: fit, base = "keep", (2560, 1440)
        subprocess.run([PY, str(HERE / "cut.py"), st["src"], "keep.json", "cut.mp4", "--size", f"{base[0]}x{base[1]}", "--crf", "16", "--fit", fit],
                       check=True, capture_output=True)
        words = json.loads((d / "words_raw.json").read_text(encoding="utf-8"))
        _write_json(d / "words.json", remap_words(words, kept))
        job(name, "export", step="Encontrando rostos", pct=15)
        subprocess.run([PY, str(HERE / "faces.py"), "cut.mp4", "faces.json"], check=True, capture_output=True)
        job(name, "export", step="Desenhando legendas", pct=25)
        sys.path.insert(0, str(HERE)); import reels_lib as R
        R.W, R.H = FW, FH                               # the engine reads the frame size at render time
        R.SAFE_TOP, R.SAFE_BOTTOM = (270, FH - 480) if fmt == "vertical" else (60, FH - 60)
        fam = c["font"]
        if fam not in R.FONTS:                          # a font file the user picked in the app (project fonts/)
            fp = d / "fonts" / fam
            if not fp.is_file(): raise FileNotFoundError(f"fonte {fam} não encontrada")
            R.FONTS[fam] = str(fp); R.DEFAULT_W[fam] = None
        w = c["weight"] if R.DEFAULT_W.get(fam) else None
        kf = c.get("kfont") or fam
        if kf not in R.FONTS:
            fp = d / "fonts" / kf
            if not fp.is_file(): raise FileNotFoundError(f"fonte {kf} não encontrada")
            R.FONTS[kf] = str(fp); R.DEFAULT_W[kf] = None
        kw = w if kf == fam else R.DEFAULT_W.get(kf)
        R.CAPTION_STYLES["app"] = dict(upper=c["upper"], fam=fam, w=w, size=int(c["size"]), stroke=int(c["stroke"]), kfam=kf, kw=kw,
                                       ksize=int(c["size"] * float(c.get("kscale", 1.0))), glow=False, max_words=int(c["words"]), max_chars=999,
                                       lines=int(c["lines"]), color=rgba(c["color"]))
        dur = duration(d / "cut.mp4")
        if str(col["look"]).startswith("ref:"):          # look copied from a reference profile (estilo.py)
            import estilo
            ref = estilo.load(col["look"][4:])["regras"].get("cor") or {}
            if ref.get("lab_mean"):
                src = estilo.colour(d / "cut.mp4", duration(d / "cut.mp4"), base[0], base[1])
                R.register_transfer("ref", src["lab_mean"], src["lab_std"], ref["lab_mean"], ref["lab_std"], ref.get("forca", .6))
                col["look"] = "ref"
            else: col["look"] = ref.get("look_base", "natural")
        z = max(1.0, min(1.25, float(cam["zoom"])))
        cuts = json.loads((d / "cuts.json").read_text()) if (d / "cuts.json").exists() else []
        import formats as F                              # after R.W/R.H: it copies the frame size on import
        acc = rgba(c["accent"]); ms = sorted(st.get("motions", []), key=lambda m: m["t0"]); fns, hide, sfx = [], [], []
        tops = [m for m in ms if m["type"] == "topico"]
        ovs, planes = [], []                             # HTML motion (motion_html.py): overlays, and planes stuck to the scene
        use_html = st.get("motion_engine", "html") == "html" and ms
        if use_html:
            import motion_html as MH
            use_html = MH.available()
            if not use_html: say(name, "Motion em HTML indisponível (HyperFrames não instalado): usei o motion clássico.")
        for m in ms:
            c0, c1 = raw_to_cut(m["t0"], kept), raw_to_cut(m["t1"], kept, end=True)
            if c1 - c0 < .3:                              # ends in another (reordered) phrase: keep its own length
                if any(g["s"] <= m["t0"] < g["e"] for g in kept): c1 = c0 + (m["t1"] - m["t0"])
                else: continue                            # entirely inside a removed stretch
            n = tops.index(m) + 1 if m in tops else 0
            done = False
            if use_html and m["type"] == "cenario":         # 3D text on a tracked surface (plane_track.py)
                if not m.get("quad") or fit == "blur":
                    say(name, "Texto no cenário sem superfície marcada (ou vídeo em pé no 16:9): usei o motion clássico."); 
                else:
                    job(name, "export", step=f"Rastreando a superfície ({m.get('text', '')})", pct=20)
                    try:
                        import plane_track as PT
                        mov, _ = MH.render(m, FW, FH, c["accent"], c1 - c0, cache=d / "motion_cache")
                        tm = raw_to_cut(m.get("tmark", m["t0"]), kept) if any(g["s"] <= m.get("tmark", -1) < g["e"] for g in kept) else c0
                        qs = PT.track(d / "cut.mp4", min(max(tm, c0), c1), c0, c1, m["quad"])
                        planes.append(dict(src=str(mov), t0=c0, t1=c1, quads=qs, atras=bool(m.get("atras", True)))); done = True
                    except Exception as e:
                        say(name, f"Texto no cenário falhou, usei o clássico: {str(e)[:160]}")
            if use_html and not done and m["type"] != "cenario":
                job(name, "export", step=f"Motion {len(ovs) + len(fns) + 1}/{len(ms)} (HTML)", pct=20)
                try:
                    mov, _ = MH.render(m, FW, FH, c["accent"], c1 - c0, n, len(tops), cache=d / "motion_cache")
                    ovs.append(dict(src=str(mov), t0=c0, t1=c1, cx=FW / 2, w=FW, prefer=MH.PREFER[m["type"]] * FH / 1920,
                                    atras=bool(m.get("atras", m["type"] == "gigante"))))   # behind the person (matte)
                    done = True
                except Exception as e:                     # one bad element never blocks the export
                    say(name, f"Motion {m['type']} em HTML falhou, usei o clássico: {str(e)[:160]}")
            if not done: fns.append(motion_fn(F, m, c0, c1, acc, n, len(tops)))
            if m["type"] in ("citacao", "frase"): hide.append((c0, c1))   # the line is already on screen
            if m.get("sfx"): sfx.append((c0, m["sfx"], -12))
        for s in st.get("sfx", []):
            if any(g["s"] <= s["t"] < g["e"] for g in kept): sfx.append((raw_to_cut(s["t"], kept), s["cat"], float(s.get("gain", -12))))
        reel = R.Reel("cut.mp4", "words.json", "faces.json", [(0, dur + 1, z, z, R.eio)], motions=fns, overlays=ovs, planes=planes, sfx=sorted(sfx), hide_captions=hide,
                      broll=broll_windows(st, kept, FH),
                      ranges=[(0, dur + 1, "big" if cam["follow"] else None)],
                      keywords=st.get("keywords", []), fix=st.get("fix", {}), caption_style="app", accent=rgba(c["accent"]),
                      look=col["look"] if col["look"] in R.GRADES else "none", jumpcuts="auto" if cam["punch"] else [], cuts=cuts,
                      correct=bool(col["correct"]), cap_y=int(c["y"] / 1920 * FH))     # y is stored on the 9:16 scale; same relative height
        if not c["enabled"]: reel.groups = []
        reel.render("render.mp4", lambda f: job(name, "export", step="Renderizando", pct=25 + int(f * 65)))
        job(name, "export", step="Ajustando o volume (-14 LUFS)", pct=92)
        subprocess.run([PY, str(HERE / "mix_audio.py"), "render.mp4", "render.mp4", "final.mp4"], check=True, capture_output=True)
        out = Path.home() / "Downloads" / f"{name}_cinex{'' if fmt == 'vertical' else '_16x9'}.mp4"
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
    po = [g["id"] for g in play_order(st)]
    if po != [g["id"] for g in st["segments"] if g["keep"]]: print("ordem de reprodução:", " ".join(map(str, po)))
    kept = sum(g["e"] - g["s"] for g in st["segments"] if g["keep"])
    print(f"{name}: {st['duration']:.1f} s -> {kept:.1f} s mantidos · corte {'TRAVADO' if st['cut_locked'] else 'aberto'} · rev {st['rev']}")
    for g in st["segments"]:
        print(f"  #{g['id']:<3} {g['s']:7.2f}-{g['e']:7.2f}  {'KEEP' if g['keep'] else 'cut '}  {g['reason'][:30]:30}  {g['text'][:90]}")
    print("legendas:", json.dumps(st["captions"], ensure_ascii=False))
    for m in st.get("motions", []): print(f"  motion #{m['id']} {m['t0']:.2f}-{m['t1']:.2f} {m['type']}: {m.get('text', '')} {m.get('text2', '')} sfx={m.get('sfx') or '-'}")
    for s in st.get("sfx", []): print(f"  sfx #{s['id']} {s['t']:.2f} {s['cat']} {s.get('gain', -12)} dB")
    for m in st.get("media", []): print(f"  mídia #{m['id']} {m['name']} {m.get('dur', 0):.1f}s {'pronta' if m.get('ready') else m.get('error') or 'preparando'}")
    for b in st.get("broll", []): print(f"  b-roll #{b['id']} {b['t0']:.2f}-{b['t1']:.2f} mídia {b['media']} a partir de {b.get('ss', 0)}s {b.get('mode', 'full')}")
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
    elif a.cmd == "order":                             # play order of kept segment ids (missing ones follow the source)
        update(a.args[0], lambda s: s.update(order=[int(x) for x in a.args[1:]])); _show(a.args[0])
    elif a.cmd == "export": export(a.args[0])
    elif a.cmd == "media": print("mídia", add_media(a.args[0], a.args[1]))
    elif a.cmd == "clips": add_clips(a.args[0], a.args[1:]); _show(a.args[0])
    elif a.cmd == "broll":
        x = a.args; add_broll(x[0], int(x[1]), float(x[2]), float(x[3]), float(x[4]) if len(x) > 4 else 0.0, x[5] if len(x) > 5 else "full"); _show(x[0])
    else: print(__doc__)
