"""Cut a video down to a list of kept segments (jump cuts) with click-free audio.

Usage: python cut.py <source> <keep.json> <out.mp4> [--size 1080x1920] [--crf 18] [--fit crop|blur|keep]
keep.json: [[start, end], ...] in SOURCE seconds, in order.
Render twice: 1080x1920 crf 18 for review, 1440x2560 crf 14 as the base for render
(zooms up to ~1.35x stay sharp). ffmpeg auto-applies phone rotation metadata.
--fit crop (default) fills the frame; blur shows the whole picture over a blurred copy of itself
(vertical footage in a 16:9 export); keep scales without cropping (at least --size on both sides) so the
engine's virtual camera can choose the framing (e.g. follow a face across a horizontal shot).
HDR sources (iPhone HLG, PQ) are tone mapped to Rec.709 automatically (hdr.py).
"""
import argparse, json, subprocess
import imageio_ffmpeg
from hdr import tonemap

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("keep"); ap.add_argument("out")
ap.add_argument("--size", default="1080x1920"); ap.add_argument("--crf", default="18")
ap.add_argument("--fit", choices=("crop", "blur", "keep"), default="crop")
a = ap.parse_args()
w, h = a.size.split("x")
K = json.load(open(a.keep))
tm = tonemap(a.src)                      # HLG/PQ phone footage → SDR (after scaling: cheaper)
tm = "," + tm if tm else ""
fl, cat = [], ""
for i, (s, e) in enumerate(K):
    d = e - s
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if a.fit == "blur":
        fl.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,split[b{i}][f{i}];[b{i}]{cover},boxblur=30:2,eq=brightness=-0.12{tm}[bg{i}];"
                  f"[f{i}]scale={w}:{h}:force_original_aspect_ratio=decrease{tm}[fg{i}];"
                  f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{i}]")
    elif a.fit == "keep":
        fl.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2{tm},setsar=1[v{i}]")
    else:
        fl.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,{cover}{tm},setsar=1[v{i}]")
    fl.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={d - 0.03:.3f}:d=0.03[a{i}]")
    cat += f"[v{i}][a{i}]"
fl.append(f"{cat}concat=n={len(K)}:v=1:a=1[v][a]")
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", a.src,
                "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
                "-crf", a.crf, "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], check=True)
print("total", round(sum(e - s for s, e in K), 2), "s")
# cuts.json: start of every segment in the CUT timeline (frame-accurate: each segment is rounded to whole
# frames by ffmpeg at 30 fps). Projects load it for `cuts=` so zoom decisions happen exactly on real cuts.
import os
starts, acc = [], 0.0
for s_, e_ in K:
    starts.append(round(acc, 3)); acc += round((e_ - s_) * 30) / 30
json.dump(starts, open(os.path.join(os.path.dirname(os.path.abspath(a.out)), "cuts.json"), "w"))
