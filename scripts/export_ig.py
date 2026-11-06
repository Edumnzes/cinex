"""Instagram deliverables from the final render (Instagram only, for now).

Usage: python export_ig.py final.mp4 --name "Marca - Tema" [--cover 1.2] [--out <pasta>] [--cuts cuts.json]

--name is a readable title ("Ynvest - Entrega Euroville"); files are named with saida.nome():
"AAAA-MM-DD Marca - Tema (Reels 9x16)". Writes to --out (default: the delivery folder, saida.pasta()):
  <nome>.mp4               the Reel (copied; run qa.py on it first)
  <nome> - capa.jpg        cover frame at --cover seconds (1080x1920) - upload it as the Reel cover
  <nome> - capa grade.jpg  the same frame with the PROFILE GRID crop (3:4, centre 1080x1440) outlined:
                           everything that must read on the grid (title, face) has to sit inside the box
  <nome> - story N.mp4     only when the video is longer than 60 s: Stories parts of <= 60 s, split on
                           the cut points of cuts.json when possible (never mid-word)
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw
from saida import nome, pasta

FF = imageio_ffmpeg.get_ffmpeg_exe()
GRID = (0, 240, 1080, 1680)          # 3:4 centre crop shown on the profile grid
STORY_MAX = 60.0


def duration(p):
    e = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e)
    return int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))


def story_splits(dur, cuts):
    if not cuts:                                   # no cut points (pure motion): equal parts, never a 2-second tail
        n = int(-(-dur // STORY_MAX)); return [dur * i / n for i in range(n + 1)]
    pts, t = [0.0], 0.0
    while dur - t > STORY_MAX:
        cand = [c for c in cuts if t + 20 < c <= t + STORY_MAX]
        t = max(cand) if cand else t + STORY_MAX
        pts.append(t)
    return pts + [dur]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--name", required=True); ap.add_argument("--cover", type=float, default=1.0)
    ap.add_argument("--out", default=None); ap.add_argument("--cuts", default="cuts.json")
    a = ap.parse_args(); sys.stdout.reconfigure(encoding="utf-8")
    out = Path(a.out).expanduser() if a.out else pasta(); out.mkdir(parents=True, exist_ok=True); dur = duration(a.video)
    base = nome(a.name)

    reel = out / f"{base}.mp4"; shutil.copy(a.video, reel); print("Reel:", reel, f"({dur:.1f} s)")

    cap = out / f"{base} - capa.jpg"
    subprocess.run([FF, "-loglevel", "error", "-y", "-ss", str(a.cover), "-i", a.video, "-frames:v", "1", "-q:v", "2", str(cap)], check=True)
    im = Image.open(cap).convert("RGB"); dim = Image.new("RGBA", im.size, (0, 0, 0, 150)); m = Image.new("L", im.size, 255)
    ImageDraw.Draw(m).rectangle(GRID, fill=0); dim.putalpha(Image.eval(m, lambda v: 150 if v else 0))
    g = Image.alpha_composite(im.convert("RGBA"), dim); ImageDraw.Draw(g).rectangle(GRID, outline=(255, 212, 0, 255), width=6)
    g.convert("RGB").save(out / f"{base} - capa grade.jpg", quality=90)
    print("Capa:", cap, "· prévia do recorte do perfil:", out / f"{base} - capa grade.jpg")

    if dur > STORY_MAX:
        cuts = json.load(open(a.cuts)) if Path(a.cuts).exists() else []
        pts = story_splits(dur, cuts)
        for i, (s, e) in enumerate(zip(pts, pts[1:]), 1):
            f = out / f"{base} - story {i}.mp4"
            subprocess.run([FF, "-loglevel", "error", "-y", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", a.video, "-c:v", "libx264",
                            "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(f)], check=True)
            print(f"Story {i}: {f} ({e - s:.1f} s)")
    else:
        print(f"Stories: não precisa dividir ({dur:.1f} s ≤ {STORY_MAX:.0f} s) - o próprio Reel pode ser compartilhado no Story")


if __name__ == "__main__":
    main()
