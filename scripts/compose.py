"""Build the RAW input for formats that need more than one source. The output is a normal 1440x2560 / 30 fps
video with audio, so the rest of the pipeline (transcribe -> plan -> cut -> project.py) runs unchanged.

split     React: reference video on top, reaction (face-centred) at the bottom.
          python compose.py split TOP.mp4 BOTTOM.MOV out.mp4 [--top-ss 0] [--bottom-ss 0] [--dur D]
                 [--ratio 0.5] [--top-gain -14] [--bottom-gain 0]
          Audio: the reaction at full level + the reference ducked (--top-gain dB). Captions then go on the seam
          (format cap_y 960) and ZOOM stays 1.0 (the layout is the framing).
          RIGHTS: only use a reference clip you may use (your own, licensed, or a short excerpt for commentary
          with credit). Instagram can mute or limit reposted audio/video.

clone     Clone: the same person twice in one locked shot. Take A = person on the LEFT, take B = on the RIGHT,
          recorded with the camera NOT moving (tripod), same light and framing.
          python compose.py clone A.MOV B.MOV out.mp4 [--seam 0.5] [--feather 90] [--b-offset 0] [--dur D]
          Left of the seam comes from A, right from B, blended over --feather px. Audio: A + B mixed (each
          speaks in its own pauses). --b-offset shifts B in time to sync the dialogue. Checks that the
          background matches (locked camera) and warns otherwise.

assemble  Voiceover / frase de identificação / conteúdo na legenda / gancho visual: clips in sequence,
          cover-cropped to 9:16, optionally under a separate narration.
          python compose.py assemble clips.json out.mp4 [--audio narration.wav] [--loop]
          clips.json: [{"src": "a.MOV", "ss": 2.0, "dur": 3.0}, ...]  (dur optional = until the end)
          --audio: the narration becomes the soundtrack and the video is fitted to it (clips loop with --loop,
          otherwise the last clip holds). Without --audio each clip keeps its own sound (silence if none).
Prints what it did; always look at the result with faces.py --sheet before planning.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, cv2, imageio_ffmpeg
from PIL import Image

FF = imageio_ffmpeg.get_ffmpeg_exe()
sys.path.insert(0, str(Path(__file__).resolve().parent)); from hdr import vf as hvf   # HLG/PQ → SDR after scaling
OW, OH, FPS = 1440, 2560, 30
MODEL = str(Path(__file__).resolve().parent.parent / "assets" / "yunet.onnx")
# Phone clips carry a "rotate" display matrix; ffmpeg rotates the pixels on decode but may copy the matrix
# to the output, so players rotate it AGAIN (clone came out sideways). Every encode clears it: rotate=0.


def probe(p, video=True):
    e = subprocess.run([FF, "-hide_banner", "-i", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    v = re.search(r"Video: .*?(\d{2,5})x(\d{2,5})", e); d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e)
    rot = re.search(r"rotation of (-?\d+)", e) or re.search(r"rotate\s*:\s*(-?\d+)", e)
    if not (v or (not video and d)): sys.exit(f"não consegui ler: {p} (confira o caminho; no JSON use C:/... e não /c/...)")
    w, h = (int(v.group(1)), int(v.group(2))) if v else (0, 0)
    if rot and abs(int(float(rot.group(1)))) in (90, 270): w, h = h, w          # phone footage stored sideways
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0
    return w, h, dur, "Audio:" in e


def frame_at(p, t, w=360):
    raw = subprocess.run([FF, "-loglevel", "error", "-ss", str(t), "-i", str(p), "-frames:v", "1", "-vf", hvf(p, f"scale={w}:-2"),
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


def face_centre(p, ss, dur):
    """Median face centre (fractions of the frame) over 7 samples; (0.5, 0.4) when no face is found."""
    det = None; pts = []
    for k in range(7):
        fr = frame_at(p, ss + dur * (k + .5) / 7)
        if fr is None: continue
        if det is None: det = cv2.FaceDetectorYN.create(MODEL, "", (fr.shape[1], fr.shape[0]), .6)
        det.setInputSize((fr.shape[1], fr.shape[0])); _, f = det.detect(fr)
        if f is not None and len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])[:4]
            pts.append(((x + w / 2) / fr.shape[1], (y + h / 2) / fr.shape[0]))
    return tuple(np.median(pts, 0)) if pts else (.5, .4)


def cover(w, h, tw, th, fx=.5, fy=.5):
    """scale+crop filter that covers tw x th, keeping (fx, fy) of the source as close to the centre as possible."""
    s = max(tw / w, th / h); sw, sh = int(round(w * s / 2) * 2), int(round(h * s / 2) * 2)
    x = int(min(max(fx * sw - tw / 2, 0), sw - tw)); y = int(min(max(fy * sh - th / 2, 0), sh - th))
    return f"scale={sw}:{sh},crop={tw}:{th}:{x}:{y},setsar=1"


def clear_rotation(path):
    """Remux (no re-encode) forcing display rotation 0: some filters (maskedmerge) carry the phone's rotation
    side data into the output even though the pixels are already upright."""
    tmp = str(path) + ".rot.mp4"
    run([FF, "-y", "-display_rotation", "0", "-i", str(path), "-c", "copy", "-movflags", "+faststart", tmp]); os.replace(tmp, path)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode: sys.exit("ffmpeg falhou:\n" + r.stderr[-1500:])


def split(a):
    tw, th, tdur, tau = probe(a.top); bw, bh, bdur, bau = probe(a.bottom)
    dur = a.dur or min(bdur - a.bottom_ss, tdur - a.top_ss)
    top_h = int(round(OH * a.ratio / 2) * 2); bot_h = OH - top_h
    fx, fy = face_centre(a.bottom, a.bottom_ss, dur)
    vf = (f"[0:v]{hvf(a.top, f'fps={FPS}', cover(tw, th, OW, top_h))}[t];[1:v]{hvf(a.bottom, f'fps={FPS}', cover(bw, bh, OW, bot_h, fx, max(fy - .08, 0)))}[b];"
          f"[t][b]vstack=inputs=2[v]")
    if tau and bau: af = f";[0:a]volume={a.top_gain}dB[ta];[1:a]volume={a.bottom_gain}dB[ba];[ta][ba]amix=inputs=2:normalize=0:duration=longest[a]"
    elif bau: af = f";[1:a]volume={a.bottom_gain}dB[a]"
    elif tau: af = f";[0:a]volume={a.top_gain}dB[a]"
    else: af = ""
    cmd = [FF, "-y", "-ss", str(a.top_ss), "-t", f"{dur:.3f}", "-i", a.top, "-ss", str(a.bottom_ss), "-t", f"{dur:.3f}", "-i", a.bottom,
           "-filter_complex", vf + af, "-map", "[v]"] + (["-map", "[a]"] if af else []) + \
          ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-metadata:s:v:0", "rotate=0", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", a.out]
    run(cmd)
    clear_rotation(a.out)
    print(f"split: {a.out} {dur:.1f}s · topo {OW}x{top_h} (ref. {a.top_gain} dB) · base {OW}x{bot_h} centrada no rosto ({fx:.2f},{fy:.2f})")
    print("lembrete: use só referência com direito de uso; legendas no meio (cap_y 960); ZOOM 1.0")


def clone(a):
    aw, ah, adur, aau = probe(a.A); bw, bh, bdur, bau = probe(a.B)
    dur = a.dur or min(adur, bdur - a.b_offset)
    # locked-camera check: background outside the middle band must match
    fa, fb = frame_at(a.A, min(1, adur / 2)), frame_at(a.B, min(1 + a.b_offset, bdur / 2))
    if fa is not None and fb is not None and fa.shape == fb.shape:
        band = np.r_[0:int(fa.shape[0] * .12), int(fa.shape[0] * .9):fa.shape[0]]
        diff = float(np.mean(cv2.absdiff(fa[band], fb[band])))
        print(f"fundo A x B (topo/rodapé): diferença média {diff:.1f}" + ("  AVISO: câmera parece ter mexido — a emenda pode aparecer" if diff > 18 else "  ok (câmera fixa)"))
    m = np.zeros((OH, OW), np.float32); sx = a.seam * OW; f = max(a.feather, 1)
    xs = np.clip((np.arange(OW) - (sx - f / 2)) / f, 0, 1)                        # 0 = A, 1 = B
    m[:] = xs[None, :]
    mask = os.path.join(tempfile.gettempdir(), "reels_clone_mask.png"); Image.fromarray((m * 255).astype(np.uint8)).save(mask)
    vf = (f"[0:v]{hvf(a.A, f'fps={FPS}', cover(aw, ah, OW, OH))},format=yuv420p[a];[1:v]{hvf(a.B, f'fps={FPS}', cover(bw, bh, OW, OH))},format=yuv420p[b];"
          f"[2:v]format=gray,scale={OW}:{OH}[m];[a][b][m]maskedmerge[v]")
    au = [i for i, has in ((0, aau), (1, bau)) if has]
    af = (";" + "".join(f"[{i}:a]" for i in au) + f"amix=inputs={len(au)}:normalize=0:duration=longest[au]") if len(au) == 2 else \
         (f";[{au[0]}:a]anull[au]" if au else "")
    cmd = [FF, "-y", "-t", f"{dur:.3f}", "-i", a.A, "-ss", str(a.b_offset), "-t", f"{dur:.3f}", "-i", a.B, "-loop", "1", "-i", mask,
           "-filter_complex", vf + af, "-map", "[v]"] + (["-map", "[au]"] if af else []) + \
          ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-metadata:s:v:0", "rotate=0", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", a.out]
    run(cmd)
    clear_rotation(a.out)
    print(f"clone: {a.out} {dur:.1f}s · emenda em {a.seam:.2f} da largura, suavizada em {a.feather}px · B deslocado {a.b_offset}s")


def assemble(a):
    clips = json.load(open(a.clips, encoding="utf-8")); tmp = Path(tempfile.mkdtemp(prefix="reels_asm_")); parts = []
    for i, c in enumerate(clips):
        w, h, d, has = probe(c["src"]); ss = c.get("ss", 0); dd = c.get("dur") or (d - ss)
        if ss >= d: sys.exit(f"{c['src']}: ss={ss} passa do fim do clipe ({d:.2f}s)")
        if dd > d - ss + .05:                              # a short clip would silently shorten the whole timeline
            print(f"aviso: {Path(c['src']).name} tem só {d - ss:.2f}s depois de ss={ss}; dur {dd} encurtado"); dd = d - ss
        fx, fy = (face_centre(c["src"], ss, dd) if c.get("face") else (.5, .5))
        out = tmp / f"p{i:03d}.mp4"
        cmd = [FF, "-y", "-ss", str(ss), "-t", f"{dd:.3f}", "-i", c["src"]]
        if not has or a.audio: cmd += ["-f", "lavfi", "-t", f"{dd:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = "1:a" if (not has or a.audio) else "0:a"
        cmd += ["-vf", hvf(c["src"], f"fps={FPS}", cover(w, h, OW, OH, fx, fy)), "-map", "0:v", "-map", amap, "-ar", "48000", "-ac", "2",
                "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-metadata:s:v:0", "rotate=0", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)]
        run(cmd); parts.append((out, dd))
    total = sum(d for _, d in parts)
    if a.audio:
        _, _, adur, _ = probe(a.audio, video=False)
        if a.loop:
            seq, acc = [], 0
            while acc < adur: p, d = parts[len(seq) % len(parts)]; seq.append((p, d)); acc += d
            parts = seq
    lst = tmp / "list.txt"; lst.write_text("".join(f"file '{p.as_posix()}'\n" for p, _ in parts), encoding="utf-8")
    joined = tmp / "joined.mp4"; run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    if a.audio:
        _, _, adur, _ = probe(a.audio, video=False)
        run([FF, "-y", "-i", str(joined), "-i", a.audio, "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={max(0, adur - total) + 1:.2f}[v]",
             "-map", "[v]", "-map", "1:a", "-t", f"{adur:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", a.out])
        clear_rotation(a.out)
        print(f"assemble: {a.out} · {len(clips)} clipe(s) sob narração de {adur:.1f}s" + (" (em loop)" if a.loop else "")
              + ("" if a.loop or total >= adur else f" · AVISO: faltam {adur - total:.1f}s de imagem (último clipe congelado) — use --loop ou mais clipes"))
    else:
        run([FF, "-y", "-i", str(joined), "-c", "copy", a.out]); clear_rotation(a.out); print(f"assemble: {a.out} · {len(clips)} clipe(s), {total:.1f}s")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("split"); s.add_argument("top"); s.add_argument("bottom"); s.add_argument("out")
    s.add_argument("--top-ss", type=float, default=0); s.add_argument("--bottom-ss", type=float, default=0); s.add_argument("--dur", type=float)
    s.add_argument("--ratio", type=float, default=.5); s.add_argument("--top-gain", type=float, default=-14); s.add_argument("--bottom-gain", type=float, default=0)
    c = sp.add_parser("clone"); c.add_argument("A"); c.add_argument("B"); c.add_argument("out")
    c.add_argument("--seam", type=float, default=.5); c.add_argument("--feather", type=int, default=90)
    c.add_argument("--b-offset", type=float, default=0); c.add_argument("--dur", type=float)
    m = sp.add_parser("assemble"); m.add_argument("clips"); m.add_argument("out"); m.add_argument("--audio"); m.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    {"split": split, "clone": clone, "assemble": assemble}[a.cmd](a)
