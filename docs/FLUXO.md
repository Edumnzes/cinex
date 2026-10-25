# Fluxo completo — do vídeo bruto à entrega

Este documento descreve tudo o que acontece quando a skill recebe um vídeo, em que ordem,
com quais ferramentas e por quê. Os caminhos citados são relativos à pasta do projeto do
vídeo (`~/reels/<nome>/`), salvo indicação.

## Visão geral

```
vídeo bruto (.MOV/.MP4)
  │
  ├─ A. Perfil da marca ─ brand.py · briefing · Instagram (leitura) → perfil.md · video.md · marca.json
  ├─ B. Formato ──────── 3 recomendados ou lista completa (13)     → template + compose.py se preciso
  ├─ C. Banco ────────── referências do formato · fontes · motions · sons (~/reels-banco)
  ├─ 1. Análise ──────── transcribe.py · energy.py · faces.py  →  mapa + perguntas
  ├─ 1b. Plano ───────── objetivo · mensagem · estrutura · sequência  →  decisoes.json
  ├─ 2. Corte ────────── plan_cut.py · cut.py · transcribe.py  →  base_1440.mp4 + cuts.json
  ├─ 3. Áudio ────────── conector Adobe (Enhance Speech)       →  speech.wav + background.wav
  ├─ 4. Direção ──────── style/visual references · looks       →  estilo de legenda + cor
  ├─ 5. Projeto ──────── project.py (reels_lib + fx)           →  câmera, legendas, motions, SFX
  ├─ 6. QA ───────────── preview · check · cuts · motion       →  ajustes
  ├─ 7. Render ──────── project.py full · mix_audio.py        →  final.mp4
  ├─ 8. QA + nota ───── qa.py · decisions.py                  →  qa.json · decisoes.json
  └─ 9. Entrega ─────── export_ig.py                          →  Reel · capa · grade · Stories
```

## A. Perfil da marca (sempre primeiro; completo só na 1ª vez)

Procedimento completo em `references/onboarding.md`.

1. `brand.py show <arroba>` verifica o que já existe em `~/instagram-legendas/<arroba>/`.
2. **Já existe** → lê `perfil.md`, `video.md` e `marca.json`, resume em 2–3 linhas e pergunta só
   se algo mudou.
3. **Não existe** → briefing curto (até 8 perguntas em 2 rodadas, com opções pré-preenchidas pelo que
   já se sabe) + análise do Instagram no navegador, com o login feito pela própria pessoa:
   perfil, grade de Reels, "Ver insights" de 8–12 Reels, insights da conta e 3–5 Reels assistidos.
   Só leitura; senha nunca é digitada; sem navegador, usa prints.
4. Grava `video.md` (números, o que funciona, direção de edição) e `marca.json` (padrões da edição).

Como o perfil entra na edição:

| Campo | Onde é usado |
|---|---|
| `transcricao_termos` | `--prompt` do transcribe.py (grafia de marca, produtos, cidades) |
| `edicao.caption_style`, `edicao.look` | direção visual (etapa 4) |
| `edicao.duracao_alvo_s`, `gancho`, `evitar` | escolha das frases e abertura (etapa 2) |
| `cores`, `fontes`, `logo`, `cta` | `project.py` via `load_brand()` (etapa 5) |
| correções da pessoa | gravadas de volta no `marca.json` / `video.md` |

Ao entregar, `brand.py log` registra o vídeo em `videos.md`.

## B. Formato do vídeo (escolhido pelo usuário)

Logo depois do perfil da marca, o Claude olha o material gravado e recomenda **3 dos 13 formatos**
(`references/formatos.md`), com o motivo de cada um; a pessoa escolhe ou pede a lista completa. O formato define
estrutura, montagem, duração, ritmo, posição da legenda, política de zoom, orçamento de SFX e os motions
(`scripts/formats.py`). Se o material não serve (ex.: Clone sem câmera fixa), a skill entrega o guia de gravação.

Formatos com várias fontes são montados primeiro com `scripts/compose.py` e o resultado entra no fluxo normal:
- `split` — React: referência em cima (áudio −14 dB), reação embaixo centrada no rosto; legenda na emenda.
- `clone` — dois takes com câmera fixa unidos por uma emenda suave; avisa se a câmera mexeu.
- `assemble` — clipes em sequência (9:16), com ou sem narração separada (voiceover, frase, conteúdo na legenda, Dia X).
Todos limpam a marcação de rotação dos vídeos de celular (senão o player gira a imagem de novo).

## C. Banco do usuário (`~/reels-banco`)

Logo após a escolha do formato, a skill lê `referencias/<formato>/referencias.md`, abre até 3 links (só leitura)
e extrai o padrão — gancho, ritmo, texto na tela, motions, sons, duração, CTA — que passa a guiar o plano e a
edição. Fontes do banco viram famílias de texto; motions com transparência são sobrepostos (`overlays`); sons
saem de `sfx/<categoria>/`. `banco.py check` valida tudo (inclusive recusa motion sem transparência).

## 0. Preparação (uma vez por computador)

`scripts/setup_env.py` cria o ambiente Python em `~/reelsenv` com:

| Pacote | Uso |
|---|---|
| faster-whisper | transcrição com tempo por palavra |
| opencv-python | leitura de vídeo, detecção de rosto (modelo YuNet em `assets/yunet.onnx`) |
| pillow, numpy | desenho de legendas/gráficos e processamento de imagem |
| imageio-ffmpeg | binário do ffmpeg (sem instalação no sistema) |
| truststore | usa os certificados do sistema (evita erro de SSL com antivírus/proxy) |

Problemas já tratados: caminhos longos no Windows, OpenCV sem cascatas Haar, ausência de ffmpeg.

## 1. Análise

| Ferramenta | Entrada → saída | O que faz |
|---|---|---|
| `transcribe.py RAW.MOV words_raw.json --prompt "..."` | vídeo → palavras com início/fim/confiança | Whisper com lista de termos da marca para acertar grafias. Re-transcreve sozinho trechos > 5 s sem fala (o Whisper às vezes pula introduções ruidosas). |
| `energy.py RAW.MOV` | vídeo → trechos de baixa energia | Volume em blocos de 50 ms; baixa energia = pausa ou respiração. Com intervalos (`40.0-44.5`) mostra o detalhe para posicionar cortes. |
| `faces.py RAW.MOV faces_raw.json --sheet sheet_raw.jpg` | vídeo → rostos por instante + miniaturas | Detector YuNet; a folha de miniaturas permite "ver" o vídeo inteiro de uma vez. |

Com isso o Claude entrega ao usuário: 3–6 pontos principais do vídeo e um **mapa**
(tempo | plano | fala | tratamento sugerido), e pergunta só o que não dá para deduzir
(nome do evento, @, dados na tela, estilo). Se o usuário já pediu "pode seguir", segue direto.

## 1b. Plano editorial (antes de cortar)

Regra do manual: objetivo → mensagem → narrativa → execução → distribuição, nesta ordem.
Antes de escolher as frases, o Claude define e mostra junto com o mapa:
- objetivo, público, **mensagem central** (uma frase) e duração alvo;
- **estrutura**: problema → solução, antes → depois, curiosidade → revelação, afirmação → prova,
  erro → correção, processo → resultado ou história → aprendizado;
- **sequência**: gancho → contexto → desenvolvimento → prova → conclusão → CTA, com o trecho de fala
  de cada parte. Frases podem ser reordenadas; o CTA só vem depois do benefício.

`decisions.py init` cria o `decisoes.json`, onde o plano é registrado.

## 2. Corte

1. **Escolha das frases** (`phrases.json`, tempos do vídeo bruto) conforme o plano: tira cabeça/rabo mortos,
   falsas largadas, a metade errada de autocorreções, repetições e agradecimentos longos.
   Uma frase forte do meio pode virar abertura de 1–2 s (cold open).
2. **`plan_cut.py`** remove as pausas **sem função** dentro de cada frase → `keep.json`. Pausas de ênfase,
   humor ou emoção são mantidas com `{"hold": [t], "why": "..."}` (até 0,7 s). Cada trecho removido e cada
   pausa mantida vão para o registro com o motivo.
3. **Ajuste fino**: o Whisper "estica" palavras sobre pausas, então cada corte é conferido no
   mapa de energia para cair no vale entre duas palavras.
4. **`cut.py`** renderiza o corte com fades de 20–30 ms nas emendas (sem estalos) e grava
   `cuts.json` — o início exato (em quadros) de cada trecho no vídeo cortado.
5. **Verificação**: o corte é transcrito de novo (`words.json`). Palavra estranha = corte
   comeu o som → alarga 0,1–0,2 s e repete. Erros restantes de grafia são corrigidos à mão.
6. **Base em alta** (`base_1440.mp4`, 1440×2560, CRF 14) + `faces.json` na linha do tempo cortada.
   `detect_cuts.py` confere os cortes visíveis na imagem.

A partir daqui **todos os tempos são da linha do tempo cortada**.

## 3. Áudio — Adobe Podcast Enhance Speech

Só a voz vai para a nuvem; a imagem nunca sai do computador.

1. O ffmpeg do ambiente extrai `voice.wav` (mono, 48 kHz) do corte.
2. Conector Adobe: `adobe_mandatory_init` → `asset_initialize_file_upload` →
   envio com `curl PUT` → `asset_finalize_file_upload` → `media_enhance_speech(assetId)`.
3. A tarefa é assíncrona; o resultado chega por um painel (widget), lido com
   `read_widget_context`. As URLs expiram, então as faixas `enhanced_speech` e `background`
   são baixadas imediatamente (`speech.wav`, `background.wav`).
4. Depois do render, `mix_audio.py` junta voz + ambiente (0,1–0,2 em interiores, 0,25–0,4 em
   feiras) + SFX e normaliza em **duas passadas** para **−14 LUFS**, pico ≤ −1 dBTP, medidos no arquivo de saída.
   Música ainda não é configurada.

Sem o conector, o áudio original é apenas normalizado.

## 4. Direção visual

Escolhida pelo conteúdo, a partir da tabela em `references/visual-references.md`:

| Conteúdo | Legenda | Cor |
|---|---|---|
| Feira / produto / B2B | hormozi | none ou vivid_day |
| Autoridade / consultor | minimal | clean_warm ou natural |
| Marca pessoal enérgica | minimal (laranja) + flash cuts | teal_orange |
| Reflexivo / storytelling | minimal com acentos manuscritos | moody |
| Externo / cinematográfico | cinematic | vivid_day |

`python project.py looks <t>` mostra o mesmo quadro em todos os ajustes de cor para decidir
com o usuário. Ajustes novos podem ser criados no próprio `project.py`
(ex.: `GRADES["natural"] = dict(...)`).

## 5. Projeto de edição (`project.py`)

Cópia adaptada de `assets/example_project.py`, usando `scripts/reels_lib.py` e `scripts/fx.py`.

| Bloco | Conteúdo |
|---|---|
| `ZOOM` | Deriva lenta ≤ ~5 % por plano; "punch-ins" só como degrau instantâneo num corte (+8–12 %) |
| `SCENES`, `RANGES` | Trocas de plano e quem a câmera acompanha — limites sempre sobre cortes do `cuts.json` |
| `cuts=..., jumpcuts="auto"` | O motor decide em cada corte se precisa de um degrau de zoom para disfarçar o "tranco" |
| `KEYWORDS`, `FIX` | Palavras destacadas e correções de grafia nas legendas |
| `STYLE`, `LOOK`, `accent` | Estilo de legenda, ajuste de cor e cor de destaque |
| `BG` | Escurecer/desfocar o fundo sob cards grandes |
| `mg_*(ov, t)` | Uma função por ideia, entrando na palavra que ilustra; `slot()` posiciona fora do rosto |
| `SFX`, `FLASHES` | Sons só nos eventos-chave (gancho, card principal, prova, CTA; ~2 a cada 10 s no máximo); flash cuts |
| `broll=[...]` | Cortes para imagens de apoio (tela cheia ou card) |

Regras de design (em `references/style-guide.md`): escala tipográfica fixa (`ts("xs"…"3xl")`),
contorno proporcional (`stroke_for`), legendas pequenas no terço inferior (y 1300), área segura
do Instagram (topo ≥ 270 px, base ≥ 480 px), um ponto focal por vez, no máximo 2 animações de
texto por vídeo.

### Câmera virtual (automática)
- **LOCK** (tripé) quando o rosto fica numa área pequena ou o plano é curto; senão **TRACK**:
  mediana + filtro passa-baixa nas detecções e mola criticamente amortecida com zona morta,
  velocidade e aceleração máximas.
- O rosto fica ancorado a 40 % da altura (olhos no terço superior) e o zoom escala em torno dele.
- Zoom máximo 1,25 (nitidez e proporção).

## 6. Controle de qualidade

| Comando | Critério |
|---|---|
| `preview t1 t2 … --debug` | Quadros de entrada/meio/saída de cada motion; zonas inseguras em vermelho |
| `check` | Nenhum card sobre o rosto de quem fala; nada fora da área segura; SFX dentro do limite |
| `cuts` | Justificativa de zoom/sem zoom em cada corte |
| `motion` | Pan p95 < 60 px/s, zoom < 5 %/s, sem "vai-e-volta" → veredito **SMOOTH** |
| `strip t0 t1` | Quadros consecutivos em volta de um corte para achar solavancos |

O Claude abre e olha cada imagem gerada antes de seguir.

## Cor: correção antes do look

O motor corrige cada plano antes de aplicar o look (`correct=True`): balanço de branco pelos tons neutros
(limitado, sem rebaixar o branco) e exposição só quando o plano está escuro — cena clara nunca é escurecida.
`python project.py color` mostra os ganhos por plano e gera `color.jpg` (antes / corrigido / + look).

## 7. Render e entrega

1. `python project.py full render.mp4` — ~4 min por minuto de vídeo; gera `final_sheet.jpg`
   (uma miniatura a cada 2 s) e `sfx.wav` se houver efeitos.
2. `mix_audio.py render.mp4 speech.wav final.mp4 --bg background.wav --bg-level X [--sfx sfx.wav]`.
3. **Controle de qualidade** — `qa.py final.mp4 --project project.py`: resolução, proporção, fps, duração,
   áudio, volume integrado, pico real, distorção, quadros pretos, imagem congelada, decodificação até o fim e
   (via `project.py check`) gráficos sobre rosto, safe zone e excesso de SFX. Qualquer FALHA bloqueia a entrega.
4. **Registro e nota** — o Claude completa o `decisoes.json` (cortes e pausas com motivo, B-roll, legendas,
   áudio, cor, motion com função, SFX, erros a rejeitar) e dá a **nota 0–5** nas 10 dimensões do manual
   (narrativa, ritmo, áudio, texto, motion, cor, composição, plataforma, acessibilidade, objetivo).
   `decisions.py check` precisa dizer COMPLETAS; `decisions.py archive` guarda uma cópia na pasta da marca.
5. **Instagram** — `export_ig.py`: Reel em Downloads, capa, prévia do recorte 3:4 da grade do perfil e,
   se passar de 60 s, partes para Stories cortadas nos pontos de corte.
6. `brand.py log <arroba> "..."` registra a entrega no histórico da marca.
7. Resposta ao usuário (inclui a tabela de notas e o veredito do QA): onde está o arquivo e a duração; tabela tempo | o que foi adicionado;
   o que foi cortado; pontos para conferir (dados técnicos na tela, @, SFX faltando);
   o que o motor não faz e melhoraria o vídeo; oferta de ajustes.

A pasta do projeto é mantida: ajustes são feitos editando `project.py` e renderizando de novo,
sem refazer análise nem corte.

## Arquivos gerados por projeto

| Arquivo | Origem |
|---|---|
| `words_raw.json`, `faces_raw.json`, `sheet_raw.jpg` | análise do bruto |
| `phrases.json`, `keep.json`, `cuts.json` | plano de corte |
| `cut_1080.mp4`, `base_1440.mp4`, `words.json`, `faces.json`, `sheet.jpg` | corte |
| `voice.wav`, `speech.wav`, `background.wav` | áudio |
| `project.py` | edição |
| `preview.jpg`, `strip.jpg`, `looks.jpg`, `final_sheet.jpg` | conferência |
| `render.mp4`, `final.mp4`, `sfx.wav` | saída |
| `color.jpg` | correção de cor |
| `qa.json`, `decisoes.json` | controle de qualidade, registro de decisões e notas |
