"""Mix Adobe Enhance Speech stems back into the video, normalized for Instagram.

Usage: python mix_audio.py <video.mp4> <enhanced_speech.wav> <out.mp4> [--bg background.wav] [--bg-level 0.35] [--sfx sfx.wav] [--clean]
- Adds a little of the original ambience (background stem) so the voice doesn't sound
  "studio-pasted" onto a noisy location shot. 0.25-0.4 works for trade shows/streets;
  use 0 for indoor talking heads.
- loudnorm to -14 LUFS / -1.5 dBTP (Instagram normalizes around -14).
- --sfx: the sfx.wav written by `project.py full` (SFX timeline) is layered back on top,
  because this script replaces the render's audio.
- Two-pass loudnorm (measure, then exact linear gain). Video stream is copied (no re-encode).
- Prints the loudness measured on the OUTPUT file (not the input) - report that number.
- --clean: plan B when Adobe Enhance Speech isn't available - pass the video itself (or its audio) as
  <speech> and the voice gets high-pass 90 Hz + FFT denoise + gentle compression before the mix.
"""
import argparse, json, os, re, subprocess, sys, tempfile
import imageio_ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("speech"); ap.add_argument("out")
ap.add_argument("--bg"); ap.add_argument("--bg-level", type=float, default=0.35); ap.add_argument("--sfx")
ap.add_argument("--clean", action="store_true", help="limpa a voz com ffmpeg (sem Adobe)")
a = ap.parse_args(); sys.stdout.reconfigure(encoding="utf-8")
FF = imageio_ffmpeg.get_ffmpeg_exe()
mix = os.path.join(tempfile.gettempdir(), "reels_mix.wav")
ins = ["-i", a.speech]; chain = "[0:a]"; n = 1
CLEAN = "highpass=f=90,afftdn=nf=-25:nr=10,acompressor=threshold=-20dB:ratio=2.5:attack=10:release=150:makeup=2"
if a.bg and a.bg_level > 0:
    ins += ["-i", a.bg]; pre = f"[{n}:a]volume={a.bg_level}[b];"; chain += "[b]"; n += 1
else:
    pre = ""
if a.sfx:
    ins += ["-i", a.sfx]; chain += f"[{n}:a]"; n += 1
if a.clean: pre = f"[0:a]{CLEAN}[v0];" + pre; chain = "[v0]" + chain[5:]
mixer = f"{chain}amix=inputs={n}:normalize=0," if n > 1 else f"{chain}"
pre_mix = os.path.join(tempfile.gettempdir(), "reels_premix.wav")
subprocess.run([FF, "-loglevel", "error", "-y", *ins, "-filter_complex", f"{pre}{mixer}highpass=f=70,aresample=48000[a]",
                "-map", "[a]", "-ac", "2", pre_mix], check=True)
# two-pass loudnorm: single pass (dynamic mode) undershoots on short clips (measured -15.7 instead of -14)
r = subprocess.run([FF, "-hide_banner", "-i", pre_mix, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                    "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
subprocess.run([FF, "-loglevel", "error", "-y", "-i", pre_mix, "-af", ln + ",aresample=48000", "-ac", "2", mix], check=True)
subprocess.run([FF, "-loglevel", "error", "-y", "-i", a.video, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", a.out], check=True)
r = subprocess.run([FF, "-hide_banner", "-i", a.out, "-af", "ebur128=peak=true", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
summ = r[r.rfind("Summary:"):]
i_ = re.search(r"I:\s+(-?[\d.]+) LUFS", summ); tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ)
print(f"entrada {m['input_i']} LUFS -> saída {i_.group(1) if i_ else '?'} LUFS, pico real {tp.group(1) if tp else '?'} dBTP (alvo -14 / <= -1)")
