"""Cut a video down to a list of kept segments (jump cuts) with click-free audio.

Usage: python cut.py <source> <keep.json> <out.mp4> [--size 1080x1920] [--crf 18] [--fit crop|blur|keep]
keep.json: [[start, end], ...] in SOURCE seconds, in order. Several clips (app projects with more than one video):
[[start, end, "path/to/clip.mov"], ...] — <source> is then ignored; consecutive segments of the same clip are
rendered together and the parts joined. A 4th element sets options: {"speed": 0.35} = slow motion
(interpolated to 30 fps, silent), {"mudo": true} = keep the picture, drop the sound, {"crop": [x, y, w, h]} =
a window of the source (fractions) — reframes to take something out of the shot, sharp because it's cut from 4K.
Render twice: 1080x1920 crf 18 for review, 1440x2560 crf 14 as the base for render
(zooms up to ~1.35x stay sharp). ffmpeg auto-applies phone rotation metadata.
--fit crop (default) fills the frame; blur shows the whole picture over a blurred copy of itself
(vertical footage in a 16:9 export); keep scales without cropping (at least --size on both sides) so the
engine's virtual camera can choose the framing (e.g. follow a face across a horizontal shot).
HDR sources (iPhone HLG, PQ) are tone mapped to Rec.709 automatically (hdr.py).
"""
import argparse, json, os, re, subprocess, tempfile
import imageio_ffmpeg
from hdr import tonemap

FF = imageio_ffmpeg.get_ffmpeg_exe()
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("keep"); ap.add_argument("out")
ap.add_argument("--size", default="1080x1920"); ap.add_argument("--crf", default="18")
ap.add_argument("--fit", choices=("crop", "blur", "keep"), default="crop")
a = ap.parse_args()
w, h = a.size.split("x")
K = json.load(open(a.keep, encoding="utf-8"))
K = [[k[0], k[1], k[2] if len(k) > 2 else a.src, k[3] if len(k) > 3 else {}] for k in K]   # [s, e, source?, options?]


def render(src, segs, out, fit, w, h):
    tm = tonemap(src)                        # HLG/PQ phone footage → SDR (after scaling: cheaper)
    tm = "," + tm if tm else ""
    probe = subprocess.run([FF, "-hide_banner", "-i", src], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    au = "0:a" if "Audio:" in probe else "1:a"                      # silent clip: take silence from anullsrc
    fl, cat = [], ""
    for i, (s, e, o) in enumerate(segs):
        sp = float(o.get("speed", 1)); d = (e - s) / sp
        # slow motion: stretch time, then motion-interpolate back to 30 fps (smooth, not duplicated frames)
        slow = f",setpts=PTS/{sp},minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if sp < 1 else ""
        cx, cy, cw, ch = o.get("crop") or (0, 0, 1, 1)           # reframe: a window of the source, before scaling
        crop = f",crop=iw*{cw}:ih*{ch}:iw*{cx}:ih*{cy}" if cw < 1 or ch < 1 else ""
        cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        if fit == "blur":
            fl.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS{crop},split[b{i}][f{i}];[b{i}]{cover},boxblur=30:2,eq=brightness=-0.12{tm}[bg{i}];"
                      f"[f{i}]scale={w}:{h}:force_original_aspect_ratio=decrease{tm}[fg{i}];"
                      f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1{slow}[v{i}]")
        elif fit == "keep":
            fl.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS{crop},scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2{tm},setsar=1{slow}[v{i}]")
        else:
            fl.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS{crop},{cover}{tm},setsar=1{slow}[v{i}]")
        if o.get("mudo") or sp < 1: fl.append(f"[1:a]atrim=0:{d:.3f},asetpts=PTS-STARTPTS[a{i}]")      # silent stretch
        else: fl.append(f"[{au}]atrim={s}:{e},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={d - 0.03:.3f}:d=0.03[a{i}]")
        cat += f"[v{i}][a{i}]"
    fl.append(f"{cat}concat=n={len(segs)}:v=1:a=1[v][a]")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
                    "-crf", a.crf, "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", out], check=True)


runs = []                                     # consecutive segments of the same source render together
for s_, e_, src, o in K:
    if runs and runs[-1][0] == src: runs[-1][1].append((s_, e_, o))
    else: runs.append((src, [(s_, e_, o)]))
if len(runs) == 1:
    render(runs[0][0], runs[0][1], a.out, a.fit, w, h)
else:                                         # several clips: render each run, then join them (same codec settings)
    tmp = tempfile.mkdtemp(prefix="cinex_cut_"); parts = []
    for i, (src, segs) in enumerate(runs):
        p = os.path.join(tmp, f"p{i:04d}.mp4")
        if i == 0 or a.fit != "keep": render(src, segs, p, a.fit, w, h)
        else: render(src, segs, p, "crop", w0, h0)    # "keep" size depends on the source: match the first run exactly
        if i == 0:
            e = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
            w0, h0 = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", e).groups()
        parts.append(p)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w", encoding="utf-8") as f: f.writelines(f"file '{p.replace(os.sep, '/')}'\n" for p in parts)
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    "-movflags", "+faststart", a.out], check=True)
    for p in parts + [lst]: os.remove(p)
    os.rmdir(tmp)
K = [(s_, s_ + (e_ - s_) / float(o.get("speed", 1))) for s_, e_, _, o in K]     # lengths on the cut timeline
print("total", round(sum(e - s for s, e in K), 2), "s")
# cuts.json: start of every segment in the CUT timeline (frame-accurate: each segment is rounded to whole
# frames by ffmpeg at 30 fps). Projects load it for `cuts=` so zoom decisions happen exactly on real cuts.
import os
starts, acc = [], 0.0
for s_, e_ in K:
    starts.append(round(acc, 3)); acc += round((e_ - s_) * 30) / 30
json.dump(starts, open(os.path.join(os.path.dirname(os.path.abspath(a.out)), "cuts.json"), "w"))
