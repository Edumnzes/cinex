# Motion em HTML (HyperFrames) — protótipo

Elementos de motion escritos em HTML + GSAP e renderizados com o [HyperFrames](https://github.com/heygen-com/hyperframes)
(HeyGen, Apache-2.0) em vídeo com transparência (MOV ProRes 4444), que o motor do Cinex sobrepõe ao vídeo
(`Reel(..., overlays=[dict(src="out.mov", t0=..., cx=540, cy=960, w=1080)])`).

Por quê: tipografia de designer, máscaras, molas e 3D (CSS 3D / three.js) com qualidade de referência — o motion
desenhado em Python é parte da "cara de IA".

## Ambiente (uma vez por computador)
- Node.js 22+ e FFmpeg + FFprobe no PATH (`winget install --id Gyan.FFmpeg -e --source winget`).
- `npm install hyperframes` numa pasta fora do OneDrive (ex.: `~/cinex-hf`) e `npx hyperframes browser ensure`
  (baixa o Chrome de renderização, ~110 MB, Google Chrome for Testing).
- Sempre com a telemetria desligada: `HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1`.

## Renderizar
Copie o HTML para um projeto HyperFrames (com a pasta `fonts/` ao lado) e rode:
`npx hyperframes render . --format mov -o out.mov --fps 30`

## Modelos usados na exportação (`templates/`)
`_base.html` (fontes, GSAP local, tela transparente do tamanho do elemento) + um arquivo por tipo, com as seções
`<!--CSS-->`, `<!--BODY-->`, `<!--JS-->` e marcadores `$TEXT`, `$TEXT2`, `$WORDS`, `$N`, `$DUR`, `$OUT`, `$ACCENT`:
titulo, topico, nome, citacao, frase e cta (seguir/salvar). `scripts/motion_html.py` preenche, renderiza em MOV com
alfa (~10 s por elemento) e guarda em cache por conteúdo (`~/reels/<projeto>/motion_cache/`). Na exportação do app,
cada elemento vira uma sobreposição posicionada pelo motor longe do rosto; se o HyperFrames não estiver instalado ou
um elemento falhar, ele usa o motion clássico (`formats.py`). No app: aba Motion › Motor › HTML / Clássico.

## Protótipos
- `enfase.html` — estilo "autoridade editorial": linha pequena + palavra de ênfase grande em serifa itálica que sobe
  da máscara com mola e leve inclinação 3D, e um traço desenhado embaixo. 4 s renderizam em ~16 s num i5 sem placa dedicada.
