"""Format templates (references/formatos.md) — defaults + the motion pieces each format uses.

    from formats import *            # after `from reels_lib import *`
    F = fmt("lists_rankings")        # official profile from conhecimento/formatos.json (duration, cap_y, zoom, sfx budget...)

The 8 profiles are versioned and change only through an approved proposal (scripts/aprendizado.py). For the rules
that apply to one video (brand and project preferences on top of the profile) use `aprendizado.py regras`.

Every helper draws one element for the window [t0, t1) with the standard enter/exit (life()), sizes from ts(),
placement with slot() when it can collide with a face. Call them from the project's mg_* functions, e.g.
    def mg_tips(ov, t):
        for i, (t0, t1, txt) in enumerate(TIPS): tip_card(ov, t, t0, t1, i + 1, len(TIPS), txt)
Keep the manual's rules: every element has a function; one animated focal point at a time.
"""
import json, math
from pathlib import Path
from PIL import ImageDraw
from reels_lib import (W, H, CAP_Y, YEL, GRN, RED, WHITE, BLACK, NAVY, GRAY, T, RR, paste, pill, text_w, ts,
                       stroke_for, life, prog, eo, eback, slot, glyph_mid, baseline_for)

CATALOG = Path(__file__).resolve().parent.parent / "conhecimento" / "formatos.json"


def formats():
    return json.loads(CATALOG.read_text(encoding="utf-8"))["formatos"]


def fmt(fid):
    f = formats()
    if fid not in f: raise KeyError(f"formato '{fid}' não existe: {sorted(f)}")
    return dict(f[fid], id=fid)


def wrap(text, size, maxw, weight=None, family="sans"):
    """Greedy word wrap measured with the real font (no guessed widths)."""
    lines, cur = [], ""
    for w in text.split():
        nxt = (cur + " " + w).strip()
        if cur and text_w(nxt, size, weight, family) > maxw: lines.append(cur); cur = w
        else: cur = nxt
    return lines + ([cur] if cur else [])


def _enter(t, t0, d=.35): return eo(prog(t, t0, d))


# ---------------------------------------------------------------- fala / dicas
def tip_card(ov, t, t0, t1, n, total, text, accent=YEL, prefer=480):
    """Numbered tip: number badge inside the card on the left, text left-aligned beside it. Enters rising;
    the number pops. Card 860 wide (inside the 88-px side margins)."""
    a = life(t, t0, t1, .3, .2)
    if a <= 0: return
    size = ts("lg"); cw = 860; b = 92; tx = (W - cw) / 2 + 40 + b + 32; lines = wrap(text, size, cw - (tx - (W - cw) / 2) - 40, "ExtraBold")
    lh = int(size * 1.2); h = max(b + 48, lh * len(lines) + 56); cy = slot(t0, t1, h, prefer=prefer); dy = 30 * (1 - _enter(t, t0))
    paste(ov, RR(cw, int(h), 36, NAVY, (255, 255, 255, 40), 2), W / 2, cy + dy, a=a)
    bs = .5 + .5 * eback(prog(t, t0 + .08, .35)); bx = (W - cw) / 2 + 40 + b / 2
    paste(ov, RR(b, b, b // 2, accent), bx, cy + dy, bs, a)
    paste(ov, T(str(n), ts("xl"), BLACK, shadow=False), bx, baseline_for(cy + dy, ts("xl")) + glyph_mid(str(n), ts("xl")), bs, a)
    for i, ln in enumerate(lines):
        ly = cy + dy - (len(lines) - 1) * lh / 2 + i * lh
        paste(ov, T(ln, size, WHITE, "ExtraBold", shadow=False), tx, baseline_for(ly, size, "ExtraBold") + glyph_mid(ln, size, "ExtraBold"), a=a, ax=0)


def tip_progress(ov, t, t0, t1, n, total, accent=YEL, y=300):
    """Small progress dots (tip n of total) in the top band — tells the viewer how much is left."""
    a = life(t, t0, t1, .25, .2)
    if a <= 0: return
    gap = 34; x0 = W / 2 - (total - 1) * gap / 2
    for i in range(total):
        on = i < n; r = 22 if i == n - 1 else 14
        paste(ov, RR(r, r, r // 2, accent if on else (255, 255, 255, 110)), x0 + i * gap, y, a=a)


def chapter_label(ov, t, t0, t1, text, accent=YEL, prefer=330):
    """Story chapter chip ("O PROBLEMA", "A VIRADA") — orients the viewer in a long narrative."""
    a = life(t, t0, t1, .3, .25)
    if a <= 0: return
    pill(ov, W / 2, slot(t0, t1, 80, prefer=prefer), text, ts("sm"), NAVY, accent, s=.7 + .3 * eback(prog(t, t0, .35)), a=a)


def quote_card(ov, t, t0, t1, text, author="", accent=YEL, prefer=520):
    """Key sentence as a serif-italic quote (story climax, testimonial punchline). Captions should be hidden
    in this window (hide_captions) so the line isn't shown twice."""
    a = life(t, t0, t1, .4, .3)
    if a <= 0: return
    size = ts("xl"); lines = wrap("“" + text + "”", size, 820, "Bold Italic", "serif"); lh = int(size * 1.2)
    h = lh * len(lines) + (70 if author else 20); cy = slot(t0, t1, h, prefer=prefer)
    for i, ln in enumerate(lines):
        pp = prog(t, t0 + i * .1, .4)
        paste(ov, T(ln, size, WHITE, "Bold Italic", stroke=stroke_for(size) // 2, family="serif"),
              W / 2, cy - h / 2 + lh / 2 + i * lh + 16 * (1 - eo(pp)), a=a * eo(pp))
    if author:                                    # on a dark pill: readable on light and dark footage
        pill(ov, W / 2, cy + h / 2 - 20, "— " + author, ts("xs"), NAVY, accent, a=a * _enter(t, t0 + .3))


# ---------------------------------------------------------------- prova
def name_card(ov, t, t0, t1, name, role="", accent=YEL, prefer=1110):
    """Lower-third for the person speaking (testimonial / interview): accent bar + name + role."""
    a = life(t, t0, t1, .35, .25)
    if a <= 0: return
    nw = max(text_w(name, ts("lg")), text_w(role, ts("sm"), "Bold") if role else 0) + 124   # 60 left (bar) + 64 right
    cy = slot(t0, t1, 150, prefer=prefer); x0 = (W - nw) / 2; dx = -40 * (1 - _enter(t, t0))
    paste(ov, RR(int(nw), 150 if role else 100, 28, NAVY), W / 2 + dx, cy, a=a)
    paste(ov, RR(10, 110 if role else 64, 5, accent), x0 + 34 + dx, cy, a=a)
    paste(ov, T(name, ts("lg"), WHITE, shadow=False), x0 + 60 + dx, cy - (22 if role else 0), a=a, ax=0)
    if role: paste(ov, T(role, ts("sm"), GRAY, "Bold", shadow=False), x0 + 62 + dx, cy + 34, a=a, ax=0)


def before_after(ov, t, t0, t1, before, after, label="", unit="", prefer=560):
    """Proof card: red 'antes' vs green 'depois' (e.g. conta R$ 890 -> R$ 49). The 'depois' side enters later."""
    a = life(t, t0, t1, .35, .25)
    if a <= 0: return
    cy = slot(t0, t1, 300, prefer=prefer)
    if label: paste(ov, T(label, ts("sm"), WHITE, "Bold"), W / 2, cy - 180, a=a * _enter(t, t0))
    for i, (tag, val, col, tt) in enumerate((("ANTES", before, RED, t0), ("DEPOIS", after, GRN, t0 + .6))):
        p = prog(t, tt, .4)
        if p <= 0: continue
        x = W / 2 + (i - .5) * 440; s = .7 + .3 * eback(p)
        paste(ov, RR(400, 240, 36, NAVY, col[:3] + (220,), 4), x, cy, s, a)
        paste(ov, T(tag, ts("xs"), col, "Bold", shadow=False), x, cy - 74, s, a)
        paste(ov, T(str(val), ts("2xl"), WHITE, shadow=False), x, cy + 4, s, a)
        if unit: paste(ov, T(unit, ts("xs"), GRAY, "Bold", shadow=False), x, cy + 76, s, a)


def react_label(ov, t, t0, t1, text="REACT", sub="", accent=YEL, y=H // 2):
    """Small chip on the split-screen seam naming the reaction (e.g. 'O ESPECIALISTA REAGE')."""
    a = life(t, t0, t1, .3, .25)
    if a <= 0: return
    pill(ov, W / 2, y - 64, text, ts("sm"), accent, BLACK, s=.7 + .3 * eback(prog(t, t0, .35)), a=a)
    if sub: paste(ov, T(sub, ts("xs"), WHITE, "Bold"), W / 2, y - 14, a=a)


def speaker_tag(ov, t, t0, t1, text, side="left", accent=YEL, y=420):
    """Clone format: which 'version' of the person is talking (EU CÉTICO / EU ESPECIALISTA)."""
    a = life(t, t0, t1, .25, .2)
    if a <= 0: return
    x = W * (.28 if side == "left" else .72)
    pill(ov, x, y, text, ts("xs"), accent if side == "right" else NAVY, BLACK if side == "right" else WHITE,
         s=.7 + .3 * eback(prog(t, t0, .3)), a=a)


# ---------------------------------------------------------------- imagem + texto
def big_phrase(ov, t, t0, t1, text, highlight=(), accent=YEL, cy=820, size=None, family="sans"):
    """The single phrase of 'frase de identificação' / 'conteúdo na legenda': centred, wrapped, key words in the
    accent colour, lines rising in sequence. Sits in the middle band; no speech captions in these formats."""
    a = life(t, t0, t1, .5, .35)
    if a <= 0: return
    size = size or ts("2xl"); weight = "Black" if family == "sans" else None
    lines = wrap(text, size, 880, weight, family); lh = int(size * 1.16); hl = {w.lower().strip(".,!?") for w in highlight}
    for i, ln in enumerate(lines):
        pp = prog(t, t0 + i * .14, .45); y = cy - (len(lines) - 1) * lh / 2 + i * lh + 18 * (1 - eo(pp))
        words = ln.split(); gap = size * .28; st = stroke_for(size); base = baseline_for(y, size, weight, family)
        ws = [text_w(w, size, weight, family) for w in words]; x = W / 2 - (sum(ws) + gap * (len(ws) - 1)) / 2
        for w, wd in zip(words, ws):                       # every word on the same baseline
            col = accent if w.lower().strip(".,!?") in hl else WHITE
            paste(ov, T(w, size, col, weight, stroke=st, family=family), x + wd / 2,
                  base + glyph_mid(w, size, weight, family, st), a=a * eo(pp))
            x += wd + gap


def read_caption(ov, t, t0, t1, text="Leia a legenda", accent=YEL, y=1280):
    """'Conteúdo na legenda': sticker pointing down to the post caption."""
    a = life(t, t0, t1, .35, .25)
    if a <= 0: return
    bob = 8 * math.sin(max(0, t - t0) * 4)
    pill(ov, W / 2, y + bob, text, ts("md"), accent, BLACK, s=.6 + .4 * eback(prog(t, t0, .4)), a=a)
    d = ImageDraw.Draw(ov); cx, cy = W / 2, y + 70 + bob; al = int(255 * a)
    d.polygon([(cx - 22, cy), (cx + 22, cy), (cx, cy + 26)], fill=accent[:3] + (al,))


# ---------------------------------------------------------------- recorrência / visual
def series_badge(ov, t, t0, t1, series, episode=None, accent=YEL, y=330):
    """Fixed series identity (same look every episode): 'NOME DA SÉRIE · EP 3'."""
    a = life(t, t0, t1, .3, .25)
    if a <= 0: return
    txt = series.upper() + (f"  ·  EP {episode}" if episode else "")
    pill(ov, W / 2, y, txt, ts("sm"), NAVY, accent, s=.7 + .3 * eback(prog(t, t0, .35)), a=a)


def next_episode(ov, t, t0, t1, text="No próximo episódio…", teaser="", accent=YEL, prefer=520):
    """End card of a series episode: teaser of the next one (drives follows/returns)."""
    a = life(t, t0, t1, .35, .3)
    if a <= 0: return
    cy = slot(t0, t1, 220, prefer=prefer)
    paste(ov, T(text, ts("lg"), WHITE, "Bold Italic", stroke=stroke_for(ts("lg")) // 2, family="serif"), W / 2, cy - 50, a=a)
    if teaser: pill(ov, W / 2, cy + 50, teaser, ts("sm"), accent, BLACK, s=.6 + .4 * eback(prog(t, t0 + .3, .35)), a=a)


def day_title(ov, t, t0, t1, day, subtitle="", accent=WHITE, prefer=520):
    """'Dia 12 / testando…' hook title (gancho visual): big number, small label, italic subtitle."""
    a = life(t, t0, t1, .3, .25)
    if a <= 0: return
    cy = slot(t0, t1, 260, prefer=prefer); p = prog(t, t0, .4)
    big, small = ts("3xl"), ts("xl")                      # hero line: 3xl, never bigger (proportion)
    wl = text_w("dia", small, "Bold Italic", "serif"); wn = text_w(str(day), big); gap = 18
    x0 = W / 2 - (wl + gap + wn) / 2; base = baseline_for(cy - 40, big)
    paste(ov, T("dia", small, accent, "Bold Italic", stroke=3, family="serif"), x0 + wl / 2,
          base + glyph_mid("dia", small, "Bold Italic", "serif", 3), a=a * eo(p))
    paste(ov, T(str(day), big, accent, stroke=stroke_for(big)), x0 + wl + gap + wn / 2,
          base + glyph_mid(str(day), big, None, "sans", stroke_for(big)), .6 + .4 * eback(p), a)
    if subtitle: paste(ov, T(subtitle, ts("lg"), WHITE, "Bold Italic", stroke=stroke_for(ts("lg")) // 2, family="serif"),
                       W / 2, cy + 70, a=a * _enter(t, t0 + .25))


# ---------------------------------------------------------------- CTAs
def cta_save(ov, t, t0, t1, text="Salve para não esquecer", accent=YEL, prefer=420):
    a = life(t, t0, t1, .3, .25)
    if a <= 0: return
    pulse = 1 + .03 * math.sin(max(0, t - t0 - .4) * 6)
    pill(ov, W / 2, slot(t0, t1, 90, prefer=prefer), text, ts("md"), accent, BLACK, s=(.6 + .4 * eback(prog(t, t0, .35))) * pulse, a=a)


def cta_follow(ov, t, t0, t1, text="Siga para mais", accent=YEL, prefer=420):
    a = life(t, t0, t1, .3, .25)
    if a <= 0: return
    pulse = 1 + .03 * math.sin(max(0, t - t0 - .4) * 6)
    pill(ov, W / 2, slot(t0, t1, 90, prefer=prefer), text, ts("md"), accent, BLACK, "plus", s=(.6 + .4 * eback(prog(t, t0, .35))) * pulse, a=a)
