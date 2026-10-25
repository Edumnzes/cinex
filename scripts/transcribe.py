"""Word-level transcription with faster-whisper.

Usage: python transcribe.py <video_or_audio> <out_words.json> [--lang pt] [--model medium] [--prompt "SuaMarca, Produto X"]
Writes [{"w": word, "s": start, "e": end, "p": prob}, ...] and prints a readable line with
gaps > 0.35 s marked as ⟨1.2s⟩ and low-confidence words marked (?).
--prompt biases spelling of brand/product names (strongly recommended).
"""
import argparse, json, subprocess, sys, os, tempfile
try:
    import truststore; truststore.inject_into_ssl()  # antivirus/proxy SSL interception on Windows
except ImportError:
    pass
import imageio_ffmpeg
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--lang", default="pt"); ap.add_argument("--model", default="medium"); ap.add_argument("--prompt", default=None)
a = ap.parse_args()

wav = os.path.join(tempfile.gettempdir(), "reels_tr_16k.wav")
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-i", a.src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
m = WhisperModel(a.model, device="cpu", compute_type="int8")
# Loose no-speech/log-prob thresholds: with crowd noise (trade shows) whisper's defaults can silently
# drop 20-30 s of real speech. Better to transcribe a little noise than lose the intro.
kw = dict(language=a.lang, word_timestamps=True, condition_on_previous_text=False, initial_prompt=a.prompt,
          no_speech_threshold=0.9, log_prob_threshold=-2.0)
segs, _ = m.transcribe(wav, **kw)
words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2), "p": round(w.probability, 2)} for s in segs for w in s.words]
# Safety net: re-transcribe any gap > 5 s on its own (whisper sometimes skips a whole window).
import wave as _wave, numpy as _np
_w = _wave.open(wav); _a = _np.frombuffer(_w.readframes(_w.getnframes()), dtype=_np.int16).astype(float)
bounds = [0.0] + [x for w in words for x in (w["s"], w["e"])] + [len(_a) / 16000]
extra = []
for g0, g1 in zip(bounds[::2], bounds[1::2]):
    if g1 - g0 > 5:
        clip = os.path.join(tempfile.gettempdir(), "reels_tr_gap.wav")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-ss", f"{g0:.2f}", "-t", f"{g1 - g0:.2f}",
                        "-i", wav, clip], check=True)
        gs, _ = m.transcribe(clip, **{**kw, "initial_prompt": None})   # no prompt: it makes whisper hallucinate brand names into gaps
        extra += [{"w": w.word.strip(), "s": round(g0 + w.start, 2), "e": round(g0 + w.end, 2), "p": round(w.probability, 2)}
                  for s in gs for w in s.words]
if extra:
    print(f"(recovered {len(extra)} words from gaps > 5 s)")
    words = sorted(words + extra, key=lambda w: w["s"])
json.dump(words, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

sys.stdout.reconfigure(encoding="utf-8")
line, prev = [], 0.0
for w in words:
    g = w["s"] - prev
    if g > .35: line.append(f"⟨{g:.1f}s⟩")
    line.append(f'{w["w"]}@{w["s"]:.1f}' + ("(?)" if w["p"] < .5 else ""))
    prev = w["e"]
print(" ".join(line))
