"""Sort downloaded sound effects into the bank: classify, clean, name, register the licence.

The user downloads sounds by hand (Pixabay has no audio API; this also serves Mixkit, Motion Array, Envato...)
and drops them, with any file name, into  ~/reels-banco/sfx/_entrada/ . Then:

    python sfx_ingest.py [--origem Pixabay] [--licenca "Pixabay Content License"] [--dry]

For every file:
  1. decode, trim silence at both ends (keeps 8 ms before the attack), 15 ms fade-out, peak to -3 dBFS
  2. classify into a category the engine uses: click · pop · whoosh · ding · riser · impact · flash · tick · error
       - the file NAME is the first evidence (download sites name files descriptively: "whoosh-6316.mp3")
       - the AUDIO is measured either way (duration, attack, where the energy peaks, brightness and its
         direction, how tonal it is, bass share) and classified by rules; when name and audio agree the
         confidence is high, when only the audio speaks it is medium, when nothing fits the file goes to
         sfx/_revisar/ for the user to decide — never guessed into a category
  3. write sfx/<categoria>/<categoria>_<nn>_<nome>.wav (48 kHz) and a line in sfx/sfx.json
     (categoria, origem, licenca, duracao, confianca, medidas, arquivo original)
  4. move the original to sfx/_entrada/_processados/ (nothing is deleted)
--dry only prints the table. Claude cannot hear: tell the user to listen once to what was classified by audio only.
"""
import argparse, hashlib, json, re, shutil, subprocess, sys, wave
from pathlib import Path
import numpy as np, imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from banco import BANCO, AUDIO_EXT, sfx_use

FF = imageio_ffmpeg.get_ffmpeg_exe(); SR = 48000
HINTS = [  # order matters: first match wins
    ("flash", r"flash|shutter|camera|obturador"),
    ("error", r"error|wrong|buzz|fail|negative|erro|denied"),
    ("riser", r"riser|rise|build[\s_-]?up|uplifter|swell|tension|subida"),
    ("whoosh", r"whoosh|woosh|swoosh|swish|swipe|sweep|transition|wind|whip"),
    ("ding", r"ding|bell|chime|success|notification|correct|sino|sparkle|coin|level[\s_-]?up"),
    ("impact", r"impact|hit|boom|thud|slam|punch|bass[\s_-]?drop|cinematic[\s_-]?hit|stomp|kick"),
    ("tick", r"typing|tick|tock|clock|counter|digitando|digitacao"),            # continuous typing / ticking
    ("pop", r"pop|bubble|plop|blip|bloop|pluck|drop"),
    ("click", r"click|tap|snap|switch|button|mouse|keyboard|teclado|clique"),
]


def decode(p):
    raw = subprocess.run([FF, "-loglevel", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def trim(x, thr_db=-48.0, pre=.008, post=.03):
    if not len(x) or np.max(np.abs(x)) < 1e-5: return x[:0], 0
    pk = np.max(np.abs(x)); thr = pk * 10 ** (thr_db / 20); idx = np.where(np.abs(x) > thr)[0]
    a = max(0, idx[0] - int(pre * SR)); b = min(len(x), idx[-1] + int(post * SR)); return x[a:b], a


def measure(x):
    """Numbers that separate the categories. All on the trimmed mono signal."""
    dur = len(x) / SR; hop = int(.005 * SR)
    env = np.sqrt(np.array([np.mean(x[i:i + hop] ** 2) for i in range(0, max(1, len(x) - hop), hop)]) + 1e-12)
    pk = int(np.argmax(env)); pv = env[pk]
    lo = next((i for i in range(pk + 1) if env[i] >= .1 * pv), 0); hi = next((i for i in range(pk + 1) if env[i] >= .9 * pv), pk)
    attack = (hi - lo) * .005
    after = np.where(env[pk:] < .1 * pv)[0]; decay = (after[0] if len(after) else len(env) - pk) * .005
    n = 1024; frames = [x[i:i + n] * np.hanning(n) for i in range(0, max(1, len(x) - n), n // 2)] or [np.pad(x, (0, max(0, n - len(x))))[:n] * np.hanning(n)]
    S = np.abs(np.fft.rfft(np.array(frames), axis=1)) + 1e-9; f = np.fft.rfftfreq(n, 1 / SR); P = S ** 2
    w = P.sum(1); cen = (S * f).sum(1) / S.sum(1)
    centroid = float(np.average(cen, weights=w)); flat = float(np.average(np.exp(np.log(S).mean(1)) / S.mean(1), weights=w))
    slope = float(np.polyfit(np.linspace(0, 1, len(cen)), cen, 1, w=np.sqrt(w))[0] / max(centroid, 1)) if len(cen) > 3 else 0.0
    bass = float(P[:, f < 160].sum() / P.sum())
    return dict(dur=round(dur, 3), attack=round(attack, 3), decay=round(decay, 3), peak_pos=round(pk * .005 / max(dur, 1e-3), 2),
                centroid=int(centroid), flat=round(flat, 3), slope=round(slope, 2), bass=round(bass, 2))


def by_audio(m):
    """Rule-based category from the measurements, or None when nothing fits clearly."""
    d, at, pp, fl, cen, bass, dec = m["dur"], m["attack"], m["peak_pos"], m["flat"], m["centroid"], m["bass"], m["decay"]
    if d >= .7 and pp >= .72: return "riser"                                   # energy keeps growing to the end
    if d <= .07 and at <= .012: return "click"                                 # a few milliseconds, instant
    if bass >= .35 and at <= .04 and .15 <= d <= 4: return "impact"            # sudden and heavy
    if fl <= .06 and dec >= .25 and cen >= 1200 and at <= .03: return "ding"   # pitched, bright, rings out
    if d <= .5 and at <= .03 and fl <= .25: return "pop"                       # short, soft-pitched blip
    if fl >= .18 and at >= .05 and .2 <= d <= 2.5 and .15 <= pp <= .8: return "whoosh"   # noisy, swells and fades
    return None


def by_name(name):
    s = re.sub(r"[_\-.\d]+", " ", name.lower())
    for cat, pat in HINTS:                       # word start only: "pop-up" yes, "laptop" no
        if re.search("(?<![a-z])(?:" + pat + ")", s): return cat
    return None


def classify(name, m):
    n, a = by_name(name), by_audio(m)
    if n and a == n: return n, .95, "nome e áudio concordam"
    if n: return n, .8, "pelo nome" + (f" (o áudio parece {a})" if a else "")
    if a: return a, .6, "só pelo áudio — vale ouvir"
    return None, 0.0, "não deu para classificar"


def save_wav(x, path):
    pk = np.max(np.abs(x)); x = x * (10 ** (-3 / 20) / pk) if pk > 0 else x
    fo = int(.015 * SR)
    if len(x) > fo * 2: x[-fo:] *= np.linspace(1, 0, fo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def free(path):
    """`path`, or `name-2.ext`, `name-3.ext`... — never overwrite a file already in the bank."""
    base, n = path, 2
    while path.exists(): path = base.with_name(f"{base.stem}-{n}{base.suffix}"); n += 1
    return path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--origem", default="Pixabay")
    ap.add_argument("--licenca", default="Pixabay Content License (uso comercial, sem atribuição)"); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(); sys.stdout.reconfigure(encoding="utf-8")
    root = BANCO / "sfx"; inbox = root / "_entrada"; inbox.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXT)
    if not files: print(f"nada em {inbox} — baixe os sons e coloque os arquivos nessa pasta"); return
    idx_p = root / "sfx.json"; idx = json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else []
    out = []; seen = {e.get("md5") for e in idx if e.get("md5")}
    for p in files:
        h = hashlib.md5(p.read_bytes()).hexdigest()
        if h in seen:                                   # "(1).mp3" copies and repeated downloads
            out.append((p.name, "duplicado", 0, "mesmo arquivo já está no banco", ""))
            if not a.dry:
                (inbox / "_processados" / "_duplicados").mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(free(inbox / "_processados" / "_duplicados" / p.name)))
            continue
        seen.add(h)
        x, _ = trim(decode(p))
        if len(x) < SR * .01: out.append((p.name, "—", 0, "áudio vazio ou ilegível", "")); continue
        m = measure(x); cat, conf, why = classify(p.stem, m)
        dest_dir = root / (cat or "_revisar"); slug = re.sub(r"[^a-z0-9]+", "-", p.stem.lower()).strip("-")[:32]
        n = len(list(dest_dir.glob("*.wav"))) + 1 if dest_dir.exists() else 1
        dest = free(dest_dir / (f"{cat}_{n:02d}_{slug}.wav" if cat else f"{slug}.wav"))
        uso = sfx_use(cat, m["dur"]) if cat else ""
        out.append((p.name, cat or "revisar", conf, why + (f" · {uso}" if uso and uso != "ideal" else ""), f"{m['dur']:.2f}s"))
        if a.dry: continue
        save_wav(x, dest)
        idx.append(dict(arquivo=str(dest.relative_to(root)).replace("\\", "/"), categoria=cat, origem=a.origem, licenca=a.licenca,
                        duracao=m["dur"], uso=uso, confianca=conf, criterio=why, medidas=m, original=p.name, md5=h))
        (inbox / "_processados").mkdir(exist_ok=True); shutil.move(str(p), str(free(inbox / "_processados" / p.name)))
    if not a.dry: idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'arquivo':38} {'categoria':9} {'conf.':5} {'dur.':6} critério")
    for name, cat, conf, why, dur in out: print(f"{name[:38]:38} {cat:9} {conf:<5} {dur:6} {why}")
    ok = sum(1 for o in out if o[1] not in ("revisar", "—", "duplicado")); dup = sum(1 for o in out if o[1] == "duplicado")
    print(f"\n{ok} classificados · {len(out) - ok - dup} para revisar · {dup} duplicados" + (" · (simulação, nada foi movido)" if a.dry else ""))


if __name__ == "__main__":
    main()
