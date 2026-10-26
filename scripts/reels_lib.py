"""reels_lib — render engine for dynamic Instagram Reels.

A per-video project file (see assets/example_project.py) imports this module, defines the
camera keyframes, speaker ranges and motion-graphic functions, builds a `Reel` and calls
`reel.cli()`. The engine handles: frame I/O via ffmpeg, face-tracked + smoothed camera,
background dim/blur for explainer screens, Hormozi-style word captions, previews,
smoothness strips and a face-collision check.

Canvas is 1080x1920; the source should be a 1440x2560 cut so zooms stay sharp.
"""
import json, subprocess, sys, math, re
from pathlib import Path
import numpy as np, cv2, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FFM = imageio_ffmpeg.get_ffmpeg_exe()
ASSETS = Path(__file__).resolve().parent.parent / "assets"
W, H, FPS = 1080, 1920, 30

# Layout system (see references/style-guide.md §5). Organic Reels UI covers the top ~270 px and the
# bottom ~25% (username, description, audio: ~480 px); everything that must be read lives between
# SAFE_TOP and SAFE_BOTTOM. Captions sit low (lower third, just above the UI) so faces and cards breathe.
SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE = 270, H - 480, 80
BAND_TOP = (300, 520)       # hooks, chips, CTA
BAND_MID = (560, 1140)      # explainer cards
CAP_Y = 1300                # caption centre line (lower third)
CAP_GAP = 96                # minimum air between any card and the caption line (whitespace / proximity)
CARD_W = 904                # max card / inset width (88 px side margins) — cards, B-roll insets, charts

# Proportion: one modular type scale (ratio 1.25, "major third", base 32 px). Every text size in a
# project comes from here, so sizes relate to each other instead of being picked ad hoc — this is what
# keeps hierarchy readable and the frame from looking "off". Max 3 levels on screen at once.
TYPE = {"2xs": 20, "xs": 26, "sm": 32, "md": 40, "lg": 50, "xl": 62, "2xl": 78, "3xl": 98}
def ts(level): return TYPE[level]
def stroke_for(size): return max(3, round(size * .09))     # outline stays proportional to the letters

YEL = (255, 212, 0, 255); GRN = (34, 197, 94, 255); RED = (239, 68, 68, 255)
WHITE = (255, 255, 255, 255); BLACK = (0, 0, 0, 255); NAVY = (11, 17, 32, 232); GRAY = (160, 170, 185, 255)

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3                     # ease-out cubic
def eexpo(x): x = clamp(x); return 1 if x >= 1 else 1 - 2 ** (-10 * x)  # ease-out expo (punch-ins)
def eio(x): x = clamp(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def eback(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def prog(t, a, d): return clamp((t - a) / d)
def life(t, a, b, fi=.3, fo=.25):
    """0..1 envelope: eased fade-in after a, fade-out before b."""
    if t < a or t > b: return 0.0
    return min(eo((t - a) / fi), eo((b - t) / fo))

# ---------------------------------------------------------------- drawing primitives
_fc, _tc, _rc, _ic = {}, {}, {}, {}
# Font families (all OFL, bundled in assets/):
#   sans  Montserrat (Thin..Black)         — workhorse: captions, cards, numbers
#   serif Libre Baskerville Italic          — elegant accent word inside a sans line ("Um *problema* de saúde")
#   cond  Bebas Neue (single weight)        — cinematic / "immersive" titles, tall condensed caps
#   hand  Caveat (Regular, Bold)            — handwritten accent with glow ("dar mal")
FONTS = {"sans": "Montserrat.ttf", "serif": "SerifItalic.ttf", "cond": "BebasNeue-Regular.ttf", "hand": "Caveat.ttf"}
DEFAULT_W = {"sans": "Black", "serif": "Bold Italic", "cond": None, "hand": "Bold"}
try:                                    # user asset bank (~/reels-banco/fontes): every font becomes a family name
    from banco import register_fonts as _reg_fonts; _reg_fonts(FONTS, DEFAULT_W)
except Exception as _e:                 # the bank is optional
    pass
def font(size, weight=None, family="sans"):
    if family not in FONTS: raise KeyError(f"fonte '{family}' não existe (embutidas + ~/reels-banco/fontes): {sorted(FONTS)}")
    weight = weight or DEFAULT_W.get(family)
    if family == "serif" and weight and "Italic" not in weight: weight = "Bold Italic"
    if family == "hand" and weight not in ("Regular", "Bold"): weight = "Bold"
    k = (size, weight, family)
    if k not in _fc:
        fp = Path(FONTS[family]); f = ImageFont.truetype(str(fp if fp.is_absolute() else ASSETS / fp), size)
        if DEFAULT_W.get(family): f.set_variation_by_name(weight)
        _fc[k] = f
    return _fc[k]

def T(txt, size, fill=WHITE, weight=None, stroke=0, sf=BLACK, shadow=True, family="sans", glow=None, glow_r=18):
    """Cached text sprite. Sprites carry `stroke+24` (+glow) px transparent padding on each side.
    glow=(r,g,b,a) adds a soft coloured halo (neon/keyword emphasis look)."""
    k = (txt, size, fill, weight, stroke, shadow, family, glow, glow_r)
    if k in _tc: return _tc[k]
    f = font(size, weight, family); pad = stroke + 24 + (glow_r * 2 if glow else 0)
    bb = f.getbbox(txt, stroke_width=stroke)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=sf)
    if glow:
        ga = im.getchannel("A").filter(ImageFilter.GaussianBlur(glow_r)).point(lambda v: min(255, int(v * 1.6 * glow[3] / 255)))
        gl = Image.new("RGBA", im.size, glow[:3] + (0,)); gl.putalpha(ga); gl.alpha_composite(im); im = gl
    if shadow:
        a = im.getchannel("A").filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * .55))
        sh = Image.new("RGBA", im.size); sh.putalpha(a)
        base = Image.new("RGBA", im.size); base.alpha_composite(sh, (0, 6)); base.alpha_composite(im); im = base
    _tc[k] = im
    return im

def glyph_mid(txt, size, weight=None, family="sans", stroke=0):
    """Vertical centre of the text's ink relative to its BASELINE (negative = above). A T() sprite is centred on
    its ink box, so words with descenders ("que", "g") or no ascenders sit at different heights if pasted by
    centre. Paste at  baseline + glyph_mid(...)  to put every word on one baseline."""
    bb = font(size, weight, family).getbbox(txt, anchor="ls", stroke_width=stroke); return (bb[1] + bb[3]) / 2

def baseline_for(cy, size, weight=None, family="sans"):
    """Baseline that puts a line of capitals visually centred on cy."""
    return cy - font(size, weight, family).getbbox("H", anchor="ls")[1] / 2

def text_w(txt, size, weight=None, family="sans"):
    """Visible width of a text (without sprite padding) — use it to size cards/pills."""
    bb = font(size, weight, family).getbbox(txt); return bb[2] - bb[0]

# ---------------------------------------------------------------- colour grading
# Looks distilled from the reference reels (see references/visual-references.md).
# Each: per-channel lift (shadows), gain (highlights), gamma, S-curve contrast, saturation, vignette.
GRADES = {
    "none":        None,
    "clean_warm":  dict(lift=(14, 11, 6), gain=(1.0, .98, .93), gamma=(1.0, 1.0, 1.02), contrast=.9, sat=.86, vig=.10),   # cream, soft, "autoridade" (oraulcharles)
    "teal_orange": dict(lift=(0, 8, 14), gain=(1.04, .99, .9), gamma=(.97, 1.0, 1.04), contrast=1.12, sat=1.06, vig=.18),  # warm skin, teal shadows (obiel)
    "moody":       dict(lift=(4, 3, 8), gain=(.96, .92, .88), gamma=(1.08, 1.1, 1.08), contrast=1.18, sat=.82, vig=.35),    # low-key, dark, practical lights (raele)
    "natural":     dict(lift=(0, 0, 0), gain=(.98, 1.0, 1.02), gamma=(1.0, 1.0, .99), contrast=1.04, sat=1.02, vig=.05),  # near-neutral, after correction
    "vivid_day":   dict(lift=(0, 0, 4), gain=(1.03, 1.01, .98), gamma=(.98, .98, 1.0), contrast=1.1, sat=1.15, vig=.12),    # outdoor, punchy (rick_miura)
}
_gc = {}
def _grade_tables(name):
    if name in _gc: return _gc[name]
    g = GRADES[name]; x = np.arange(256) / 255.0; luts = []
    for c in range(3):
        y = x ** g["gamma"][c]
        y = .5 + (y - .5) * g["contrast"] if g["contrast"] <= 1 else y + (g["contrast"] - 1) * (y - .5) * (1 - abs(2 * y - 1)) * 2
        y = g["lift"][c] / 255 + y * (g["gain"][c] - g["lift"][c] / 255)
        luts.append(np.clip(y * 255, 0, 255).astype(np.uint8))
    yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 1.414
    vig = (1 - g["vig"] * np.clip((r - .35) / .65, 0, 1) ** 1.6).astype(np.float32)[..., None]
    _gc[name] = (luts, vig, g["sat"]); return _gc[name]

def grade(img, name):
    """Apply a look from GRADES to an RGB uint8 frame (1080x1920)."""
    if not name or GRADES.get(name) is None: return img
    luts, vig, sat = _grade_tables(name)
    out = np.dstack([cv2.LUT(img[..., c], luts[c]) for c in range(3)]).astype(np.float32)
    if abs(sat - 1) > .01:
        lum = out @ np.float32([.299, .587, .114]); out = lum[..., None] + (out - lum[..., None]) * sat
    return np.clip(out * vig, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- caption styles
# hormozi  : UPPERCASE Montserrat Black + stroke, keyword yellow (retention / sales)
# minimal  : sentence case Montserrat SemiBold, soft shadow, keyword swapped to serif italic + accent colour (authority / premium)
# cinematic: Bebas Neue caps, keyword yellow with soft glow (outdoor, storytelling)
CAPTION_STYLES = {
    # sizes from TYPE: captions are "xl" (62) — below display titles ("2xl"/"3xl"), above card labels.
    "hormozi":   dict(upper=True,  fam="sans",  w="Black",    size=62, stroke=6, kfam="sans",  kw="Black",       ksize=62, glow=False, max_words=3, max_chars=20),
    "minimal":   dict(upper=False, fam="sans",  w="SemiBold", size=50, stroke=0, kfam="serif", kw="Bold Italic", ksize=62, glow=True,  max_words=4, max_chars=28),
    "cinematic": dict(upper=True,  fam="cond",  w=None,       size=78, stroke=0, kfam="cond",  kw=None,          ksize=98, glow=True,  max_words=3, max_chars=20),
}

def RR(w, h, r, fill, ol=None, ow=0):
    """Anti-aliased rounded rectangle sprite (drawn 3x, downsampled)."""
    w, h = int(w), int(h); k = (w, h, r, fill, ol, ow)
    if k in _rc: return _rc[k]
    s = 3; im = Image.new("RGBA", (w * s, h * s))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * s - 1, h * s - 1), r * s, fill=fill, outline=ol, width=ow * s)
    _rc[k] = im.resize((w, h), Image.LANCZOS)
    return _rc[k]

def paste(ov, spr, cx, cy, s=1.0, a=1.0, ax=.5, ay=.5):
    """Composite `spr` onto `ov` anchored at (cx,cy) with scale s and opacity a (clipped)."""
    if a <= .004 or s <= .01: return
    if abs(s - 1) > .005:
        spr = spr.resize((max(1, int(spr.width * s)), max(1, int(spr.height * s))), Image.BILINEAR)
    if a < .996:
        spr = spr.copy(); spr.putalpha(spr.getchannel("A").point(lambda v: int(v * a)))
    x = int(round(cx - spr.width * ax)); y = int(round(cy - spr.height * ay))
    x0, y0 = max(0, x), max(0, y); x1, y1 = min(ov.width, x + spr.width), min(ov.height, y + spr.height)
    if x1 <= x0 or y1 <= y0: return
    if (x0, y0, x1, y1) != (x, y, x + spr.width, y + spr.height):
        spr = spr.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    ov.alpha_composite(spr, (x0, y0))

def pill(ov, cx, cy, text, size=40, bg=YEL, fg=BLACK, icon_name=None, s=1.0, a=1.0, pad=40, gap=16):
    """Pill sized from its content so icon + text never overlap (the #1 layout bug)."""
    tw = text_w(text, size); isz = int(size * 1.3) if icon_name else 0
    w = pad * 2 + tw + (isz + gap if icon_name else 0); h = int(size * 2.1)
    paste(ov, RR(w, h, h // 2, bg), cx, cy, s, a)
    x = cx - w * s / 2 + pad * s
    if icon_name:
        paste(ov, icon(icon_name, isz, fg), x + isz * s / 2, cy, s, a); x += (isz + gap) * s
    paste(ov, T(text, size, fg, shadow=False), x + tw * s / 2, cy + 2, s, a)
    return w, h

def icon(name, sz, col=YEL, lvl=1.0):
    """Vector icons: battery(lvl), bolt, sun, inverter, chart, cart, plus, check, home, factory, panel, money."""
    k = (name, sz, col, round(lvl, 2))
    if k in _ic: return _ic[k]
    s = 3; S = sz * s; im = Image.new("RGBA", (S, S)); d = ImageDraw.Draw(im); lw = max(3, S // 14)
    if name == "battery":
        bx0, by0, bx1, by1 = S * .06, S * .28, S * .84, S * .72
        d.rounded_rectangle((bx0, by0, bx1, by1), S * .08, outline=col, width=lw)
        d.rounded_rectangle((bx1 + lw * .3, S * .42, S * .95, S * .58), S * .03, fill=col)
        m = lw * 1.8; iw = (bx1 - bx0 - 2 * m) * clamp(lvl)
        if iw > 2: d.rounded_rectangle((bx0 + m, by0 + m, bx0 + m + iw, by1 - m), S * .04, fill=col)
    elif name == "bolt":
        d.polygon([(S*.58,S*.04),(S*.2,S*.56),(S*.47,S*.56),(S*.38,S*.96),(S*.8,S*.4),(S*.52,S*.4)], fill=col)
    elif name == "sun":
        c = S / 2; d.ellipse((c - S*.2, c - S*.2, c + S*.2, c + S*.2), fill=col)
        for i in range(8):
            a = i * math.pi / 4
            d.line((c + math.cos(a)*S*.3, c + math.sin(a)*S*.3, c + math.cos(a)*S*.45, c + math.sin(a)*S*.45), fill=col, width=lw)
    elif name == "inverter":
        d.rounded_rectangle((S*.12, S*.08, S*.88, S*.92), S*.1, outline=col, width=lw)
        d.line([(S*.25 + i*S*.5/40, S*.5 - math.sin(i/40*2*math.pi)*S*.13) for i in range(41)], fill=col, width=lw, joint="curve")
        d.line((S*.3, S*.76, S*.7, S*.76), fill=col, width=lw)
    elif name == "chart":
        for i, hh in enumerate((.35, .55, .8)):
            x = S*.14 + i*S*.27; d.rounded_rectangle((x, S*(.9-hh), x + S*.19, S*.9), S*.03, fill=col)
        d.line((S*.1, S*.5, S*.4, S*.3, S*.6, S*.38, S*.9, S*.08), fill=WHITE, width=lw, joint="curve")
    elif name == "cart":
        d.line((S*.05, S*.15, S*.2, S*.15, S*.32, S*.66, S*.82, S*.66), fill=col, width=lw, joint="curve")
        d.polygon([(S*.22, S*.25), (S*.92, S*.25), (S*.82, S*.55), (S*.3, S*.55)], fill=col)
        for x in (.38, .76): d.ellipse((S*x - S*.07, S*.74, S*x + S*.07, S*.88), fill=col)
    elif name == "plus":
        d.line((S*.5, S*.18, S*.5, S*.82), fill=col, width=lw * 2); d.line((S*.18, S*.5, S*.82, S*.5), fill=col, width=lw * 2)
    elif name == "check":
        d.line((S*.15, S*.52, S*.4, S*.76, S*.86, S*.24), fill=col, width=lw * 2, joint="curve")
    elif name == "home":
        d.polygon([(S*.5, S*.1), (S*.92, S*.48), (S*.08, S*.48)], fill=col)
        d.rectangle((S*.2, S*.46, S*.8, S*.9), fill=col); d.rectangle((S*.42, S*.62, S*.58, S*.9), fill=(0, 0, 0, 0))
    elif name == "factory":
        d.polygon([(S*.05, S*.9), (S*.05, S*.45), (S*.3, S*.6), (S*.3, S*.45), (S*.55, S*.6), (S*.55, S*.45), (S*.8, S*.6), (S*.8, S*.15), (S*.95, S*.15), (S*.95, S*.9)], fill=col)
    elif name == "panel":
        d.polygon([(S*.2, S*.2), (S*.95, S*.2), (S*.8, S*.75), (S*.05, S*.75)], outline=col, width=lw)
        for f in (1 / 3, 2 / 3): d.line((S*(.2 + .75*f), S*.2, S*(.05 + .75*f), S*.75), fill=col, width=lw // 2)
        d.line((S*.125, S*.475, S*.875, S*.475), fill=col, width=lw // 2); d.line((S*.45, S*.75, S*.45, S*.92), fill=col, width=lw)
    elif name == "sprout":                      # agro / plantation
        d.line((S*.5, S*.95, S*.5, S*.45), fill=col, width=lw)
        d.chord((S*.08, S*.18, S*.58, S*.62), 180, 360, fill=col); d.polygon([(S*.08, S*.4), (S*.5, S*.4), (S*.5, S*.55)], fill=col)
        d.ellipse((S*.5, S*.1, S*.95, S*.5), fill=col)
        d.line((S*.2, S*.95, S*.8, S*.95), fill=col, width=lw)
    elif name == "pin":                         # location
        d.ellipse((S*.2, S*.05, S*.8, S*.65), fill=col); d.polygon([(S*.25, S*.45), (S*.75, S*.45), (S*.5, S*.95)], fill=col)
        d.ellipse((S*.38, S*.2, S*.62, S*.44), fill=(0, 0, 0, 0))
    elif name == "structure":                   # mounting structure / truss
        d.line((S*.08, S*.85, S*.5, S*.2, S*.92, S*.85), fill=col, width=lw, joint="curve")
        d.line((S*.08, S*.85, S*.92, S*.85), fill=col, width=lw)
        for f in (.3, .5, .7): d.line((S*f, S*.85, S*(.5 + (f - .5) * .4), S*(.2 + abs(f - .5) * 1.3)), fill=col, width=lw // 2)
    elif name == "money":
        d.ellipse((S*.1, S*.1, S*.9, S*.9), outline=col, width=lw)
        d.text((S*.5, S*.52), "$", font=font(int(S*.5)), fill=col, anchor="mm")
    _ic[k] = im.resize((sz, sz), Image.LANCZOS)
    return _ic[k]


# ---------------------------------------------------------------- B-roll clips
class _Clip:
    """Sequential ffmpeg reader for a B-roll clip, pre-scaled to its on-screen size.
    Restarts (seeks) only when the requested time jumps, so full renders read each frame once."""
    def __init__(self, src, ss, w, h, cover):
        self.src, self.ss, self.w, self.h, self.cover = src, ss, w, h, cover
        self.p = None; self.nt = None; self.last = None
    def _open(self, lt):
        if self.p: self.p.kill()
        vf = (f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase,crop={self.w}:{self.h}" if self.cover
              else f"scale={self.w}:{self.h}")
        self.p = subprocess.Popen([FFM, "-loglevel", "error", "-ss", f"{self.ss + lt:.3f}", "-i", self.src, "-vf", f"fps={FPS},{vf}",
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        self.nt = lt
    def frame(self, lt):
        if self.p is None or self.nt is None or abs(lt - self.nt) > 1.5 / FPS: self._open(lt)
        b = self.p.stdout.read(self.w * self.h * 3)
        if len(b) == self.w * self.h * 3:
            self.last = np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3)
        self.nt = lt + 1 / FPS
        return self.last

class _Overlay:
    """Sequential RGBA reader for an animated overlay from the bank: alpha video (.mov ProRes 4444 / qtrle / png,
    .webm VP9 - decoded with libvpx-vp9 so the alpha survives), .gif, or a folder of PNG frames.
    Scaled to width w (height keeps the aspect). frame(lt) returns an RGBA PIL image (or None after the end)."""
    def __init__(self, src, kind, w, loop=False, speed=1.0):
        self.src, self.kind, self.loop, self.speed = src, kind, loop, speed
        if kind == "png_seq":
            self.files = sorted(Path(src).glob("*.png")); im = Image.open(self.files[0]); sw, sh = im.size
        else:
            sw, sh = _probe_size(src)
        self.w = int(w); self.h = int(round(self.w * sh / sw / 2) * 2)
        self.dur = len(self.files) / FPS if kind == "png_seq" else _probe_dur(src)
        self.p = None; self.nt = None; self.last = None
    def _open(self, lt):
        if self.p: self.p.kill()
        pre = ["-c:v", "libvpx-vp9"] if self.src.lower().endswith(".webm") else []
        lp = ["-stream_loop", "-1"] if self.loop else []
        self.p = subprocess.Popen([FFM, "-loglevel", "error", *lp, *pre, "-ss", f"{lt * self.speed:.3f}", "-i", self.src,
                                   "-vf", f"setpts=PTS/{self.speed},fps={FPS},scale={self.w}:{self.h}", "-f", "rawvideo",
                                   "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.nt = lt
    def frame(self, lt):
        if not self.loop and lt * self.speed > self.dur: return None
        if self.kind == "png_seq":
            i = int(lt * self.speed * FPS); i = i % len(self.files) if self.loop else min(i, len(self.files) - 1)
            return Image.open(self.files[i]).convert("RGBA").resize((self.w, self.h), Image.LANCZOS)
        if self.p is None or self.nt is None or abs(lt - self.nt) > 1.5 / FPS: self._open(lt)
        b = self.p.stdout.read(self.w * self.h * 4)
        if len(b) == self.w * self.h * 4: self.last = Image.frombuffer("RGBA", (self.w, self.h), b, "raw", "RGBA", 0, 1)
        self.nt = lt + 1 / FPS
        return self.last

def _probe_dur(src):
    e = subprocess.run([FFM, "-hide_banner", "-i", src], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e)
    return int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 1.0

def _probe_size(src):
    probe = subprocess.run([FFM, "-hide_banner", "-i", src], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", probe); w, h = int(m.group(1)), int(m.group(2))
    if re.search(r"rotation of -?90", probe): w, h = h, w
    return w, h


_CURRENT = {}
def slot(t0, t1, h, prefer=None, margin=32):
    """Best vertical centre for a block of height h shown during [t0, t1]: stays inside the safe
    area above the captions and avoids the union of the tracked face boxes over that window.
    Decided once per motion (cached) so cards never drift with the face. Use it for every card:
        cy = slot(36.3, 40.85, 232, prefer=900)"""
    r = _CURRENT.get("reel")
    key = (t0, t1, h, prefer)
    if key in _CURRENT.setdefault("slots", {}): return _CURRENT["slots"][key]
    lo, hi = SAFE_TOP + h / 2, CAP_Y - CAP_GAP - h / 2
    prefer = (lo + hi) / 2 if prefer is None else prefer
    boxes = [b for b in (r.face_box(t) for t in np.arange(t0, t1, .2)) if b] if r else []
    best, bc = prefer, 1e18
    for y in np.arange(lo, max(lo, hi) + 1, 8):
        ov = sum(max(0, min(y + h / 2, b[3] + margin) - max(y - h / 2, b[1] - margin)) for b in boxes)
        c = ov * 1000 + abs(y - prefer)
        if c < bc: best, bc = float(y), c
    _CURRENT["slots"][key] = best
    return best


class Reel:
    """
    src        1440x2560 (or any 9:16) cut, audio included
    words      words.json of the CUT (transcribe.py)
    faces      faces.json of the CUT (faces.py)
    zoom_keys  [(t0, t1, z0, z1, ease_fn)] in order; t0==t1 = instant jump (use at shot changes)
    scenes     [t, ...] shot changes -> zoom bump + short flash
    ranges     [(t0, t1, mode)] who the camera follows: "left" | "right" | "big" | None (centre, B-roll)
    motions    [fn(ov, t), ...] drawing functions (use BAND_* rows; never cover the face)
    bg         [(t0, t1, dim, blur)] darken/blur windows behind explainer cards (0..1)
    keywords   caption words painted yellow (UPPERCASE as displayed)
    fix        {"wrong": "right"} lower-case transcription fixes
    join_next  tokens that merge with the following token ("RISE" -> "RISE 261")
    join_prev  tokens that merge into the previous one ("kWh" -> "261 kWh")
    caption_style "hormozi" | "minimal" | "cinematic" (CAPTION_STYLES); accent = keyword colour
    look       colour grade name from GRADES ("clean_warm", "teal_orange", "moody", "vivid_day", "none")
    flashes    [t, ...] glow "flash cut" hits (bloom + white burst) — pair each with a "flash" SFX
    sfx        [(t, "category_or_file", gain_db), ...] mixed into the render; categories resolve to
               <sfx_dir>/<category>*.wav|mp3 (user-supplied licensed files, e.g. Mixkit/Pixabay/Motion Array)
    """
    def __init__(self, src, words, faces, zoom_keys, scenes=(), ranges=(), motions=(), bg=(), keywords=(), fix=None,
                 join_next=(), join_prev=(), cap_y=CAP_Y, face_anchor=.40, camera="auto", deadzone=.05, max_speed=.22,
                 max_accel=.6, lock_spread=(.14, .09), z_max=1.25, scene_bump=0.0,
                 caption_style="hormozi", accent=YEL, look="none", flashes=(), sfx=(), sfx_dir=None,
                 jumpcuts="auto", cuts=(), jump_zoom=1.07, min_face=40, hide_captions=(), broll=(),
                 caption_anim="group", correct=True, overlays=()):
        # cuts: EVERY keep.json join in the cut timeline. jumpcuts="auto": the engine decides per cut whether a
        # zoom step is needed (visible jump on the same framing) or not (framing already changes, close-up,
        # B-roll, graphic entering, too soon) — see `python project.py cuts`. A list forces those cuts.
        # broll: [dict(t0=, t1=, src="clip.mp4", ss=0, mode="full"|"card", prefer=700, zoom=(1.0, 1.08))]
        #   full = 9:16 cover-crop over the whole frame with a slow push (Ken Burns), 0.2 s cross-fade;
        #   card = inset at CARD_W wide, rounded, same radius/border as cards, placed with slot().
        #   Both get the project's colour look so stock footage matches the speaker's shots.
        # jumpcuts: cut points inside the same shot -> zoom alternates 1.0 / jump_zoom at each one
        # (fakes a 2-camera shoot so jump cuts don't read as glitches). min_face: ignore faces narrower
        # than this (in the 360-px analysis frame) — lower it (~28) when the speakers are small in frame.
        self.auto_jumps = isinstance(jumpcuts, str)
        self.cuts = sorted(set(cuts) | (set() if self.auto_jumps else set(jumpcuts)))
        self.jumps = [] if self.auto_jumps else sorted(jumpcuts); self.jump_zoom = jump_zoom; self.min_face = min_face
        self.hide_caps = list(hide_captions)   # [(t0, t1)] windows where a big title already says the line
        self.broll = []
        for b in broll:
            b = dict(b); b.setdefault("ss", 0); b.setdefault("mode", "full"); b.setdefault("zoom", (1.0, 1.08))
            if b["mode"] == "full":
                b["clip"] = _Clip(b["src"], b["ss"], W, H, True)
            else:
                sw, sh = _probe_size(b["src"]); cw = CARD_W; ch = int(round(cw * sh / sw / 2) * 2)
                ch = min(ch, 720); b["clip"] = _Clip(b["src"], b["ss"], cw, ch, True); b["size"] = (cw, ch)
            self.broll.append(b)
        self.cs = CAPTION_STYLES[caption_style]; self.accent = accent; self.look = look
        # caption_anim: "group" = each caption group enters once and the spoken word is only emphasised
        #   (manual 9.2: do not turn every word into its own animation); "word" = legacy per-word pop.
        # correct: technical colour correction per shot BEFORE the look (manual 11): exposure + white balance
        #   measured on the footage, limited strength so skin stays natural. `python project.py color` shows it.
        self.cap_anim, self.correct, self._corr = caption_anim, correct, None
        # overlays: animated elements from the asset bank (~/reels-banco/motions) or any file:
        #   dict(id="seta_curva" | src="path", t0=3.2, t1=None (= t0 + clip length), cx=540, cy=700 | prefer=700,
        #        w=360, loop=False, speed=1.0, a=1.0). Same rules as motions: one function each, never over a face.
        self.overlays = []
        if overlays:
            try:
                from banco import motions as _bank_motions; bank = _bank_motions()
            except Exception: bank = {}
            for o in overlays:
                o = dict(o)
                if "id" in o and "src" not in o:
                    if o["id"] not in bank: raise KeyError(f"motion '{o['id']}' não está no banco: {sorted(bank)}")
                    o["src"], kind = bank[o["id"]]["path"], bank[o["id"]]["kind"]
                else:
                    kind = "png_seq" if Path(o["src"]).is_dir() else ("gif" if o["src"].lower().endswith(".gif") else "video")
                o["clip"] = _Overlay(o["src"], kind, o.get("w", 360), o.get("loop", False), o.get("speed", 1.0))
                o.setdefault("t1", o["t0"] + o["clip"].dur / o.get("speed", 1.0))
                self.overlays.append(o)
        self.flashes, self.sfx = list(flashes), list(sfx)
        self.sfx_dir = Path(sfx_dir) if sfx_dir else Path.home() / "reels-sfx"
        self.src = src
        probe = subprocess.run([FFM, "-hide_banner", "-i", src], capture_output=True, text=True).stderr
        m = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", probe); self.SW, self.SH = int(m.group(1)), int(m.group(2))
        # base crop window with the OUTPUT aspect: the whole frame for a 9:16 base, a moving 9:16 window over a
        # horizontal source (the virtual camera follows the face across it), and the reverse for 16:9 output.
        self.CW0 = min(self.SW, self.SH * W / H); self.CH0 = self.CW0 * H / W
        d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe); self.dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
        self.zk, self.scenes, self.ranges, self.motions, self.bgw = list(zoom_keys), list(scenes), list(ranges), list(motions), list(bg)
        self.keywords, self.cap_y = {k.upper() for k in keywords}, cap_y
        # Camera ("virtual operator", see style-guide §3): per range decide LOCK (tripod: one framing for the
        # whole stretch) or TRACK (damped spring, dead zone, speed/accel limits). face_anchor = where the face
        # centre sits on screen (0.40 = eyes on the upper third); zoom scales around that point so the face
        # never drifts while zooming. z_max caps every zoom; scene_bump = optional zoom bump on shot changes.
        self.face_anchor, self.cam_mode, self.deadzone = face_anchor, camera, deadzone
        self.max_speed, self.max_accel, self.lock_spread = max_speed, max_accel, lock_spread
        self.z_max, self.scene_bump = z_max, scene_bump
        self.faces = json.load(open(faces))
        self._captions(json.load(open(words, encoding="utf-8")), fix or {}, set(join_next), set(join_prev))
        self._build_focus()
        _CURRENT["reel"] = self; _CURRENT["slots"] = {}
        self.cut_report = self._analyse_cuts() if self.auto_jumps else []
        if self.auto_jumps: self.jumps = [c for c, need, _ in self.cut_report if need]
        _CURRENT["reel"] = self; _CURRENT["slots"] = {}

    # ------------------------------------------------------------ captions
    def _captions(self, raw, fix, jn, jp):
        toks = []
        for w in raw:
            if w["w"].startswith("-") and toks:          # "all" "-in" "-one" -> "all-in-one"
                toks[-1]["w"] += w["w"]; toks[-1]["e"] = w["e"]; continue
            toks.append(dict(w))
        for tk in toks:
            tk["brk"] = tk["w"][-1] in ",.?!"
            core = re.sub(r"[,.;:]", "", tk["w"])
            core = fix.get(core.lower(), core)
            tk["d"] = core.upper() if self.cs["upper"] else core
            tk["d"] = re.sub(r"(?i)\bkwh\b", "kWh", re.sub(r"(?i)\bkw\b", "kW", tk["d"]))
        jn = {x.upper() for x in jn}; jp = {x.upper() for x in jp}
        merged = []
        for tk in toks:
            if merged and (merged[-1]["d"].upper() in jn or tk["d"].upper() in jp):
                m = merged[-1]; m["d"] += " " + tk["d"]; m["e"] = tk["e"]; m["brk"] = tk["brk"]; continue
            merged.append(tk)
        for tk in merged: tk["key"] = tk["d"].upper() in self.keywords
        groups, g = [], []
        mw, mc = self.cs["max_words"], self.cs["max_chars"]
        for tk in merged:
            if g:
                chars = sum(len(x["d"]) + 1 for x in g) + len(tk["d"])
                if len(g) >= mw or chars > mc or g[-1]["brk"] or tk["s"] - g[-1]["e"] > .4:
                    groups.append(g); g = []
            g.append(tk)
        if g: groups.append(g)
        self.groups = []
        for i, g in enumerate(groups):
            nxt = groups[i + 1][0]["s"] - .05 if i + 1 < len(groups) else self.dur
            end = nxt if nxt - g[-1]["e"] < .6 else g[-1]["e"] + .3
            self.groups.append({"s": max(0, g[0]["s"] - .05), "e": end, "w": g})

    def draw_captions(self, ov, t):
        if any(a <= t < b for a, b in self.hide_caps): return
        g = next((g for g in self.groups if g["s"] <= t < g["e"]), None)
        if not g: return
        cs = self.cs; items = []
        for tk in g["w"]:
            if tk["key"]:
                glow = (self.accent[:3] + (150,)) if cs["glow"] else None
                sp = T(tk["d"], cs["ksize"], self.accent, cs["kw"], cs["stroke"], family=cs["kfam"], glow=glow)
                vw = text_w(tk["d"], cs["ksize"], cs["kw"], cs["kfam"])
            else:
                sp = T(tk["d"], cs["size"], cs.get("color", WHITE), cs["w"], cs["stroke"], family=cs["fam"])
                vw = text_w(tk["d"], cs["size"], cs["w"], cs["fam"])
            key = tk["key"]
            mid = glyph_mid(tk["d"], cs["ksize"] if key else cs["size"], cs["kw"] if key else cs["w"],
                            cs["kfam"] if key else cs["fam"], cs["stroke"])
            items.append((tk, sp, vw + 2 * cs["stroke"], mid))
        gap = int(cs["size"] * .4)                     # visible word gap from the font size, not sprite padding
        avail = W - 2 * SAFE_SIDE
        rows = [items]
        if cs.get("lines", 1) == 2 and len(items) > 1 and sum(it[2] for it in items) + gap * (len(items) - 1) > avail:
            # two lines only when one doesn't fit: split where the two widths are most even
            cum = [sum(it[2] for it in items[:i]) for i in range(1, len(items))]
            i = min(range(len(cum)), key=lambda j: abs(cum[j] - (cum[-1] + items[-1][2]) / 2)) + 1
            rows = [items[:i], items[i:]]
        lh = cs["size"] * 1.15
        for ri, row in enumerate(rows):                # one baseline per row, rows centred on cap_y
            self._caption_row(ov, t, g, row, gap, avail, baseline_for(self.cap_y, cs["size"], cs["w"], cs["fam"])
                              + (ri - (len(rows) - 1) / 2) * lh)

    def _caption_row(self, ov, t, g, items, gap, avail, base):
        cs = self.cs
        tot = sum(it[2] for it in items) + gap * (len(items) - 1)
        k = min(1.0, avail / tot)
        x = W / 2 - tot * k / 2
        for tk, sp, vw, mid in items:
            st = g["s"] if self.cap_anim == "group" else tk["s"] - .04
            if t >= st:
                p = (t - st) / (.18 if self.cap_anim == "group" else .16)
                if cs["upper"] and self.cap_anim == "group":   # one entrance per group; spoken word emphasised
                    sc = (.9 + .1 * eo(p)) * k; dy = 0
                    if tk["s"] <= t < tk["e"] + .05: sc *= 1.06
                elif cs["upper"]:                      # legacy: punchy pop per word
                    sc = (.55 + .45 * eback(p)) * k; dy = 0
                    if tk["s"] <= t < tk["e"] + .05: sc *= 1.08
                else:                                  # minimal: soft rise + fade, no bounce
                    sc = k; dy = 14 * (1 - eo(p))
                paste(ov, sp, x + vw * k / 2, base + mid * k + dy, sc, clamp(p * 2.5))
            x += (vw + gap) * k

    # ------------------------------------------------------------ camera
    def _range_idx(self, t):
        for j, r in enumerate(self.ranges):
            if r[0] <= t < r[1]: return j
        return -1

    def _pick(self, fs, mode):
        fs = [f for f in fs if f[2] >= self.min_face]   # ignore background people (small faces)
        if not fs: return None
        f = (min(fs, key=lambda f: f[0]) if mode == "left" else max(fs, key=lambda f: f[0]) if mode == "right"
             else max(fs, key=lambda f: f[2]))
        return f

    def _build_focus(self):
        """Virtual camera operator.
        1. Per range, the chosen face centre at 10 fps -> gap fill (hold last) -> median-of-5 (kills detector spikes).
        2. Mode (AutoFlip-style): LOCK if the face stays within lock_spread (fraction of the frame) for the
           whole range — the crop is fixed on the median position, like a tripod. Otherwise TRACK: a
           critically damped spring with a dead zone (hysteresis), max speed and max acceleration, so moves
           start and stop smoothly and small head motion never moves the frame.
        3. Range boundaries sit on cuts, so the camera re-frames instantly there (reads as a new shot)."""
        kx, ky = self.SW / 360, self.SH / 640          # faces.py analyses a 360x640 frame
        tgt = {}; self.face_raw = {}; self.range_mode = {}
        for ri, rg in enumerate(self.ranges):
            a, b, mode = rg[0], rg[1], rg[2]
            want = rg[3] if len(rg) > 3 else self.cam_mode
            idx_all = [i for i, fr in enumerate(self.faces) if a <= fr["t"] < b]
            # the first ~0.12 s after a boundary can still hold the previous shot's frame (10 fps sampling):
            # build the target from later samples and back-fill those early indices with the first good one.
            idx = [i for i in idx_all if self.faces[i]["t"] >= a + .12] or idx_all
            early = [i for i in idx_all if i not in idx]
            if not idx: continue
            picks = [self._pick(self.faces[i]["f"], mode) if mode else None for i in idx]
            for i, f in zip(idx, picks):
                if f: self.face_raw[i] = [f[0] * kx, f[1] * ky, f[2] * kx, f[3] * ky]
            pts = [((f[0] + f[2] / 2) * kx, (f[1] + f[3] / 2) * ky) if f else None for f in picks]
            if all(p is None for p in pts):
                self.range_mode[ri] = "none"
                for i in idx: tgt[i] = np.array([self.SW / 2, self.SH / 2])
                continue
            last = next(p for p in pts if p is not None)
            for j in range(len(pts)):
                if pts[j] is None: pts[j] = last
                last = pts[j]
            arr = np.array(pts, float)
            if len(arr) >= 5:                                   # median-of-5: remove single-frame detector jumps
                pad = np.pad(arr, ((2, 2), (0, 0)), mode="edge")
                arr = np.stack([np.median(pad[j:j + 5], 0) for j in range(len(arr))])
            spread = (np.percentile(arr, 95, 0) - np.percentile(arr, 5, 0)) / np.array([self.CW0, self.CH0])
            short = (min(b, self.dur) - a) < 3.0 and spread[0] < .30          # short shots: a move can't settle -> hold
            # Is a fixed (tripod) framing enough? Put the crop on the median face and check that the face centre
            # stays inside the good area (12 % side margins, between 12 % and 62 % of the height) for 95 % of the shot.
            z = self.zoom((a + min(b, self.dur)) / 2); cw, ch = self.CW0 / z, self.CH0 / z; med = np.median(arr, 0)
            dx = np.abs(arr[:, 0] - med[0]) / cw; dy = (arr[:, 1] - med[1]) / ch
            fits = (np.percentile(dx, 95) <= .5 - .12 and np.percentile(dy, 95) <= .62 - self.face_anchor
                    and np.percentile(-dy, 95) <= self.face_anchor - .12)
            lock = want == "lock" or (want == "auto" and (short or fits))
            self.range_why = getattr(self, "range_why", {})
            self.range_why[ri] = ("forced" if want != "auto" else "short shot" if short and not fits else
                                  "fixed framing keeps the face in the good area" if fits else
                                  f"subject moves beyond a fixed framing (dx95 {np.percentile(dx, 95):.0%} of width)")
            self.range_mode[ri] = "lock" if lock else "track"
            if lock:
                med = np.median(arr, 0)
                for i in idx: tgt[i] = med
            else:                                               # track: low-pass the target too (sigma 0.6 s)
                if len(arr) > 7:
                    ker = cv2.getGaussianKernel(37, 6).ravel(); pad = np.pad(arr, ((18, 18), (0, 0)), mode="edge")
                    arr = np.stack([np.convolve(pad[:, c], ker, "valid") for c in (0, 1)], 1)
                for i, p in zip(idx, arr): tgt[i] = p
            for i in early: tgt[i] = tgt[idx[0]]
        nf = int(self.dur * FPS) + 2
        self.focus_px = np.zeros((nf, 2)); self.has_face = np.zeros(nf, bool)
        pos = vel = None; moving = False; prev_r = None; dt = 1 / FPS; glide = False
        cuts = [0.0] + list(self.scenes) + list(self.cuts) + list(self.jumps)
        is_cut = lambda t: any(abs(t - c) < 1.5 / FPS for c in cuts)
        dz = self.deadzone * self.CW0; vmax = self.max_speed * self.CW0; amax = self.max_accel * self.CW0
        kk = (2 * math.pi * .55) ** 2; cc = 2 * math.sqrt(kk)          # critically damped spring (~0.55 Hz)
        for n in range(nf):
            t = n / FPS; i0 = int(t * 10); fr = t * 10 - i0
            r = self._range_idx(t)
            p0 = tgt.get(i0); p1 = tgt.get(i0 + 1, p0)
            if self._range_idx(i0 / 10) != r: p0 = p1            # sample belongs to the previous shot: use the next one
            if p1 is not None and self._range_idx((i0 + 1) / 10) != r: p1 = p0
            if p0 is None: target = np.array([self.SW / 2, self.SH / 2])
            else: target = p0 + (p1 - p0) * fr
            mode = self.range_mode.get(r, "none")
            self.has_face[n] = mode in ("lock", "track")
            if r != prev_r and pos is not None and not is_cut(t):
                glide = True                     # range change inside a continuous shot: glide, never snap
            if glide:
                mode = "track"; moving = True
            if pos is None or (r != prev_r and not glide) or mode != "track":
                pos = target.copy(); vel = np.zeros(2); moving = False
            else:
                err = target - pos; dist = float(np.hypot(*err))
                if not moving and dist > dz: moving = True          # hysteresis: start beyond the dead zone,
                if moving and dist < dz * .25 and float(np.hypot(*vel)) < vmax * .05: moving = False   # stop near target
                acc = (kk * err - cc * vel) if moving else (-cc * vel)
                an = float(np.hypot(*acc))
                if an > amax: acc *= amax / an
                vel = vel + acc * dt
                vn = float(np.hypot(*vel))
                if vn > vmax: vel *= vmax / vn
                pos = pos + vel * dt
                if glide and float(np.hypot(*(target - pos))) < dz * .25 and float(np.hypot(*vel)) < vmax * .05:
                    glide = False                # settled on the new framing
            self.focus_px[n] = pos; prev_r = r

    def _face_near(self, t):
        i = min(max(int(round(t * 10)), 0), len(self.faces) - 1)
        fs = [f for f in self.faces[i]["f"] if f[2] >= self.min_face]
        return max(fs, key=lambda f: f[2]) if fs else None

    def _small_gray(self, t):
        fr = next(self.frames(max(0, t), 1), None)
        return None if fr is None else cv2.cvtColor(cv2.resize(fr, (90, 160), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32)

    def _graphic_area(self, t):
        lay = Image.new("RGBA", (W, H))
        for m in self.motions: m(lay, t)
        return float((np.asarray(lay.getchannel("A")) > 40).mean())

    def _graphic_enters(self, c):
        """'enters' when a motion graphic appears around cut c, 'on' when one is already on screen —
        either way it is the focal point, so the camera shouldn't add a zoom step on top of it."""
        before, at, after = self._graphic_area(c - .35), self._graphic_area(c), self._graphic_area(c + .35)
        if after - before > .02: return "enters"
        if at > .03: return "on"
        return None

    def _analyse_cuts(self, min_gap=2.5):
        """Decide, cut by cut, whether a zoom step is needed. A jump cut only looks like a glitch when the
        framing barely changes (same person, same place, same size) — then an 8 % zoom step turns it into a
        'second camera'. If the cut already changes the picture, a zoom adds nothing and just pumps."""
        rows, last = [], -99.0
        for c in self.cuts:
            if c <= .05 or any(abs(c - sc) < .05 for sc in self.scenes):
                continue                                          # real shot changes: a new shot needs no disguise
            a, b = self._face_near(c - .15), self._face_near(c + .15)
            need, why = False, ""
            if a is None or b is None:
                why = "no face on one side (B-roll / turn) - reads as a new shot"
            else:
                fh = max(a[3], b[3]) / 640
                dx = abs((a[0] + a[2] / 2) - (b[0] + b[2] / 2)) / 360; ds = abs(b[3] - a[3]) / max(a[3], 1)
                ga, gb = self._small_gray(c - 2 / FPS), self._small_gray(c + 1 / FPS)
                mad = float(np.abs(ga - gb).mean()) if ga is not None and gb is not None else 0
                if fh > .40: why = f"close-up (face {fh:.0%} of height) - no zoom-in"
                elif dx > .08 or ds > .15 or mad > 25: why = f"framing already changes (shift {dx:.0%}, size {ds:.0%}, diff {mad:.0f})"
                elif self._range_idx(c - .05) != self._range_idx(c + .05) and self.ranges[self._range_idx(c + .05)][2] != self.ranges[self._range_idx(c - .05)][2]:
                    why = "camera already re-frames here (new follow target)"
                elif c - last < min_gap: why = f"too soon ({c - last:.1f}s after the last zoom step)"
                elif self._graphic_enters(c): why = f"a graphic {self._graphic_enters(c)} screen - it is the focal point".replace("enters screen", "enters").replace("on screen", "is on screen")
                else: need, why = True, f"visible jump on the same framing (shift {dx:.0%}, diff {mad:.0f})"
            if need: last = c
            rows.append((c, need, why))
        return rows

    def zoom(self, t):
        z, act = 1.0, None
        for key in self.zk:                  # the key that started most recently wins (overlaps can't delay a cut)
            if t >= key[0]: act = key
        if act:
            t0, t1, z0, z1, f = act
            z = z1 if t >= t1 or t1 <= t0 else z0 + (z1 - z0) * f((t - t0) / (t1 - t0))
        if self.scene_bump:
            for sc in self.scenes:
                if sc <= t < sc + .35: z *= 1 + self.scene_bump * (1 - eo((t - sc) / .35))
        n = sum(1 for j in self.jumps if j <= t)
        if n % 2: z *= self.jump_zoom
        return min(max(z, 1.0), self.z_max)

    def crop(self, t):
        """Anchor-based framing: the focus point is placed at a fixed SCREEN position (face_anchor) and the
        crop is derived from it, so zooming scales around the face instead of sliding it up/down."""
        z = self.zoom(t); cw, ch = self.CW0 / z, self.CH0 / z; s = W / cw
        n = min(int(round(t * FPS)), len(self.focus_px) - 1)
        fx, fy = self.focus_px[n]
        sy = H * (self.face_anchor if self.has_face[n] else .5)
        x0 = clamp(fx - (W / 2) / s, 0, self.SW - cw); y0 = clamp(fy - sy / s, 0, self.SH - ch)
        return x0, y0, s

    def face_box(self, t):
        """Tracked face box in OUTPUT coords (x0,y0,x1,y1) or None — use it to keep graphics off faces."""
        f = self.face_raw.get(int(round(t * 10)))
        if not f: return None
        x0, y0, s = self.crop(t)
        return ((f[0] - x0) * s, (f[1] - y0) * s, (f[0] + f[2] - x0) * s, (f[1] + f[3] - y0) * s)

    def motion_report(self, pan_max=.30, zoom_rate_max=20.0):
        """Measure what the viewer feels: how fast the picture slides (px/s on screen) and scales (%/s),
        ignoring the frames right at cuts (jumps there are intended). Flags: pan > pan_max*W px/s,
        zoom rate > zoom_rate_max %/s, and wobble (direction reversal within 0.6 s)."""
        cuts = sorted(set(round(c, 2) for c in list(self.scenes) + list(self.jumps) + [r[0] for r in self.ranges]))
        near = lambda t: any(abs(t - c) < 2 / FPS for c in cuts)
        if self.cuts:                                   # everything that jumps must sit on a real cut
            off = lambda x: min(abs(x - c) for c in self.cuts)
            for rg in self.ranges[1:]:
                if rg[0] < self.dur and off(rg[0]) > 1.5 / FPS:
                    print(f"  WARN range boundary {rg[0]:.3f}s is not on a cut (nearest {min(self.cuts, key=lambda c: abs(c - rg[0])):.3f}s) -> use cuts.json values")
            for t0, t1, z0, z1, _ in self.zk:
                if t0 == t1 and t0 > 0 and off(t0) > 1.5 / FPS:
                    print(f"  WARN zoom step at {t0:.3f}s is not on a cut (nearest {min(self.cuts, key=lambda c: abs(c - t0)):.3f}s)")
        print("camera per range:")
        for ri, rg in enumerate(self.ranges):
            if rg[0] < self.dur: print(f"  {rg[0]:6.2f}-{min(rg[1], self.dur):6.2f}  follow={rg[2]}  mode={self.range_mode.get(ri, 'none'):5s}  "
                                      f"{getattr(self, 'range_why', {}).get(ri, 'no face (B-roll): hold')}")
        prev = None; vels = []; issues = []; pans = []; zrs = []
        for n in range(int(self.dur * FPS) - 2):
            t = n / FPS; x0, y0, s = self.crop(t); z = self.zoom(t)
            m = min(n, len(self.has_face) - 1)
            sy = H * (self.face_anchor if self.has_face[m] else .5)
            cx, cy = x0 + (W / 2) / s, y0 + sy / s        # source point under the anchor: pure zoom doesn't move it
            if prev is not None and not near(t):
                v = np.array([cx - prev[0], cy - prev[1]]) * s * FPS
                pan = float(np.hypot(*v)); zr = abs(z - prev[2]) / prev[2] * FPS * 100
                pans.append(pan); zrs.append(zr)
                if pan > pan_max * W: issues.append((t, f"fast pan {pan:.0f} px/s"))
                if zr > zoom_rate_max: issues.append((t, f"fast zoom {zr:.0f} %/s"))
                back = [pv for (tt, pv) in vels if t - .6 <= tt <= t - .3]
                if pan > .04 * W and back and any(float(np.dot(v, pv)) < 0 and np.hypot(*pv) > .04 * W for pv in back):
                    issues.append((t, "wobble (direction reversal)"))
                vels.append((t, v)); vels = vels[-30:]
            prev = (cx, cy, z)
        if pans:
            print(f"pan  px/s: p50 {np.percentile(pans, 50):.0f}  p95 {np.percentile(pans, 95):.0f}  max {max(pans):.0f}   (limit {pan_max * W:.0f})")
            print(f"zoom %/s: p95 {np.percentile(zrs, 95):.1f}  max {max(zrs):.1f}   (limit {zoom_rate_max:.0f})")
        merged = []
        for t, msg in issues:
            if merged and msg.split()[0] == merged[-1][2].split()[0] and t - merged[-1][1] < .2: merged[-1][1] = t
            else: merged.append([t, t, msg])
        for a_, b_, msg in merged: print(f"  ISSUE {a_:6.2f}-{b_:6.2f}s  {msg}")
        print("verdict:", "SMOOTH" if not merged else f"{len(merged)} issue(s) — fix before rendering")

    # ------------------------------------------------------------ colour correction (before the look)
    def _build_correction(self):
        """Per shot (between SCENES): white balance from near-neutral pixels (grey world, clipped to +-10 %,
        70 % strength, normalised so no channel goes down) and exposure (brightens dark shots only, max +15 %).
        Gains use a highlight roll-off (255 stays 255) so walls and skies neither clip nor turn grey."""
        bounds = sorted({0.0, self.dur, *[x for x in self.scenes if 0 < x < self.dur]})
        self._corr = []
        for a, b in zip(bounds, bounds[1:]):
            smp = []
            for k in range(5):
                fr = next(self.frames(a + (b - a) * (k + .5) / 5, 1), None)
                if fr is not None: smp.append(cv2.resize(fr, (90, 160), interpolation=cv2.INTER_AREA))
            g, e, note = np.ones(3), 1.0, "sem amostra"
            if smp:
                x = np.concatenate([q.reshape(-1, 3) for q in smp]).astype(np.float32) / 255
                lum = x @ np.float32([.299, .587, .114]); mx, mn = x.max(1), x.min(1); sat = (mx - mn) / (mx + 1e-6)
                neu = x[(sat < .18) & (lum > .2) & (lum < .92)]
                if len(neu) > 200:
                    m = neu.mean(0); g = 1 + (np.clip(m.mean() / m, .9, 1.1) - 1) * .7
                    g = g / g.min()                    # only lift channels: white stays white, nothing gets dimmer
                med = float(np.median(lum)); clip_hi = float((lum > .985).mean())
                if med < .36: e = float(np.clip(.42 / med, 1, 1.15))   # brighten clearly dark shots only;
                # bright high-key scenes (white walls) are left alone - darkening them turns white into grey
                note = f"luma {med:.2f}, neutros {len(neu)}" + (f", {clip_hi:.0%} estourado" if clip_hi > .05 else "")
            x = np.arange(256, dtype=np.float32) / 255; luts = []
            for c in range(3):
                kk = float(g[c] * e)
                y = x * kk / (1 + (kk - 1) * x) if kk > 1 else x * kk
                luts.append(np.clip(y * 255, 0, 255).astype(np.uint8))
            self._corr.append((a, b, tuple(round(float(v), 3) for v in g), round(e, 3), note, luts))

    def color_correct(self, img, t):
        if not self.correct: return img
        if self._corr is None: self._build_correction()
        seg = next((c for c in self._corr if c[0] <= t < c[1]), self._corr[-1])
        return np.dstack([cv2.LUT(img[..., c], seg[5][c]) for c in range(3)])

    def color_report(self):
        if self._corr is None: self._build_correction()
        print(f"correção de cor por plano (antes do look '{self.look}'):")
        for a, b, g, e, note, _ in self._corr:
            print(f"  {a:6.2f}-{b:6.2f}s  ganho RGB {g}  exposição x{e}  ({note})")
        return [dict(t0=a, t1=b, wb_gain=g, exposure=e) for a, b, g, e, _, _ in self._corr]

    def camera(self, frame, t):
        x0, y0, s = self.crop(t)
        M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
        return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def bg_fx(self, img, t):
        dim = max([dm * life(t, a, b, .3, .25) for a, b, dm, _ in self.bgw] + [0])
        blur = max([bl * life(t, a, b, .35, .25) for a, b, _, bl in self.bgw] + [0])
        if blur > .01: img = cv2.addWeighted(img, 1 - blur, cv2.GaussianBlur(img, (0, 0), 22), blur, 0)
        if dim > .01: img = (img * (1 - dim)).astype(np.uint8)
        for sc in self.scenes:
            if sc <= t < sc + .14:
                a = .3 * (1 - (t - sc) / .14); img = cv2.addWeighted(img, 1 - a, np.full_like(img, 255), a, 0)
        for fl in self.flashes:                       # "flash cut": bloom of the highlights + white burst, ~0.25 s
            if fl <= t < fl + .25:
                k = 1 - eo((t - fl) / .25)
                hi = cv2.GaussianBlur(cv2.threshold(img, 150, 255, cv2.THRESH_TOZERO)[1], (0, 0), 28)
                img = cv2.addWeighted(img, 1, hi, 1.4 * k, 0)
                img = cv2.addWeighted(img, 1 - .55 * k, np.full_like(img, 255), .55 * k, 0)
        return img

    # ------------------------------------------------------------ sound effects
    def sfx_report(self):
        """Manual 7.3 / 21: SFX are selective. Warn on density and on sounds placed on plain cuts."""
        msgs = []
        if not self.sfx: return msgs
        per10 = len(self.sfx) / max(self.dur, 1) * 10
        if per10 > 2.0:
            msgs.append(f"SFX: {len(self.sfx)} em {self.dur:.0f}s ({per10:.1f} a cada 10 s) - use só nos eventos-chave (máx ~2/10 s)")
        on_cuts = [t for t, *_ in self.sfx if any(abs(t - c) < .12 for c in self.cuts if c > 0)]
        if len(on_cuts) > 2:
            msgs.append(f"SFX: {len(on_cuts)} sons em cortes simples {['%.1f' % x for x in on_cuts]} - corte não precisa de som")
        return msgs

    def _sfx_file(self, name, t=0.0):
        p = Path(name)
        if p.suffix and p.exists(): return p
        try:
            from banco import sfx_file as _bank_sfx
            hit = _bank_sfx(name, t)
            if hit: return hit
        except Exception: pass
        for ext in ("wav", "mp3", "ogg", "m4a"):
            hits = sorted(self.sfx_dir.glob(f"{name}*.{ext}"))
            if hits: return hits[0]
        return None

    def sfx_track(self, path="sfx.wav"):
        """Render all SFX onto one silent timeline (48 kHz stereo). Returns path or None.
        Missing categories are reported, never invented — ask the user for licensed files."""
        items, miss = [], set()
        for t, name, gain in self.sfx:
            f = self._sfx_file(name, t)
            (items.append((t, f, gain)) if f else miss.add(name))
        if miss: print("SFX missing in ~/reels-banco/sfx/<categoria>/ and", self.sfx_dir, "->", sorted(miss))
        if not items: return None
        cmd = [FFM, "-loglevel", "error", "-y", "-f", "lavfi", "-t", f"{self.dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fl = []
        try: from banco import SFX_CAP as caps
        except Exception: caps = {}
        names = [n for _, n, _ in self.sfx if self._sfx_file(n, _)]
        for i, (t, f, gain) in enumerate(items):
            cmd += ["-i", str(f)]
            cat = names[i] if i < len(names) else ""; d = _probe_dur(str(f)); cap = caps.get(cat, 3.0); pre = ""
            if cat == "riser":                         # a riser leads INTO the event: it ends at t (last `cap` seconds)
                use = min(d, cap); pre = f"atrim=start={d - use:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.15,"
                ms = max(0, int((t - use) * 1000))
            else:                                      # anything else starts at t and never runs past its useful length
                if d > cap: pre = f"atrim=end={cap:.3f},afade=t=out:st={cap - .12:.3f}:d=0.12,"
                ms = max(0, int(t * 1000))
            fl.append(f"[{i + 1}:a]{pre}aresample=48000,aformat=channel_layouts=stereo,volume={gain}dB,adelay={ms}|{ms}[s{i}]")
        fl.append("[0:a]" + "".join(f"[s{i}]" for i in range(len(items))) + f"amix=inputs={len(items) + 1}:normalize=0:duration=first[a]")
        subprocess.run(cmd + ["-filter_complex", ";".join(fl), "-map", "[a]", path], check=True)
        print(f"wrote {path} ({len(items)} sfx)")
        return path

    # ------------------------------------------------------------ compose / io
    def _broll_full(self, img, t):
        for b in self.broll:
            if b["mode"] != "full" or not (b["t0"] <= t < b["t1"]): continue
            fr = b["clip"].frame(t - b["t0"])
            if fr is None: continue
            z0, z1 = b["zoom"]; z = z0 + (z1 - z0) * eio((t - b["t0"]) / max(.01, b["t1"] - b["t0"]))
            M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, z)
            fr = grade(cv2.warpAffine(fr, M, (W, H), borderMode=cv2.BORDER_REFLECT), self.look)
            a = min(eo((t - b["t0"]) / .2), eo((b["t1"] - t) / .2))
            img = cv2.addWeighted(img, 1 - a, fr, a, 0)
        return img

    def _broll_cards(self, ov, t):
        for b in self.broll:
            if b["mode"] != "card" or not (b["t0"] <= t < b["t1"]): continue
            fr = b["clip"].frame(t - b["t0"])
            if fr is None: continue
            cw, ch = b["size"]; a = life(t, b["t0"], b["t1"], .3, .25)
            cy = slot(b["t0"], b["t1"], ch, prefer=b.get("prefer", 700))
            im = Image.fromarray(grade(fr, self.look)).convert("RGBA")
            mask = RR(cw, ch, 40, (255, 255, 255, 255)).getchannel("A"); im.putalpha(mask)
            s = .9 + .1 * eback(prog(t, b["t0"], .4))
            paste(ov, RR(cw + 8, ch + 8, 44, (255, 255, 255, 60)), W / 2, cy, s, a)
            paste(ov, im, W / 2, cy, s, a)

    def _overlays(self, ov, t):
        for o in self.overlays:
            if not (o["t0"] <= t < o["t1"]): continue
            im = o["clip"].frame(t - o["t0"])
            if im is None: continue
            cy = o["cy"] if "cy" in o else slot(o["t0"], o["t1"], o["clip"].h, prefer=o.get("prefer", 700))
            a = o.get("a", 1.0) * min(1, (t - o["t0"]) / .08, (o["t1"] - t) / .08)   # 2-3 frame soft edges
            paste(ov, im, o.get("cx", W / 2), cy, 1.0, a)

    def compose(self, frame, t, debug=False):
        img = self.bg_fx(self._broll_full(grade(self.color_correct(self.camera(frame, t), t), self.look), t), t)
        ov = Image.new("RGBA", (W, H))
        self._broll_cards(ov, t)
        self._overlays(ov, t)
        for m in self.motions: m(ov, t)
        self.draw_captions(ov, t)
        if debug: self._debug(ov, t)
        o = np.asarray(ov, dtype=np.uint16); al = o[..., 3:4]
        return ((img.astype(np.uint16) * (255 - al) + o[..., :3] * al) // 255).astype(np.uint8)

    def _debug(self, ov, t):
        d = ImageDraw.Draw(ov)
        d.rectangle((0, 0, W, SAFE_TOP), fill=(255, 0, 0, 50)); d.rectangle((0, SAFE_BOTTOM, W, H), fill=(255, 0, 0, 50))
        d.line((SAFE_SIDE, 0, SAFE_SIDE, H), fill=(255, 0, 0, 160), width=2); d.line((W - SAFE_SIDE, 0, W - SAFE_SIDE, H), fill=(255, 0, 0, 160), width=2)
        d.line((0, H / 3, W, H / 3), fill=(0, 200, 255, 140), width=2)
        fb = self.face_box(t)
        if fb: d.rectangle(fb, outline=(0, 255, 120, 255), width=4)
        d.text((20, 20), f"{t:.2f}s z={self.zoom(t):.2f}", font=font(36, "Bold"), fill=WHITE)

    def check_collisions(self, t):
        """Warn when a motion graphic covers >10% of the tracked face or leaves the safe area."""
        fb = self.face_box(t); msgs = []
        for name, m in [(m.__name__, m) for m in self.motions] + [("broll_card", self._broll_cards), ("overlay", self._overlays)]:
            lay = Image.new("RGBA", (W, H)); m(lay, t); bb = lay.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
            if not bb: continue
            if bb[1] < SAFE_TOP - 10 or bb[3] > SAFE_BOTTOM + 10 or bb[0] < SAFE_SIDE - 30 or bb[2] > W - SAFE_SIDE + 30:
                msgs.append(f"{t:.2f}s {name}: outside safe area {bb}")
            if fb:
                ix = max(0, min(bb[2], fb[2]) - max(bb[0], fb[0])) * max(0, min(bb[3], fb[3]) - max(bb[1], fb[1]))
                fa = (fb[2] - fb[0]) * (fb[3] - fb[1])
                if fa and ix / fa > .1: msgs.append(f"{t:.2f}s {name}: covers {100 * ix / fa:.0f}% of the face")
        return msgs

    def frames(self, ss=None, n=None):
        cmd = [FFM, "-loglevel", "error"] + (["-ss", str(ss)] if ss is not None else []) + ["-i", self.src] + \
              (["-frames:v", str(n)] if n else []) + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=self.SW * self.SH * 3)
        sz = self.SW * self.SH * 3
        while True:
            b = p.stdout.read(sz)
            if len(b) < sz: break
            yield np.frombuffer(b, np.uint8).reshape(self.SH, self.SW, 3)

    def _sheet(self, tiles, path, cols=6):
        rows = math.ceil(len(tiles) / cols); sheet = Image.new("RGB", (cols * 360, rows * 640))
        for i, tl in enumerate(tiles): sheet.paste(tl, ((i % cols) * 360, (i // cols) * 640))
        sheet.save(path, quality=88); print("wrote", path)

    def cli(self, argv=None):
        """
        preview t1 t2 ... [--debug]   -> preview.jpg (+ collision report)
        strip t0 t1 [step_frames]      -> strip.jpg: consecutive frames to judge smoothness
        check [step]                   -> collision/safe-area report over the whole video
        cuts                           -> per cut: zoom step or not, and why (jumpcuts="auto")
        color                          -> colour correction per shot + color.jpg (antes / corrigido / + look)
        motion                         -> camera QA: lock/track per range, pan & zoom speeds, wobble, verdict
        full out.mp4                   -> final render (audio copied from src, SFX mixed in, sfx.wav kept)
        looks [t]                      -> looks.jpg: the same frame in every colour grade, to pick one with the user
        """
        argv = argv or sys.argv[1:]
        sys.stdout.reconfigure(encoding="utf-8")
        cmd, args = argv[0], [a for a in argv[1:] if not a.startswith("--")]
        debug = "--debug" in argv
        if cmd == "preview":
            tiles = []
            for t in map(float, args):
                tiles.append(Image.fromarray(self.compose(next(self.frames(t, 1)), t, debug)).resize((360, 640), Image.LANCZOS))
                for m in self.check_collisions(t): print("WARN", m)
            self._sheet(tiles, "preview.jpg")
        elif cmd == "strip":
            t0, t1 = float(args[0]), float(args[1]); step = int(args[2]) if len(args) > 2 else 3
            n = int((t1 - t0) * FPS); tiles = []
            for i, fr in enumerate(self.frames(t0, n)):
                if i % step == 0:
                    tiles.append(Image.fromarray(self.compose(fr, t0 + i / FPS, True)).resize((360, 640), Image.LANCZOS))
            self._sheet(tiles, "strip.jpg", cols=min(8, len(tiles)))
        elif cmd == "check":
            step = float(args[0]) if args else .25; t = 0.0; n = 0
            while t < self.dur:
                for m in self.check_collisions(t): print("WARN", m); n += 1
                t += step
            for m in self.sfx_report(): print("WARN", m); n += 1
            print(f"{n} warnings")
        elif cmd == "color":                           # correction per shot + before/after sheet
            self.color_report(); tiles = []
            for a, b, *_ in self._corr:
                t = (a + b) / 2; fr = self.camera(next(self.frames(t, 1)), t)
                for lab, im in (("antes", fr), ("corrigido", self.color_correct(fr, t)),
                                ("+ " + self.look, grade(self.color_correct(fr, t), self.look))):
                    im = Image.fromarray(im).resize((360, 640), Image.LANCZOS)
                    ImageDraw.Draw(im).text((12, 12), f"{t:.1f}s {lab}", font=font(26, "Bold"), fill=WHITE, stroke_width=3, stroke_fill=BLACK)
                    tiles.append(im)
            self._sheet(tiles, "color.jpg", cols=3)
        elif cmd == "full":
            self.render(args[0])
        elif cmd == "cuts":                            # why each cut gets (or doesn't get) a zoom step
            for c, need, why in self.cut_report: print(f"  {c:6.2f}s  {'ZOOM   ' if need else 'no zoom'}  {why}")
            print(f"{sum(1 for r in self.cut_report if r[1])} of {len(self.cut_report)} same-shot cuts get a zoom step")
        elif cmd == "motion":                          # camera QA: modes per range + pan/zoom speed + wobble
            self.motion_report()
        elif cmd == "looks":                           # compare colour grades on one frame
            t = float(args[0]) if args else self.dur / 2
            fr = self.camera(next(self.frames(t, 1)), t); tiles = []
            for name in GRADES:
                im = Image.fromarray(grade(fr, name)).resize((360, 640), Image.LANCZOS)
                ImageDraw.Draw(im).text((12, 12), name, font=font(28, "Bold"), fill=WHITE, stroke_width=3, stroke_fill=BLACK)
                tiles.append(im)
            self._sheet(tiles, "looks.jpg", cols=len(tiles))

    def render(self, out, progress=None):
        """Final render (audio copied from src, SFX mixed in, sfx.wav kept, final_sheet.jpg).
        progress(fraction) is called once per second of video (used by the Cinex app)."""
        enc = subprocess.Popen([FFM, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                                "-i", "-", "-i", self.src, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                                "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
        for i, fr in enumerate(self.frames()):
            enc.stdin.write(self.compose(fr, i / FPS).tobytes())
            if i % 150 == 0: print(f"{i / FPS:.1f}s", flush=True)
            if progress and i % FPS == 0: progress(min(1.0, i / FPS / self.dur))
        enc.stdin.close(); enc.wait(); print("done", out)
        if self.sfx and self.sfx_track("sfx.wav"):   # keep sfx.wav: mix_audio.py --sfx reuses it after Adobe
            tmp = out + ".tmp.mp4"; Path(out).replace(tmp)
            subprocess.run([FFM, "-loglevel", "error", "-y", "-i", tmp, "-i", "sfx.wav", "-filter_complex",
                            "[0:a][1:a]amix=inputs=2:normalize=0:duration=first[a]", "-map", "0:v", "-map", "[a]",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
            Path(tmp).unlink(); print("mixed sfx into", out)
        subprocess.run([FFM, "-loglevel", "error", "-y", "-i", out, "-vf", f"fps=1/2,scale={180 if W < H else 320}:{320 if W < H else 180},tile={9 if W < H else 6}x{4 if W < H else 6}", "-frames:v", "1", "final_sheet.jpg"])
        print("wrote final_sheet.jpg")
