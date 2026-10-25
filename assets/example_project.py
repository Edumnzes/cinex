"""Worked example (v2): one speaker to camera, format `fala_popups`, brand loaded from the saved profile.

Copy this file next to base_1440.mp4 / words.json / faces.json / cuts.json as project.py, set HANDLE and FORMAT,
then rewrite CONFIG (timings come from cuts.json and words.json of YOUR cut) and the MOTIONS.
    python project.py preview 1 5 9 14 20 --debug     key moments of each motion
    python project.py check                           graphics over the face / safe area / SFX density
    python project.py cuts | motion | color           zoom decision per cut, camera QA, colour correction per shot
    python project.py full render.mp4                 then mix_audio.py -> qa.py -> decisions.py -> export_ig.py
For a video with no footage at all (format `motion_explicativo`) start from example_motion.py instead.
"""
import sys, math, json
from pathlib import Path
SKILL = Path.home() / ".claude" / "skills" / "cinex"
sys.path.insert(0, str(SKILL / "scripts"))
from reels_lib import *  # noqa: F401,F403  (Reel, T, RR, paste, pill, icon, easing, colours, bands, ts, slot)
from fx import blur_text                                  # at most 2 text animations per video; this one uses 1
from formats import fmt, tip_card, tip_progress, name_card, cta_follow
from brand import load_brand, rgba

# ============================================================ BRAND + FORMAT (steps A and B of the skill)
HANDLE = "suamarca"                                       # folder ~/instagram-legendas/<handle>/ (marca.json)
B = load_brand(HANDLE)                                    # every key has a default, so this works before onboarding
F = fmt("fala_popups")                                    # structure, cap_y, zoom policy, SFX budget of the format
ACCENT = rgba(B["cores"]["destaque"]); CARD = rgba(B["cores"]["card"], 232); TEXT = rgba(B["cores"]["texto"])
NOME = B["nome"] or "Sua Marca"
STYLE, LOOK = B["edicao"]["caption_style"], B["edicao"]["look"]   # from what already works on the brand's Instagram

# ============================================================ CONFIG (CUT timeline — never type cut times by hand)
CUTS = json.load(open("cuts.json")) if Path("cuts.json").exists() else [0.0]
DUR_HINT = 24.0                                           # length of the example cut; your times come from words.json
SHOT2 = min(CUTS, key=lambda c: abs(c - 7.1))             # a real shot change: take it FROM cuts.json
# Zoom (style-guide §3): slow drift <= ~5 % per shot; a new level only as an instant step on a cut.
ZOOM = [(0.0, SHOT2, 1.0, 1.04, eio),
        (SHOT2, SHOT2, 1.06, 1.06, eo), (SHOT2, 60, 1.06, 1.10, eio)]
SCENES = [SHOT2]                                          # shot changes only (subset of CUTS)
RANGES = [(0, SHOT2, "big"), (SHOT2, 60, "big")]          # who the camera follows; boundaries sit on cuts
BG = [(20.6, 60, .22, 0)]                                 # dim under the CTA
KEYWORDS = set(B["keywords"]) | {"NOVIDADES"}             # highlight only words that help understanding
FIX = dict(B["fix"])                                      # recurring transcription fixes of this brand
# SFX: key events only (manual §5) — hook, main card, CTA. Files: ~/reels-banco/sfx/<category>/.
SFX = [(0.1, "whoosh", -12), (3.6, "pop", -12), (20.7, "whoosh", -10)]
assert len(SFX) / DUR_HINT * 10 <= F["sfx_max_10s"] + .01, "mais SFX do que o formato permite"

# ============================================================ MOTIONS — one per idea, each with a function
def mg_hook(ov, t):                       # 0.1-3.2 s · situates brand + subject while the hook is spoken
    a = life(t, .1, 3.2, .3, .25)
    if a <= 0: return
    pill(ov, W / 2, slot(.1, 3.2, 90, prefer=330), f"{NOME.upper()} RESPONDE", ts("sm"), CARD, TEXT, "pin",
         s=.6 + .4 * eback(prog(t, .1, .35)), a=a)


def mg_quem(ov, t):                       # 3.5-7 s · says who is speaking (lower third from formats.py)
    name_card(ov, t, 3.5, 7.0, "Nome de quem fala", NOME, ACCENT)


TIPS = ((9.0, 12.5, "Primeira ideia em até 8 palavras"),      # each tip enters on the word that starts it
        (12.5, 16.5, "Segunda ideia, curta e concreta"),
        (16.5, 20.4, "Terceira ideia com um número"))
def mg_ideias(ov, t):                     # 9-20.4 s · the three points, numbered, with progress
    for i, (t0, t1, txt) in enumerate(TIPS):
        tip_progress(ov, t, t0, t1, i + 1, len(TIPS), ACCENT)
        tip_card(ov, t, t0, t1, i + 1, len(TIPS), txt, ACCENT)


def mg_cta(ov, t):                        # last seconds · the call to action, after the benefit is clear
    if t < 20.6: return
    blur_text(ov, B["cta"]["principal"], W / 2, 360, ts("2xl"), t, 20.65, TEXT, a=eo(prog(t, 20.6, .3)), stroke=stroke_for(ts("2xl")))
    cta_follow(ov, t, 21.4, 60, B["cta"]["secundario"], ACCENT, prefer=480)


if __name__ == "__main__":
    Reel("base_1440.mp4", "words.json", "faces.json", ZOOM, SCENES, RANGES,
         [mg_hook, mg_quem, mg_ideias, mg_cta], BG, KEYWORDS, FIX,
         cuts=CUTS, jumpcuts="auto",                       # the engine decides, per cut, if a zoom step is needed
         caption_style=STYLE, accent=ACCENT, look=LOOK, cap_y=F["cap_y"],
         sfx=SFX, min_face=30, hide_captions=[(20.6, 60)],   # the CTA title already shows that line
         # overlays=[dict(id="seta_curva", t0=9.2, cx=760, cy=820, w=320)],   # motions from ~/reels-banco/motions
         ).cli()
