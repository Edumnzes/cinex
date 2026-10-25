"""RSD (desligamento rápido) — motion explicativo, só texto na tela, marca fictícia "Sol Exemplo".
Conteúdo-base: explicação de @infinitienergybrasil / @joao.growsolar (reescrita, sem áudio nem imagem deles).
Estilo: referências de motion limpo (fundo claro, 1 cor de marca, cards, tipografia cinética) + diagramas de
sistema solar com fluxo CC/CA e mudança de estado.
"""
import sys, math
from functools import lru_cache
from PIL import Image, ImageDraw
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "cinex" / "scripts"))
from motion_lib import *  # noqa

# ============================================================ ROTEIRO (texto = narração)
TXT = dict(
    A="As placas transformam a luz do sol em energia.",
    B="Essa energia desce até o inversor…",
    C="…e segue para a casa e para a rede.",
    D="Agora imagine um foco de incêndio.",
    E="O bombeiro desliga o inversor.",
    F="Mas a energia vem de cima para baixo: o telhado continua energizado.",
    G="Cada placa gera cerca de 40 V.",
    H="10 placas em série somam 400 V no telhado.",
    I="O RSD fica embaixo de cada placa.",
    J="No desligamento, ele corta a energia placa por placa.",
    K="A tensão não se soma. Telhado seguro.",
)
HL = dict(A={"sol": GOLD}, B={"inversor…": INK}, F={"energizado": DANGER, "cima": DANGER, "baixo": DANGER},
          G={"40": DC, "v": DC}, H={"400": DANGER, "v": DANGER}, I={"rsd": GOLD}, J={"placa": SAFE},
          K={"seguro": SAFE})
# timeline: hook, title, then one window per sentence (reading time), then claim cards and CTA
T0 = {}; t = 8.0
for k in "ABCDEFGHIJK":
    T0[k] = (t + .2, t + .2 + read_time(TXT[k])); t = T0[k][1]
    if k in "CFHK": t += .2                                   # small breath between chapters
S1, S2 = (0.0, 4.3), (4.3, 8.0)
OUT = T0["K"][1]                                              # diagram leaves
L0, M0, CTA0 = OUT + .3, OUT + 3.7, OUT + 7.6
DUR = CTA0 + 4.6
A0, B0, C0, D0, E0, F0, G0, H0, I0, J0, K0 = (T0[k][0] for k in "ABCDEFGHIJK")
INV_OFF, RSD_CUT = E0 + 1.1, J0 + 1.2                         # the two switch moments

# ============================================================ LAYOUT — a house in section (8-px grid, safe area)
# roof with the 10 modules, inverter on the inside wall, appliances on an AC bus, grid pole outside on the right
ROOF = [(210, 392), (750, 392), (850, 672), (110, 672)]       # trapezoid (front view of the roof face)
WALL = (160, 680, 800, 1150)                                  # house body
PW, PH, PGAP = 100, 64, 12
PCOLS = [256 + i * (PW + PGAP) for i in range(5)]
PROWS = [446, 566]
INVX, INVY = 250, 900
BUSY, APPY = 985, 1076
APPS = ((340, "fridge"), (480, "tv"), (720, "lamp"))
POLEX = 915
TXTY = 1310
P_DC = dense([(INVX, 672), (INVX, 854)], r=0)
P_BUS = dense([(INVX, 946), (INVX, BUSY), (POLEX, BUSY), (POLEX, 1012)])
P_DROPS = [dense([(x, BUSY), (x, 1030)], r=0) for x, _ in APPS]
WIRES = Wires((200, 660, 970, 1040))
WHITE_ = (255, 255, 255, 255); ROOFC = (54, 60, 74, 255)


@lru_cache(maxsize=2)
def house_sprite():
    """Static house in section: roof face, walls, floor and ground line. Drawn once at 3x, placed at y=370."""
    k = 3; oy = 370; im = Image.new("RGBA", (W * k, 820 * k)); d = ImageDraw.Draw(im)
    P = lambda x, y: (x * k, (y - oy) * k)
    d.line([P(70, 1154), P(1010, 1154)], fill=HAIR, width=6 * k)                                  # ground
    d.rounded_rectangle((*P(WALL[0], WALL[1]), *P(WALL[2], WALL[3])), 10 * k, fill=(255, 255, 255, 255), outline=INK, width=8 * k)
    d.polygon([P(*q) for q in ROOF], fill=ROOFC)
    d.line([P(*q) for q in ROOF] + [P(*ROOF[0])], fill=INK, width=8 * k, joint="curve")
    d.line([P(WALL[0] - 20, 1150), P(WALL[2] + 20, 1150)], fill=INK, width=10 * k)                # floor slab
    return im.resize((W, 820), Image.LANCZOS)


@lru_cache(maxsize=16)
def g_app(kind, on=True, s=92):
    """Appliance glyphs: fridge | tv | lamp. on = powered (accent light), off = grey."""
    im = Image.new("RGBA", (s * 3, s * 3)); d = ImageDraw.Draw(im); k = 3
    ink = INK if on else MUTE; lit = AC if on else (200, 204, 211, 255); w = 6 * k
    if kind == "fridge":
        d.rounded_rectangle((24 * k, 6 * k, 68 * k, 88 * k), 8 * k, fill=(255, 255, 255, 255), outline=ink, width=w)
        d.line((24 * k, 36 * k, 68 * k, 36 * k), fill=ink, width=w)
        d.line((34 * k, 18 * k, 34 * k, 28 * k), fill=ink, width=w); d.line((34 * k, 46 * k, 34 * k, 62 * k), fill=ink, width=w)
        d.ellipse((54 * k, 14 * k, 62 * k, 22 * k), fill=lit)
    elif kind == "tv":
        d.rounded_rectangle((8 * k, 14 * k, 84 * k, 64 * k), 8 * k, fill=(lit[:3] + (70,)) if on else (232, 234, 238, 255), outline=ink, width=w)
        d.line((46 * k, 64 * k, 46 * k, 78 * k), fill=ink, width=w); d.line((28 * k, 80 * k, 64 * k, 80 * k), fill=ink, width=w)
    else:                                                                                         # pendant lamp
        d.line((46 * k, 0, 46 * k, 26 * k), fill=ink, width=w)
        d.pieslice((20 * k, 22 * k, 72 * k, 74 * k), 180, 360, fill=ink)
        if on: d.ellipse((30 * k, 44 * k, 62 * k, 76 * k), fill=lit[:3] + (90,))
        d.ellipse((38 * k, 46 * k, 54 * k, 62 * k), fill=lit)
    return im.resize((s, s), Image.LANCZOS)


def diagram(ov, t):
    inv_on = t < INV_OFF; hot = F0 <= t < RSD_CUT; cut = eo(prog(t, RSD_CUT, .5)); off = eo(prog(t, INV_OFF, .4))
    ph = prog(t, A0, .5)
    if ph <= 0: return
    paste(ov, house_sprite(), W / 2, 370 + 410 + 24 * (1 - eo(ph)), a=eo(ph))                     # the house rises in
    ps = prog(t, A0 + .35, .5)
    if ps > 0: paste(ov, g_sun(104), 112, 352, (.5 + .5 * eback(ps)) * (1 + .04 * math.sin(t * 2.2)), eo(ps))
    # ---- wires inside the house
    WIRES.begin()
    pdc = eo(prog(t, B0, .7))
    if pdc > 0:
        col = lerp(lerp(DC, DANGER, eo(prog(t, F0, .4))), HAIR, cut)
        wdt = 11 + (4 * (0.5 + 0.5 * math.sin((t - F0) * 9)) if hot else 0)
        WIRES.line(P_DC, col, wdt, 0, pdc)
        if pdc >= 1 and cut < 1: WIRES.dots(P_DC, t, col, n=2, speed=120, r=11, a=1 - cut)
    pac = eo(prog(t, C0, .9))
    if pac > 0:
        col = lerp(AC, HAIR, off)
        WIRES.line(P_BUS, col, 11, 0, pac)
        for pth in P_DROPS: WIRES.line(pth, col, 11, 0, eo(prog(t, C0 + .35, .4)))
        if pac >= 1 and off < 1: WIRES.dots(P_BUS, t, AC, n=4, speed=170, r=11, a=1 - off)
    WIRES.end(ov)
    # ---- modules on the roof (+ series links, 40 V, RSD)
    for r, y in enumerate(PROWS):
        for c, x in enumerate(PCOLS):
            i = r * 5 + c; p = prog(t, A0 + .3 + i * .04, .35)
            if p <= 0: continue
            paste(ov, g_panel(PW, PH, "hot" if hot else "on"), x, y, .6 + .4 * eback(p), eo(p))
            if c < 4 and cut < 1 and p >= 1: paste(ov, RR(PGAP, 8, 4, DANGER if hot else DC), x + (PW + PGAP) / 2, y, a=1 - cut)
            pv = prog(t, G0 + .15 + i * .07, .3)
            if pv > 0: label(ov, "40 V", x, y, ts("xs"), WHITE_, a=eo(pv))
            pr = prog(t, I0 + .2 + i * .07, .35)
            if pr > 0:
                cy = y + PH / 2 + 6 + 15
                paste(ov, RR(PW, 30, 9, lerp(GOLD, SAFE, cut)), x, cy, .5 + .5 * eback(pr), eo(pr))
                label(ov, "RSD", x, cy, 22, INK, a=eo(pr))
    # ---- inverter on the wall, with its switch (and the rapid-shutdown switch later)
    pi = prog(t, B0 - .25, .4)
    if pi > 0:
        paste(ov, g_inverter(84, 96, inv_on), INVX, INVY, .6 + .4 * eback(pi), eo(pi))
        label(ov, "INVERSOR", INVX + 62, INVY - 22, ts("xs"), ax=0, a=eo(pi))
        label(ov, "ligado" if inv_on else "desligado", INVX + 62, INVY + 20, ts("sm"), SAFE if inv_on else MUTE, "Bold", ax=0, a=eo(pi))
    pe = eo(prog(t, E0, .35))
    if pe > 0:
        label(ov, "CHAVE", 576, INVY - 46, ts("xs"), a=pe); toggle(ov, 576, INVY + 8, 1 - off, on=SAFE, w=104, h=54)
    pj = eo(prog(t, J0, .35))
    if pj > 0:
        label(ov, "RSD", 712, INVY - 46, ts("xs"), INK, a=pj); toggle(ov, 712, INVY + 8, cut, on=SAFE, w=104, h=54)
    # ---- appliances + grid pole
    pa = prog(t, C0 - .2, .4)
    if pa > 0:
        for n, (x, kind) in enumerate(APPS):
            pp = prog(t, C0 - .2 + n * .08, .4)
            if pp > 0: paste(ov, g_app(kind, off < 1), x, APPY, .6 + .4 * eback(pp), eo(pp))
        paste(ov, g_tower(112, INK if off < 1 else MUTE), POLEX, 1066, .6 + .4 * eback(pa), eo(pa))
        label(ov, "REDE", POLEX, 1132, ts("xs"), a=eo(pa))
    pf = prog(t, D0 + .25, .4)
    if pf > 0: paste(ov, g_flame(104), 600, 1092, (.4 + .6 * eback(pf)) * (1 + .06 * math.sin(t * 13)), eo(pf))
    # ---- state tags in the stretch between the roof and the inverter
    if F0 + .3 <= t < RSD_CUT:
        p = prog(t, F0 + .3, .35); pill(ov, 520, 718, "ENERGIZADO", ts("sm"), DANGER, WHITE_, "bolt", s=.6 + .4 * eback(p), a=eo(p))
    if t >= RSD_CUT + .3:
        p = prog(t, RSD_CUT + .3, .35); pill(ov, 520, 718, "SEGURO", ts("sm"), SAFE, WHITE_, "check", s=.6 + .4 * eback(p), a=eo(p))
    if H0 + .2 <= t < RSD_CUT:
        p = prog(t, H0 + .2, .35); v = int(round(400 * eo(prog(t, H0 + .5, .9)) / 40) * 40)
        pill(ov, 520, 786, f"10 × 40 V = {v} V", ts("sm"), INK, WHITE_, s=.6 + .4 * eback(p), a=eo(p))
    if t >= RSD_CUT + .45:
        p = prog(t, RSD_CUT + .45, .35); pill(ov, 520, 786, "40 V por placa", ts("sm"), INK, WHITE_, s=.6 + .4 * eback(p), a=eo(p))


CHAPTERS = (("COMO FUNCIONA", A0, T0["C"][1]), ("O PROBLEMA", D0, T0["F"][1]), ("A CONTA", G0, T0["H"][1]), ("A SOLUÇÃO", I0, T0["K"][1]))


def draw(ov, t):
    # 1. hook
    ktext(ov, t, .2, S1[1], "Desligou o inversor.", 800, ts("2xl"), weight="Bold", maxw=900)
    b = ktext(ov, t, 1.5, S1[1], "O telhado continua energizado?", 940, ts("xl"), MUTE, "SemiBold", {"energizado?": DANGER})
    # 2. title
    if S2[0] <= t < S2[1]:
        out = eo(prog(t, S2[1] - .28, .28)); p = prog(t, S2[0] + .1, .45)
        paste(ov, T("RSD", ts("3xl"), INK, "Black", shadow=False), W / 2, 760 - 22 * out, .7 + .3 * eback(p), eo(p) * (1 - out))
    ktext(ov, t, S2[0] + .5, S2[1], "Rapid Shutdown", 852, ts("md"), MUTE, "Medium")
    ktext(ov, t, S2[0] + 1.0, S2[1], "desligamento rápido", 940, ts("xl"), INK, "Bold")
    chip(ov, t, S2[0] + 1.7, S2[1], "ITEM DE SEGURANÇA", W / 2, 1050, GOLD, INK, ts("sm"))
    # 3-6. the system
    if A0 - .1 <= t < OUT + .5:
        ex = eo(prog(t, OUT, .45))
        if ex > 0:
            lay = Image.new("RGBA", (W, H)); diagram(lay, t)
            lay.putalpha(lay.getchannel("A").point(lambda v: int(v * (1 - ex)))); ov.alpha_composite(lay, (0, int(-30 * ex)))
        else:
            diagram(ov, t)
    for name, a, b in CHAPTERS: chip(ov, t, a, b, name, W / 2, 296, INK, (255, 255, 255, 255), ts("xs"))
    for k in "ABCDEFGHIJK": ktext(ov, t, T0[k][0], T0[k][1], TXT[k], TXTY, ts("lg"), INK, "SemiBold", HL.get(k), maxw=880)
    pk = prog(t, K0 + 1.2, .35)
    if 0 < pk and t < OUT: paste(ov, g_check(56), W / 2, TXTY + 96, .5 + .5 * eback(pk), eo(pk) * (1 - eo(prog(t, OUT - .28, .28))))
    # 7. claims (as stated in the base video — the brand confirms the normative basis)
    b = ktext(ov, t, L0, M0, "Hoje, instalar o RSD é obrigatório.", 800, ts("2xl"), INK, "Bold", {"obrigatório.": INK}, maxw=860)
    if b and t < M0 - .3:                                    # circle only the last line ("é obrigatório.")
        lw = text_w("é", ts("2xl"), "Bold") + ts("2xl") * .28 + text_w("obrigatório.", ts("2xl"), "Bold"); ly = b[3] - ts("2xl") * 1.24 / 2
        ring(ov, t, L0 + 1.1, (W / 2 - lw / 2, ly - 40, W / 2 + lw / 2, ly + 44), GOLD, pad=(36, 10))
    if M0 <= t < CTA0:
        if card(ov, W / 2, 800, 880, 300, t, M0, a=1 - eo(prog(t, CTA0 - .28, .28))):
            pass
    ktext(ov, t, M0 + .15, CTA0, "Sem ele, a seguradora pode recusar a cobertura.", 800, ts("lg"), INK, "SemiBold",
          {"recusar": DANGER, "cobertura.": DANGER}, maxw=760)
    # 8. CTA
    ktext(ov, t, CTA0 + .1, DUR + 1, "Seu sistema tem RSD?", 760, ts("2xl"), INK, "Bold", {"rsd?": GOLD})
    p = prog(t, CTA0 + 1.1, .4)
    if p > 0:
        pulse = 1 + .025 * math.sin(max(0, t - CTA0 - 1.6) * 6)
        pill(ov, W / 2, 900, "Fale com a Sol Exemplo", ts("md"), GOLD, INK, s=(.6 + .4 * eback(p)) * pulse, a=eo(p))
    p = prog(t, CTA0 + 1.6, .4)
    if p > 0: label(ov, "@solexemplo", W / 2, 1000, ts("sm"), MUTE, "SemiBold", a=eo(p))


# SFX only on key events (manual 5): 9 sounds in 62 s. A riser leads into the rapid-shutdown switch.
SFX = [(0.2, "whoosh", -12),                 # hook
       (S2[0] + .1, "pop", -12),             # title RSD
       (A0, "whoosh", -14),                  # the house rises in
       (INV_OFF, "click", -10),              # inverter switch off
       (RSD_CUT, "riser", -16),              # ...leads into
       (RSD_CUT, "click", -10),              # the rapid-shutdown switch
       (RSD_CUT + .3, "ding", -12),          # SEGURO
       (L0, "whoosh", -12),                  # "é obrigatório"
       (CTA0 + 1.1, "pop", -12)]             # CTA button

if __name__ == "__main__":
    print(f"duração {DUR:.1f}s · inversor off {INV_OFF:.1f}s · RSD {RSD_CUT:.1f}s · saída {OUT:.1f}s") if len(sys.argv) > 1 and sys.argv[1] == "times" else None
    Motion(draw, DUR, BG, sfx=SFX).cli() if not (len(sys.argv) > 1 and sys.argv[1] == "times") else print({k: tuple(round(x, 1) for x in v) for k, v in T0.items()})
