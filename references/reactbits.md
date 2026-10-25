# React Bits → Reels (animation bank)

React Bits (https://reactbits.dev, github.com/DavidHDev/react-bits) is a catalogue of ~170 animated
React components (text animations, animations, backgrounds, components). Licence: **MIT + Commons
Clause** — free for personal and commercial use, but the components may not be redistributed as a
bundle. So this skill ships **no React Bits code**: `scripts/fx.py` re-creates the useful *looks*
natively for video frames, and this file maps the catalogue to what you can use in a reel.

Use it as a **vocabulary**: pick 1–2 text animations per video and repeat them (unity), e.g.
`split_text` for section titles + `count_up` for numbers. Every size still comes from `ts()`.

## Contents
1. Text animations
2. Animations / effects
3. Backgrounds
4. Components (patterns)
5. Using the real components (optional, advanced)

## 1. Text animations
| React Bits | fx.py | Use in reels | Notes |
|---|---|---|---|
| Split Text | `split_text` | hooks, section titles | letters rise + fade, stagger 30 ms |
| Blur Text | `blur_text` | quotes, authority lines | calm, premium; pairs with `minimal` captions |
| Text Type / Text Cursor | `text_type` | "pesquise…", prompts, data | cps 14–22 |
| Decrypted / Scrambled Text / Shuffle | `decrypted_text` | tech specs, codes, numbers | great for inverter/battery specs |
| Shiny Text | `shiny_text` | premium label, brand name | slow sweep (speed .6–1.0) |
| Gradient Text | `gradient_text` | ONE hero word | never body text |
| Rotating Text / Text Loop | `rotating_text` | lists said quickly (solar → bateria → mobilidade) | `pill_bg=NAVY` for chip look |
| Count Up / Counter | `count_up` | kW, kWh, %, R$ | unit one scale step smaller |
| Glitch / Fuzzy Text | — (flash cut + `decrypted_text`) | energetic hooks | use sparingly |
| Stroke Text / Echo Text | `T(..., stroke=…)` outline-only DIY | big background words | translucent behind speaker |
| Circular Text | DIY (rotate chars on a circle) | badge around a logo | — |
| Masked Heading, Fold, Warp, Depth, Particle, Split-Flap, ASCII, Falling, Text Pressure, Variable Proximity, Scroll Float/Reveal/Velocity, Curved Loop, True Focus | not recommended | web/scroll/cursor interactions — no meaning in a linear video, or too heavy |

## 2. Animations / effects
| React Bits | Reels equivalent |
|---|---|
| Fade Content / Animated Content | `life()` + `eo()`/`eback()` entrances (every motion already does this) |
| Electric Border / Star Border / Border Glow | `fx.border_glow` on the hero card |
| Gradual Blur | `BG=[(t0,t1,dim,blur)]` windows (engine) |
| Glare Hover | `shiny_text` / a sweep over a card |
| Noise | subtle grain — not in engine yet; LUT/grade instead |
| Pixel Transition / Halftone Reveal / Dither Veil | transition ideas between B-roll and speaker — do in NLE, or ask to implement |
| Logo Loop | partner/brand marquee — DIY: row of logos scrolling with `paste()` |
| Cursor effects (Glow, Swarm, Target, Ghost, Blob, Splash), Magnet, Click Spark, Image Trail | web-only (need a cursor) |

## 3. Backgrounds (title cards, interstitials, end cards)
| React Bits | fx.py | When |
|---|---|---|
| Aurora / Soft Aurora | `aurora(t, colors)` | opening title card, quote screen — use brand/palette colours |
| Dot Grid / Grid Scan / Ripple Grid | `dot_grid(t)` | tech/engineering explainers, behind charts |
| Light Rays, Beams, Particles, Galaxy, Hyperspeed, Silk, Plasma, Iridescence, Prism, Liquid Chrome, Lightning… | not built | ask to implement one, or render the real one (§5); keep ≤ 2–3 s, behind text only |
Paste a background layer first inside a motion (`ov.alpha_composite(aurora(t))`), usually with
`BG=[(t0, t1, .6, 1.0)]` so the footage underneath is dimmed/blurred.

## 4. Components → reel patterns
| React Bits | Pattern in this skill |
|---|---|
| Counter | `count_up` in a navy card |
| Stepper / Animated List | staggered pills (e.g. DIVULGAR → CONECTAR → INFORMAR) |
| Profile Card | guest name card (icon + name + @handle) |
| Magic Bento / Spotlight Card / Chroma Grid | icon tiles row (módulos · inversores · estruturas) |
| Card Swap / Stack / Bounce Cards | product cards replacing each other on each spec |
| Tilted / Reflective / Glass Surface | not recommended (3D/light interaction reads poorly at phone size) |

## 5. Using the real components (optional, advanced)
If the user explicitly wants an exact React Bits look the engine doesn't have: install the component
into **their own** small Vite/React project with the site's shadcn/jsrepo command (the code then lives
in their project, which the licence allows), render it on a transparent 1080x1920 page, capture frames
with a headless browser at 30 fps (e.g. Playwright, stepping the animation clock), encode as a
transparent MOV/PNG sequence and overlay it with ffmpeg. This is slower and needs Node — only do it when
the look matters more than time, and never copy the component source into this skill.
