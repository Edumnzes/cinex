# Reels style guide — references, numbers and why

Read this before planning motions/zooms for a new video. Everything here is tuned for
1080x1920 @ 30 fps, talking-head + B-roll content (trade shows, product demos, interviews).

> **Manual de edição prevalece.** Onde este guia divergir de `references/manual-edicao.md` (pausas com função, SFX seletivo, legenda por grupo, correção antes do look), vale o manual.

## Contents
1. Reference editors (what to borrow)
2. Pacing & retention
3. Smoothing rules (camera + animation)
4. Framing
5. Layout, spacing, hierarchy
6. Captions
7. Motion-graphic patterns (catalogue)
8. Audio
9. Sources

## 1. Reference editors
| Reference | Borrow | Avoid |
|---|---|---|
| Alex Hormozi | word-by-word captions, ALL CAPS, yellow keyword, thick stroke | emojis on every line (reads cheap for B2B) |
| Ali Abdaal | clean animated text, icons that explain, subtle SFX on the key animations | long flat talking-head stretches |
| Iman Gadzhi | fast cuts, Montserrat, punch-ins on impact lines | heavy glitch transitions |
| MrBeast | something changes on screen every 2–4 s, no dead air | shouting pace — keep it credible for technical audiences |
Techniques: J-cut / L-cut (audio leads/lags the picture across a shot change), speed ramp on
B-roll, alternating 10–15 % punch-ins across jump cuts (fakes a 2-camera shoot), Ken Burns on shots without faces.

## 2. Pacing & retention
- Hook in the first 3 s: a question or promise on screen + the event/brand badge. Primary keyword on screen in the first 3 s (on-screen text is OCR-indexed for search/Explore).
- Something relevant changes every few seconds (a caption group, a card, a shot change) — but retention is not
  frantic editing: keep a shot while it still informs, never cut so fast that understanding suffers (manual §3).
- Each graphic enters on the word it illustrates and leaves before the topic changes. Graphics must clarify, prove, compare or add context — never decorate.
- Explainer "interstitial" (blurred/darkened background + big card) goes over B-roll, where no face is lost.
- CTA in the last ~3 s.

## 3. Smoothing rules — camera = a calm human operator
Research: Google AutoFlip (stationary / panning / tracking decided per scene; tripod-like when the subject is
still), Grundmann et al. "Auto-Directed Video Stabilization with Robust L1 Optimal Camera Paths" (paths made of
static, constant-velocity and smooth-acceleration segments, never a jittery chase), Premiere Auto Reframe
("Slower motion" preset for talking heads: nearly static, few keyframes), virtual-operator write-ups (dead
zone ~5 %, damped spring with speed/acceleration caps, face margin, eyes on the upper third), 1€ filter (low
cut-off when slow = no jitter). In practice animated zoom/tracking reads as unnatural ("estranho") on talking heads → be conservative.

Camera (engine, automatic)
- Per range the engine picks **LOCK** (one fixed framing for the whole shot = tripod) when the face stays within
  ~14 % × 9 % of the frame, or the shot is shorter than 3 s; otherwise **TRACK**: median-of-5 + 0.6 s low-pass on
  the detections, then a critically damped spring (~0.55 Hz) with a 5 % dead zone and hysteresis, max speed 22 %
  of the frame width/s and max acceleration 60 %/s². Force per range with a 4th tuple item: `(t0, t1, "left", "lock")`.
- **Face anchor**: the face centre is pinned to 40 % of the screen height (eyes on the upper third) and every zoom
  scales around that point — the face never slides while zooming.
- **Range boundaries only on cuts** (keep.json joins). Switching who the camera follows mid-shot is a visible jump.
  If a boundary can't sit on a cut (the camera itself pans away), the engine glides to the new framing instead of
  snapping — but never switch the followed person inside one continuous shot just because they are mentioned:
  there-and-back within a few seconds reads as wobble (`motion` flags it). Use a name card instead.
- `scene_bump` is off by default (the zoom "bounce" on shot changes read as a glitch).

Zoom (you write it in `ZOOM`)
- Slow drift inside a shot: ≤ ~5 % over the whole shot with `eio` (e.g. 1.04 → 1.08). Ken Burns on B-roll ≤ 8 %.
- **Punch-ins only on cuts** (t0 == t1 at a keep.json join), +8–12 %, on the emphasis word. Never an animated
  punch (the old 150–250 ms `eexpo` zooms read as "estranho"). ≥ 3 s between punches.
- Close-ups (face taller than ~40 % of the frame): zoom 1.0–1.04, no punches.
- `z_max` 1.25 caps everything (sharpness + proportion). Jump-cut alternation (`jumpcuts`, 1.07) stays: it happens on cuts.

When is a zoom NEEDED? (not every cut — the user was explicit)
A zoom is a tool with one job each time; if it has no job, leave the camera alone.
| Situation | Zoom? | Why |
|---|---|---|
| Jump cut, same framing (person barely moved, picture almost identical) | YES, one 7–8 % step | hides the "tranco"; reads as a second camera |
| Cut that already changes the framing (person moved/turned, size changed, big pixel change) | no | the cut itself is the change; a zoom just pumps |
| Cut into / out of B-roll, or no face on one side | no | reads as a new shot already |
| The camera re-frames onto another person at that cut | no | the re-frame is the change |
| A graphic enters or is on screen (card, title, CTA, hero line) | no | one focal point — the graphic is it |
| Close-up (face > 40 % of the height) | no zoom-in | no room; proportion first |
| < 2.5 s after the previous zoom step | no | pumping; keep the previous level |
| Emphasis word (number, promise, punchline) with a cut ≤ 0.5 s before it and none of the above | optional editorial punch (+8–12 %) in `ZOOM`, max ~1 per 8 s | emphasis — the only zoom *you* add by hand |
The engine applies the table automatically for jump cuts (`cuts=CUTS` from cuts.json, `jumpcuts="auto"`) and explains
every decision with `python project.py cuts`. Read it; override with a list only if you disagree.

When is TRACKING needed?
- Only when a fixed framing would let the face leave the good area (12 % side margins, face centre between 12 %
  and 62 % of the height) — the engine tests exactly that per range and prints why (`motion`).
- A person walking/turning, the camera operator panning away, or a long shot with drift → track (damped).
- Talking head, seated/standing interview, short shots (< 3 s) → lock. Never track just because it's available.

QA — run before every render: `python project.py motion`
- Prints LOCK/TRACK per range, pan speed on screen (limit 0.30 × width/s ≈ 324 px/s) and zoom rate (limit 20 %/s)
  measured at the face anchor, and **wobble** (direction reversals within 0.6 s). Target verdict: SMOOTH.
  Typical good numbers: pan p95 < 60 px/s, zoom max < 5 %/s.

Animation
- Enter 250–400 ms (ease-out back for pops, ease-out cubic/expo for slides); exit 200–250 ms.
- Stagger elements of one card by 80–150 ms. Nothing appears/disappears in < 6 frames.
- Counters: count up over ~0.7 s with ease-out; bars grow staggered 25 ms each.
- One motion curve family for the whole video (consistency reads as "designed").

## 4. Framing
- Eyes near the upper-third line (y ≈ 600–700). Engine default `face_y=.17` places the face above centre.
- Head room: never crop the top of the head on punch-ins; if the face is near the frame top, lower the zoom instead.
- Look room: more free space on the side the speaker looks at.
- Two-shots: follow whoever is speaking (`left`/`right` ranges); switch ranges only at cuts or on a punch-in so the move reads as a camera change.
- Graphics never cover the active speaker's face. Use `slot()` and run `check`.
  When a close-up face fills the middle band: compact card BELOW the face (chest) or small chips ABOVE the head; save big cards for B-roll.
- If the speaker is already very close to the lens (face box taller than ~40 % of the frame), don't punch in
  there at all — hold zoom ≈ 1.0 for that stretch. Zooming a close-up leaves no free band for graphics and the
  face gets cramped; `check` will flag it. Proportion first: shrink the camera, not the cards.

## 5. Layout, spacing, hierarchy — graphic-design principles
Based on Figma's 13 principles of graphic design (https://www.figma.com/pt-br/resource-library/principios-do-design-grafico/).
The user's standing request: **proportion matters most — nothing oversized, captions low and smaller.**

- **Proportion / hierarchy** — every size comes from `TYPE` (modular scale ×1.25, base 32):
  `2xs 20 · xs 26 · sm 32 · md 40 · lg 50 · xl 62 · 2xl 78 · 3xl 98`.
  Captions = `xl` (62). Card titles `lg`, labels `xs`, pills `sm` (`md` for the one key pill),
  hook/section titles `2xl`, and `3xl` only for the single hero line of the video (captions hidden then).
  Max 3 levels on screen at once; adjacent levels only (don't put a 3xl next to an xs).
- **Stroke** scales with size: `stroke_for(size)` (~9 %). A fixed 10 px outline on small text looks heavy.
- **Whitespace / proximity** — 8 px grid; ≥ 40 px between unrelated blocks, 16–24 px inside a group;
  ≥ `CAP_GAP` (96 px) between any card and the caption line (`slot()` enforces it). Related items
  (icon + label, title + subtitle) sit close; unrelated ones far.
- **Alignment / balance** — centre axis for everything in a vertical frame; cards ≤ 904 px wide
  (88 px side margins); left-aligned text only inside a card with a visible left edge.
- **Emphasis / contrast** — one focal point per moment: either a card OR a punch-in OR a flash, not all
  three. Yellow = emphasis; if everything is yellow, nothing is.
- **Repetition / unity** — same radius family (24–48), same navy card, same pill style through the video.
- **Rhythm / movement** — elements enter in reading order (top → bottom, left → right), stagger 80–150 ms.
- Safe area 1080x1920: top ≥ 270 px, bottom ≥ 480 px clear (organic Reels UI), sides ≥ 80 px.
  Bands: top 300–520 (chips, hooks, CTA) · middle 560–1140 (cards) · captions at y = 1300 (lower third).
- Size pills/cards from `text_w()` + padding — never hard-code a width and hope the text fits.
- Palette: navy translucent cards (11,17,32,232), yellow #FFD400 accent, green #22C55E positive, red #EF4444 problem/cost, gray labels.

## 5b. The same principles for motions and B-roll
Proportion, hierarchy, whitespace and unity are not only about text — they govern movement and footage too.

Motions
- **Amplitude ∝ size**: small elements can pop from 0.5→1.0 and travel up to ~1× their height; big cards
  only 0.85→1.0 and ≤ 0.3× their height. Big things moving far look cheap and heavy.
- **Duration ∝ importance**: labels 250 ms in, hero lines 400–500 ms; exits always faster than entrances.
- **One animated focal point** at a time (emphasis): while a card animates, the camera holds; a punch-in
  lands between graphics, not on top of one.
- **Repetition / unity**: the same element type always enters the same way (all pills pop, all cards rise,
  all numbers count). Pick at most 2 text animations from `fx.py` per video (references/reactbits.md).
- **Rhythm**: stagger lists 80–150 ms in reading order; leave ≥ 0.4 s of calm between two motion events.

B-roll (engine `broll=[...]`)
- **Proportion of the frame**: either full-bleed 9:16 (`mode="full"`, cover-crop) or an inset card
  exactly `CARD_W` (904) wide with the cards' radius and hairline border (`mode="card"`) — never an
  arbitrary size or a letterboxed 16:9 floating mid-screen.
- **Duration**: 2–4 s, entering on the word it illustrates (J-cut feel), 0.2 s cross-fade; Ken Burns
  1.0→1.08 max (bigger push = nausea at phone size).
- **Colour unity**: B-roll gets the project's `look`, so stock and phone footage match.
- **Hierarchy**: over full-bleed B-roll allow one label or one chart, not a card stack; captions keep running.
- **Framing**: the subject of the B-roll near the centre/upper third; cards use `slot()` so they avoid the
  speaker's face (the collision check covers B-roll cards too). When a face fills the frame, prefer full-bleed.
- **Sources**: user's own footage first, then licensed banks (Motion Array, Envato, Artlist, Pixabay/Mixkit
  free) — see visual-references §7.

## 6. Captions
- Montserrat Black, UPPERCASE, 62 px (`xl`), 6 px stroke + soft shadow, 1–3 words (≤ 20 chars), centred on y = 1300 (lower third), break on punctuation or gaps > 0.4 s.
- The caption group enters once (180 ms ease-out); the word being spoken is only emphasised (≈6 % bigger), never its own
  animation (manual §7, engine `caption_anim="group"`); keywords in the accent colour only when they help understanding.
- Fix transcription errors via `fix`; merge brand tokens (`join_next={"RISE"}`, `join_prev={"kWh"}`).

## 7. Motion-graphic patterns
| Moment in speech | Pattern | Placement |
|---|---|---|
| Opening | hook question (2 lines) + event pill with icon | top band |
| Topic named ("armazenamento") | chip/pill with icon, 2–3 s | top band |
| Product named | title card (compact while face visible → full card on B-roll) | slot() |
| "Ideal para…" / audience | icon tile + 2-line card sliding in | middle band |
| Technical concept | interstitial explainer: animated chart/diagram, then "solution" and "result" pills | middle band, bg blur .62 |
| Numbers/specs | counter cards with units, battery/progress bar | slot() — above head on close-ups |
| Comparison | two columns, red "antes" vs green "depois" | middle band |
| Closing | "Gostou…?" + pulsing follow pill | slot(), top band |

## 8. Audio
- Cut edits get 20–30 ms fades (cut.py) — no clicks.
- Adobe Podcast Enhance Speech (Adobe connector `media_enhance_speech`) returns speech / background / reverb stems.
  Mix speech + 0.25–0.4 background for location shots (keeps the room real), 0 for indoor.
- Loudness −14 LUFS integrated, true peak ≤ −1 dBTP (mix_audio.py). Instagram normalizes around −14.
- SFX are selective (manual §5): key events only (hook, main card, proof, CTA), ~2 per 10 s max, never on plain cuts,
  licensed files from the user only.

## 9. Sources
- OpusClip — Reels caption best practices: https://www.opus.pro/blog/instagram-reels-caption-subtitle-best-practices
- Ascynd — Hormozi caption specs: https://ascynd.io/en/blog/hormozi-captions
- Outfy — Instagram safe zone 2026: https://www.outfy.com/blog/instagram-safe-zone/
- AIR Media-Tech — retention editing: https://air.io/en/youtube-hacks/advanced-retention-editing-cutting-patterns-that-keep-viewers-past-minute-8
- Pixflow — retention editing: https://pixflow.net/blog/youtube-video-retention-editing/
- Clippie — editing techniques 2026: https://clippie.ai/blog/video-editing-techniques-creators-2026
- Envato — motion graphics for short form: https://elements.envato.com/learn/motion-graphics-for-short-form-video
- Vimeo — lower thirds: https://vimeo.com/blog/post/what-is-lower-thirds
- SendShort — Iman Gadzhi / Ali Abdaal styles: https://sendshort.ai/guides/iman-gadzhi-style/ , https://sendshort.ai/guides/ali-abdaal-style/
- Increditors — Hormozi, Abdaal, MrBeast: https://increditors.com/an-ultimate-guide-to-alex-hormozi-ali-abdaal-and-mr-beast-video-editing-style-and-methods/
