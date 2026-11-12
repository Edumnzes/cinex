"""Pure motion-graphics videos (format `visualization_3d`, 2D energy-flow explainer): no footage underneath, a light background, one brand
accent, kinetic typography, app-like cards and an animated SYSTEM DIAGRAM (nodes, wires, energy flowing, states).
Style distilled from the user's references (clean SaaS/Apple-like motion; solar system diagrams with DC/AC flows).

    from motion_lib import *
    def draw(ov, t): ...                      # draw one frame on the RGBA overlay (1080x1920)
    Motion(draw, dur=56, bg=BG).cli()         # preview t1 t2 ... | full out.mp4 | check

Rules kept from the manual: every element has a function; one focal point at a time; sizes only from ts();
safe zones (top 270, bottom 480); text big enough to read without sound (the text IS the narration here).
Reading time: ~0.33 s per word + 1 s, never less than 2.2 s per sentence.
"""
import math, subprocess, sys
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from reels_lib import (W, H, FPS, FFM, SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE, T, RR, paste, pill, text_w, ts, stroke_for,
                       eo, eio, eback, clamp, prog, life, glyph_mid, baseline_for, font)
from formats import wrap

# ---------------------------------------------------------------- palette (light UI)
BG = (244, 244, 241); INK = (17, 17, 17, 255); MUTE = (138, 144, 154, 255); HAIR = (208, 211, 217, 255)
CARD = (255, 255, 255, 255); DC = (47, 107, 255, 255); AC = (255, 122, 26, 255)
DANGER = (239, 68, 68, 255); SAFE = (34, 197, 94, 255); GOLD = (242, 178, 30, 255)
SS = 2                                   # supersampling for vector layers (wires, glyphs)


def lerp(a, b, p): return tuple(int(round(x + (y - x) * p)) for x, y in zip(a, b))
def read_time(text): return max(2.2, 1.0 + .33 * len(text.split()))


# ---------------------------------------------------------------- kinetic text
def ktext(ov, t, t0, t1, text, cy, size=None, color=INK, weight="SemiBold", hl=None, cx=W / 2, maxw=900,
          lh=1.24, stagger=.045, family="sans", hl_weight="Bold"):
    """Sentence as kinetic type: words rise + fade in sequence, the whole block lifts out. `hl` = {word: colour}
    paints key words (compare case-insensitively, punctuation ignored). Returns the block's bbox (x0, y0, x1, y1)."""
    if not (t0 <= t < t1): return None
    size = size or ts("lg"); hl = {k.lower(): v for k, v in (hl or {}).items()}
    out = eo(prog(t, t1 - .28, .28)); lines = wrap(text, size, maxw, weight, family); wi = 0
    bx0, bx1 = W, 0
    for i, ln in enumerate(lines):
        y = cy + (i - (len(lines) - 1) / 2) * size * lh; base = baseline_for(y, size, weight, family)
        items = []
        for w in ln.split():
            key = w.lower().strip(".,!?:;…"); wt = hl_weight if key in hl else weight
            items.append((w, hl.get(key, color), wt, text_w(w, size, wt, family)))
        gap = size * .28; tot = sum(it[3] for it in items) + gap * (len(items) - 1); x = cx - tot / 2
        bx0, bx1 = min(bx0, x), max(bx1, x + tot)
        for w, col, wt, wd in items:
            p = eo(prog(t, t0 + wi * stagger, .38)); wi += 1
            if p > 0:
                paste(ov, T(w, size, col, wt, shadow=False, family=family), x + wd / 2,
                      base + glyph_mid(w, size, wt, family) + 26 * (1 - p) - 22 * out, a=p * (1 - out))
            x += wd + gap
    hh = len(lines) * size * lh
    return (bx0, cy - hh / 2, bx1, cy + hh / 2)


def ring(ov, t, t0, box, color=GOLD, width=7, pad=(34, 22), dur=.55):
    """Hand-drawn-like ellipse traced around a key phrase (reference: 'It's leverage.' circled)."""
    p = eio(prog(t, t0, dur))
    if p <= 0 or box is None: return
    x0, y0, x1, y1 = box; x0 -= pad[0]; x1 += pad[0]; y0 -= pad[1]; y1 += pad[1]
    w, h = int(x1 - x0), int(y1 - y0); L = Image.new("RGBA", (w * SS + 40, h * SS + 40)); d = ImageDraw.Draw(L)
    d.arc((20, 20, w * SS + 20, h * SS + 20), -200, -200 + 372 * p, fill=color, width=width * SS)
    ov.alpha_composite(L.resize((w + 20, h + 20), Image.LANCZOS), (int(x0) - 10, int(y0) - 10))


# ---------------------------------------------------------------- cards / chips
@lru_cache(maxsize=256)
def soft_card(w, h, r=36, fill=CARD, shadow=46):
    """White rounded card with a soft drop shadow (app-like UI card)."""
    m = 60; im = Image.new("RGBA", (w + 2 * m, h + 2 * m)); sh = Image.new("RGBA", im.size)
    sh.alpha_composite(RR(w, h, r, (20, 24, 40, shadow)), (m, m + 14)); sh = sh.filter(ImageFilter.GaussianBlur(18))
    im.alpha_composite(sh); im.alpha_composite(RR(w, h, r, fill, (0, 0, 0, 16), 2), (m, m)); return im


def card(ov, cx, cy, w, h, t, t0, r=36, a=1.0, fill=CARD):
    """Card pops in (0.9 -> 1 with a small overshoot). Returns the entrance progress."""
    p = prog(t, t0, .42)
    if p <= 0: return 0
    paste(ov, soft_card(int(w), int(h), r, fill), cx, cy, .9 + .1 * eback(p), a * eo(prog(t, t0, .25))); return p


def label(ov, text, cx, cy, size=None, color=MUTE, weight="Bold", a=1.0, ax=.5):
    size = size or ts("2xs")
    paste(ov, T(text, size, color, weight, shadow=False), cx, baseline_for(cy, size, weight) + glyph_mid(text, size, weight), a=a, ax=ax)


def chip(ov, t, t0, t1, text, cx, cy, bg=INK, fg=(255, 255, 255, 255), size=None):
    a = life(t, t0, t1, .3, .25)
    if a > 0: pill(ov, cx, cy, text, size or ts("xs"), bg, fg, s=.7 + .3 * eback(prog(t, t0, .35)), a=a)


def toggle(ov, cx, cy, p, on=SAFE, off=(200, 204, 211, 255), w=120, h=62):
    """iOS-like switch; p = 1 on, 0 off (animate p)."""
    paste(ov, RR(w, h, h // 2, lerp(off, on, p)), cx, cy)
    paste(ov, RR(h - 12, h - 12, (h - 12) // 2, (255, 255, 255, 255)), cx + (p - .5) * (w - h), cy)


# ---------------------------------------------------------------- wires with flowing energy
def dense(pts, r=30, step=3.0):
    """Orthogonal polyline -> dense point list with rounded corners (for draw-on and flow dots)."""
    out = []
    def seg(a, b):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(n + 1): out.append((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))
    cur = pts[0]
    for i in range(1, len(pts) - 1):
        a, c, b = pts[i - 1], pts[i], pts[i + 1]
        la, lb = math.dist(a, c), math.dist(c, b); rr = min(r, la / 2, lb / 2)
        p1 = (c[0] + (a[0] - c[0]) * rr / la, c[1] + (a[1] - c[1]) * rr / la)
        p2 = (c[0] + (b[0] - c[0]) * rr / lb, c[1] + (b[1] - c[1]) * rr / lb)
        seg(cur, p1)
        for k in range(1, 9):
            u = k / 8; out.append(((1 - u) ** 2 * p1[0] + 2 * u * (1 - u) * c[0] + u * u * p2[0],
                                   (1 - u) ** 2 * p1[1] + 2 * u * (1 - u) * c[1] + u * u * p2[1]))
        cur = p2
    seg(cur, pts[-1]); arr = np.array(out); d = np.r_[0, np.cumsum(np.hypot(*np.diff(arr, axis=0).T))]
    return arr, d


class Wires:
    """Supersampled layer for wires + flow dots inside a bounding box (kept small so every frame is cheap)."""
    def __init__(self, bbox): self.b = bbox; self.L = None
    def begin(self):
        x0, y0, x1, y1 = self.b; self.L = Image.new("RGBA", ((x1 - x0) * SS, (y1 - y0) * SS)); self.d = ImageDraw.Draw(self.L)
    def _p(self, pt): return ((pt[0] - self.b[0]) * SS, (pt[1] - self.b[1]) * SS)
    def line(self, path, color, width=8, p0=0.0, p1=1.0, a=1.0):
        arr, d = path; lo, hi = d[-1] * p0, d[-1] * p1
        pts = [self._p(p) for p, s in zip(arr, d) if lo <= s <= hi]
        if len(pts) < 2: return
        col = color[:3] + (int(color[3] * a),); wd = int(round(width * SS))
        self.d.line(pts, fill=col, width=wd, joint="curve")
        for p in (pts[0], pts[-1]): self.d.ellipse((p[0] - wd / 2, p[1] - wd / 2, p[0] + wd / 2, p[1] + wd / 2), fill=col)
    def dots(self, path, t, color, n=3, speed=170.0, r=9, a=1.0, glow=True):
        """Energy tokens travelling along the path (px/s). Use speed=0 with a<1 to freeze/fade them."""
        arr, d = path; L = d[-1]
        for k in range(n):
            s = (t * speed + k * L / n) % L; i = int(np.searchsorted(d, s)); x, y = self._p(arr[min(i, len(arr) - 1)])
            if glow: self.d.ellipse((x - r * 2 * SS, y - r * 2 * SS, x + r * 2 * SS, y + r * 2 * SS), fill=color[:3] + (int(46 * a),))
            self.d.ellipse((x - r * SS, y - r * SS, x + r * SS, y + r * SS), fill=(255, 255, 255, int(255 * a)))
            self.d.ellipse((x - (r - 3) * SS, y - (r - 3) * SS, x + (r - 3) * SS, y + (r - 3) * SS), fill=color[:3] + (int(255 * a),))
    def end(self, ov):
        x0, y0, x1, y1 = self.b; ov.alpha_composite(self.L.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))


# ---------------------------------------------------------------- glyphs of an energy system (cached sprites)
def _canvas(w, h): im = Image.new("RGBA", (w * 3, h * 3)); return im, ImageDraw.Draw(im)
def _done(im, w, h): return im.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=64)
def g_panel(w=104, h=60, state="on"):
    """PV module. state: on (blue cells) | off (grey) | hot (energised, red frame)."""
    im, d = _canvas(w, h); k = 3
    cell = {"on": (27, 49, 110, 255), "off": (150, 156, 168, 255), "hot": (27, 49, 110, 255)}[state]
    frame = {"on": (12, 22, 52, 255), "off": (120, 126, 138, 255), "hot": DANGER}[state]
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), 9 * k, fill=frame)
    d.rounded_rectangle((4 * k, 4 * k, (w - 4) * k, (h - 4) * k), 6 * k, fill=cell)
    for i in range(1, 4): d.line((w * k * i / 4, 4 * k, w * k * i / 4, (h - 4) * k), fill=(255, 255, 255, 70), width=k)
    d.line((4 * k, h * k / 2, (w - 4) * k, h * k / 2), fill=(255, 255, 255, 70), width=k)
    return _done(im, w, h)


@lru_cache(maxsize=16)
def g_inverter(w=84, h=96, on=True):
    im, d = _canvas(w, h); k = 3
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), 14 * k, fill=(236, 238, 242, 255), outline=(60, 66, 80, 255), width=3 * k)
    d.rounded_rectangle((16 * k, 16 * k, (w - 16) * k, 46 * k), 6 * k, fill=(24, 28, 40, 255))
    d.ellipse((w * k / 2 - 8 * k, 62 * k, w * k / 2 + 8 * k, 78 * k), fill=SAFE if on else (170, 175, 185, 255))
    return _done(im, w, h)


@lru_cache(maxsize=8)
def g_house(s=88, col=INK):
    im, d = _canvas(s, s); k = 3; w = 7 * k
    d.line([(8 * k, 42 * k), (44 * k, 10 * k), (80 * k, 42 * k)], fill=col, width=w, joint="curve")
    d.line([(18 * k, 38 * k), (18 * k, 78 * k), (70 * k, 78 * k), (70 * k, 38 * k)], fill=col, width=w, joint="curve")
    d.rounded_rectangle((36 * k, 52 * k, 52 * k, 78 * k), 3 * k, fill=col)
    return _done(im, s, s)


@lru_cache(maxsize=8)
def g_tower(s=88, col=INK):
    im, d = _canvas(s, s); k = 3; w = 6 * k
    d.line([(30 * k, 82 * k), (40 * k, 12 * k), (48 * k, 12 * k), (58 * k, 82 * k)], fill=col, width=w, joint="curve")
    for y, x0, x1 in ((26, 20, 68), (44, 14, 74)): d.line((x0 * k, y * k, x1 * k, y * k), fill=col, width=w)
    d.line([(34 * k, 60 * k), (54 * k, 44 * k)], fill=col, width=4 * k); d.line([(54 * k, 60 * k), (34 * k, 44 * k)], fill=col, width=4 * k)
    return _done(im, s, s)


@lru_cache(maxsize=8)
def g_sun(s=96, col=GOLD):
    im, d = _canvas(s, s); k = 3; c = s * k / 2
    d.ellipse((c - 20 * k, c - 20 * k, c + 20 * k, c + 20 * k), fill=col)
    for i in range(8):
        an = i * math.pi / 4; d.line((c + math.cos(an) * 28 * k, c + math.sin(an) * 28 * k, c + math.cos(an) * 42 * k, c + math.sin(an) * 42 * k),
                                     fill=col, width=7 * k)
    return _done(im, s, s)


@lru_cache(maxsize=8)
def g_flame(s=80):
    im, d = _canvas(s, s); k = 3
    def drop(cx, cy, r, top, col):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col); d.polygon([(cx - r * .92, cy - r * .4), (cx + r * .92, cy - r * .4), (cx + r * .1, top)], fill=col)
    drop(40 * k, 50 * k, 24 * k, 4 * k, DANGER); drop(41 * k, 58 * k, 13 * k, 30 * k, (255, 196, 64, 255))
    return _done(im, s, s)


@lru_cache(maxsize=8)
def g_check(s=44, col=SAFE):
    im, d = _canvas(s, s); k = 3
    d.ellipse((0, 0, s * k - 1, s * k - 1), fill=col); d.line([(11 * k, 23 * k), (19 * k, 31 * k), (33 * k, 14 * k)], fill=(255, 255, 255, 255), width=5 * k, joint="curve")
    return _done(im, s, s)


@lru_cache(maxsize=8)
def g_bolt(s=40, col=DANGER):
    im, d = _canvas(s, s); k = 3
    d.polygon([(24 * k, 2 * k), (8 * k, 22 * k), (18 * k, 22 * k), (14 * k, 38 * k), (32 * k, 16 * k), (21 * k, 16 * k)], fill=col)
    return _done(im, s, s)


@lru_cache(maxsize=4)
def _blob(r, col):
    im = Image.new("RGBA", (r * 2, r * 2)); ImageDraw.Draw(im).ellipse((r * .35, r * .35, r * 1.65, r * 1.65), fill=col)
    return im.filter(ImageFilter.GaussianBlur(r * .22))


def ambient(ov, t, col=GOLD, a=.16):
    """Two very soft accent blobs drifting slowly: keeps the frame alive during text holds (reference: soft rings)."""
    b = _blob(420, col[:3] + (int(255 * a),))
    paste(ov, b, 180 + 60 * math.sin(t * .23), 1560 + 50 * math.cos(t * .19))
    paste(ov, b, 930 + 50 * math.cos(t * .21), 260 + 40 * math.sin(t * .17), .8)


# ---------------------------------------------------------------- sound effects (same rules as the Reel engine)
def sfx_track(sfx, dur, path="sfx.wav"):
    """sfx = [(t, "categoria" | file, gain_db)] from ~/reels-banco/sfx. Long sounds are cut to the category's useful
    length, a riser ENDS at t. Returns the path, or None when nothing could be resolved (missing ones are printed)."""
    try: from banco import sfx_file, SFX_CAP
    except Exception: return None
    from reels_lib import _probe_dur
    items, miss = [], set()
    for t, name, gain in sfx:
        f = Path(name) if Path(name).suffix and Path(name).exists() else sfx_file(name, t)
        (items.append((t, name, f, gain)) if f else miss.add(name))
    if miss: print("SFX sem arquivo em ~/reels-banco/sfx ->", sorted(miss))
    if not items: return None
    cmd = [FFM, "-loglevel", "error", "-y", "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]; fl = []
    for i, (t, cat, f, gain) in enumerate(items):
        cmd += ["-i", str(f)]; d = _probe_dur(str(f)); cap = SFX_CAP.get(cat, 3.0); pre = ""
        if cat == "riser":
            use = min(d, cap); pre = f"atrim=start={d - use:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.15,"; ms = max(0, int((t - use) * 1000))
        else:
            if d > cap: pre = f"atrim=end={cap:.3f},afade=t=out:st={cap - .12:.3f}:d=0.12,"
            ms = max(0, int(t * 1000))
        fl.append(f"[{i + 1}:a]{pre}aresample=48000,aformat=channel_layouts=stereo,volume={gain}dB,adelay={ms}|{ms}[s{i}]")
    fl.append("[0:a]" + "".join(f"[s{i}]" for i in range(len(items))) + f"amix=inputs={len(items) + 1}:normalize=0:duration=first[a]")
    subprocess.run(cmd + ["-filter_complex", ";".join(fl), "-map", "[a]", path], check=True)
    print(f"wrote {path} ({len(items)} sfx)"); return path


# ---------------------------------------------------------------- renderer
class Motion:
    def __init__(self, draw, dur, bg=BG, sfx=(), amb=GOLD):
        self.draw, self.dur, self.bg, self.sfx, self.amb = draw, dur, bg, list(sfx), amb
        self.base = Image.new("RGBA", (W, H), bg + (255,))

    def frame(self, t, debug=False):
        ov = self.base.copy()
        if self.amb: ambient(ov, t, self.amb)
        self.draw(ov, t)
        if debug:
            d = ImageDraw.Draw(ov); d.rectangle((0, 0, W, SAFE_TOP), fill=(255, 0, 0, 40)); d.rectangle((0, SAFE_BOTTOM, W, H), fill=(255, 0, 0, 40))
            d.text((20, 20), f"{t:.2f}s", font=font(36, "Bold"), fill=(0, 0, 0, 255))
        return ov.convert("RGB")

    def bbox(self, t):
        """Bounding box of everything drawn at t (without the ambient background) for the safe-zone check."""
        ov = Image.new("RGBA", (W, H)); self.draw(ov, t)
        return ov.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox()

    def cli(self, argv=None):
        argv = argv or sys.argv[1:]; sys.stdout.reconfigure(encoding="utf-8")
        cmd, args = argv[0], [a for a in argv[1:] if not a.startswith("--")]
        if cmd == "preview":
            ts_ = [float(a) for a in args]; cols = min(6, len(ts_))
            sheet = Image.new("RGB", (cols * 360, math.ceil(len(ts_) / cols) * 640))
            for i, t in enumerate(ts_): sheet.paste(self.frame(t, "--debug" in argv).resize((360, 640), Image.LANCZOS), ((i % cols) * 360, (i // cols) * 640))
            sheet.save("preview.jpg", quality=88); print("wrote preview.jpg")
        elif cmd == "check":
            n = 0; t = 0.0
            while t < self.dur:
                bb = self.bbox(t)
                if bb and (bb[1] < SAFE_TOP - 6 or bb[3] > SAFE_BOTTOM + 6 or bb[0] < SAFE_SIDE - 30 or bb[2] > W - SAFE_SIDE + 30):
                    print(f"WARN {t:.2f}s fora da área segura {bb}"); n += 1
                t += .5
            if self.sfx and len(self.sfx) / max(self.dur, 1) * 10 > 2.0:
                print(f"WARN SFX: {len(self.sfx)} em {self.dur:.0f}s - use só nos eventos-chave (máx ~2 a cada 10 s)"); n += 1
            print(f"{n} warnings")
        elif cmd == "full":
            out = args[0]; n = int(self.dur * FPS)
            trk = sfx_track(self.sfx, self.dur) if self.sfx else None      # SFX from the bank, or a silent track
            audio = ["-i", trk] if trk else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            enc = subprocess.Popen([FFM, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                    *audio, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
                                    "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
            for i in range(n):
                enc.stdin.write(self.frame(i / FPS).tobytes())
                if i % 150 == 0: print(f"{i / FPS:.1f}s", flush=True)
            enc.stdin.close(); enc.wait(); print("done", out)
            subprocess.run([FFM, "-loglevel", "error", "-y", "-i", out, "-vf", "fps=1/2,scale=180:320,tile=10x3", "-frames:v", "1", "final_sheet.jpg"]); print("wrote final_sheet.jpg")
        else: print(self.cli.__doc__ or "preview t1 t2 ... [--debug] | check | full out.mp4")
