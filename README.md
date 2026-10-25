# Cinex — edição de Reels com o Claude Code

_Antigo **reels-editor**. A partir da v3 a ferramenta se chama Cinex._

Transforma vídeos brutos gravados no celular em **Reels / TikTok / Shorts prontos (1080×1920)**:
corta pausas e respirações, coloca legendas dinâmicas palavra por palavra, faz zooms suaves
acompanhando o rosto, adiciona motion graphics explicativos, corrige a cor e limpa a voz
com o Adobe Podcast Enhance Speech.

> **Código aberto (licença MIT).** Qualquer pessoa pode usar, modificar e distribuir, sem pedir autorização —
> veja [LICENSE.md](LICENSE.md). Como os dados são tratados: [TERMOS_DE_USO.md](TERMOS_DE_USO.md).

---

## Índice
1. [O que a skill faz](#o-que-a-skill-faz)
2. [Requisitos](#requisitos)
3. [Instalação](#instalação)
4. [Como usar](#como-usar)
5. [Estrutura do repositório](#estrutura-do-repositório)
6. [Comandos do projeto](#comandos-do-projeto)
7. [Formatos](#formatos)
8. [Perfil da marca](#perfil-da-marca)
9. [Banco (referências, fontes, motions, efeitos)](#banco-referências-fontes-motions-efeitos)
10. [Efeitos sonoros](#efeitos-sonoros)
11. [Áudio com Adobe Podcast](#áudio-com-adobe-podcast)
12. [Privacidade e segurança](#privacidade-e-segurança)
13. [Limitações](#limitações)
14. [Solução de problemas](#solução-de-problemas)
15. [Documentação detalhada](#documentação-detalhada)
16. [Licença](#licença)

---

## O que a skill faz

| Etapa | Resultado |
|---|---|
| Formato (template) | Você escolhe 1 de 13 formatos (fala + pop-ups, dicas, história, depoimento, react, clone, frase, conteúdo na legenda, voiceover, série, gancho visual, multitarefa e motion explicativo, sem vídeo gravado) |
| Plano editorial | Objetivo, mensagem central, estrutura (problema→solução, antes→depois…) e sequência gancho→CTA antes de cortar |
| Perfil da marca (1ª vez) | Briefing curto + análise dos Reels e Insights do Instagram; salvo no computador e reaproveitado |
| Análise | Transcrição com tempo de cada palavra, mapa de pausas, detecção de rostos, resumo do vídeo |
| Corte | Remove pausas **sem função**, respirações, "éé", falsas largadas e repetições; mantém pausas de ênfase; verifica transcrevendo de novo |
| Câmera virtual | Zooms leves só nos cortes, enquadramento fixo (tripé) ou acompanhamento suave do rosto |
| Legendas | Sincronizadas com a fala, animadas por grupo (sem animar cada palavra), 3 estilos, palavras-chave destacadas |
| Motion graphics | Selos, cards, listas, contadores, gráficos e chamada final — posicionados fora do rosto |
| Cor | **Correção** automática por plano (balanço de branco, exposição) e depois o look (natural, clean_warm…) |
| Áudio | Voz tratada pelo Adobe Podcast + ambiente dosado + volume no padrão do Instagram (−14 LUFS) |
| Controle de qualidade | Resolução, fps, volume, pico, distorção, quadros pretos, imagem congelada, safe zones, excesso de SFX |
| Nota e registro | Nota 0–5 em 10 dimensões + `decisoes.json` com cada decisão e o motivo |
| Entrega (Instagram) | Reel, capa, prévia do recorte da grade do perfil e partes para Stories se passar de 60 s |

O fluxo completo, passo a passo, está em [docs/FLUXO.md](docs/FLUXO.md). Os critérios de edição seguem o
*Manual Técnico de Edição Profissional para Social Media* do autor, transformado em regras em
[references/manual-edicao.md](references/manual-edicao.md) — ele prevalece sobre as outras referências.

## Requisitos

- **Claude Code** (app desktop, CLI ou extensão de IDE) com suporte a skills.
- **Python 3.10+** instalado no sistema (só para criar o ambiente; o resto é automático).
- ~2 GB livres (modelo de transcrição Whisper baixado no primeiro uso).
- Windows, macOS ou Linux. Testado principalmente no Windows 11.
- Opcional: **conector Adobe for creativity** no Claude, para o tratamento de voz.
- Opcional: arquivos de efeitos sonoros licenciados (veja [Efeitos sonoros](#efeitos-sonoros)).

Não é preciso instalar ffmpeg: a skill usa o binário do pacote `imageio-ffmpeg`.

## Instalação

```bash
git clone https://github.com/Edumnzes/cinex.git ~/.claude/skills/cinex
```

```bash
python ~/.claude/skills/cinex/scripts/setup_env.py
```

O segundo comando cria o ambiente Python em `~/reelsenv` (caminho curto de propósito — caminhos
longos quebram o `venv` no Windows) e instala as dependências de [requirements.txt](requirements.txt).
Ele imprime o caminho do Python e do ffmpeg que a skill vai usar.

Para atualizar depois:

```bash
git -C ~/.claude/skills/cinex pull
```

## Como usar

No Claude Code, anexe o vídeo e chame a skill:

```
@"C:\Users\voce\Downloads\VIDEO.MOV"
/cinex
```

Ou simplesmente peça em linguagem natural: *"edita esse vídeo para Reels, corta as pausas e
coloca legenda"*. A skill também é acionada por pedidos parciais (só legendas, só o corte, só o áudio).

O Claude vai:
1. **na primeira vez com uma marca**: fazer um briefing curto e analisar os Reels e Insights
   do Instagram (você faz o login; a skill só lê) — isso fica salvo e não é repetido;
2. recomendar 3 formatos para o vídeo e deixar você escolher (ou ver os 13);
3. analisar o vídeo e mostrar o mapa (tempo | plano | fala | tratamento sugerido) com o plano editorial;
4. perguntar o que só você sabe (nome do evento, @, dados na tela);
5. cortar, montar o projeto, conferir prévias, renderizar e passar no controle de qualidade;
6. entregar o arquivo final em `Downloads` com um resumo e a nota de cada dimensão.

Cada vídeo ganha uma pasta de trabalho em `~/reels/<nome-do-video>/`. Ela é mantida para que
ajustes (texto, cor, tempo) sejam rápidos — basta pedir.

## Estrutura do repositório

```
cinex/
├── SKILL.md                  # instruções que o Claude segue (ponto de entrada da skill)
├── README.md                 # este arquivo
├── LICENSE.md                # licença MIT
├── TERMOS_DE_USO.md          # termos de uso e privacidade
├── THIRD_PARTY_NOTICES.md    # licenças de terceiros (fontes, modelo, bibliotecas)
├── CHANGELOG.md
├── requirements.txt
├── docs/
│   └── FLUXO.md              # o fluxo completo, do vídeo bruto à entrega
├── scripts/
│   ├── setup_env.py          # cria ~/reelsenv e instala dependências
│   ├── transcribe.py         # transcrição com faster-whisper (tempo por palavra)
│   ├── energy.py             # mapa de energia do áudio (pausas)
│   ├── faces.py              # detecção de rostos (YuNet) + folha de miniaturas
│   ├── plan_cut.py           # remove pausas dentro das frases escolhidas
│   ├── cut.py                # renderiza o corte (+ cuts.json com o início de cada trecho)
│   ├── detect_cuts.py        # confere os cortes visíveis na imagem
│   ├── mix_audio.py          # mixa voz + ambiente + SFX e normaliza (−14 LUFS)
│   ├── brand.py              # lê/grava o perfil da marca (~/instagram-legendas/<arroba>/)
│   ├── qa.py                 # controle de qualidade do arquivo final
│   ├── decisions.py          # registro de decisões + nota 0–5 (decisoes.json)
│   ├── export_ig.py          # Reel, capa, prévia da grade e Stories
│   ├── formats.py            # padrões e motions de cada formato
│   ├── motion_lib.py         # motor de motion puro (sem vídeo): texto cinético, cards, fios, ícones
│   ├── compose.py            # split (react), clone e assemble (clipes + narração)
│   ├── banco.py              # banco do usuário: init / status / check / list
│   ├── sfx_ingest.py         # classifica, limpa e organiza efeitos sonoros baixados
│   ├── reels_lib.py          # motor: câmera, legendas, cor, B-roll, SFX, QA, render
│   └── fx.py                 # animações de texto e fundos (inspiradas no React Bits)
├── references/
│   ├── manual-edicao.md      # critérios do manual de edição (prevalece sobre os demais)
│   ├── formatos.md           # os 13 formatos: estrutura, edição, motions e guia de gravação
│   ├── banco.md              # como a skill usa referências, fontes, motions e sons do banco
│   ├── onboarding.md         # briefing + análise do Instagram (1ª vez por marca)
│   ├── style-guide.md        # números e regras: ritmo, zoom, proporção, legendas
│   ├── visual-references.md  # direções visuais, cor, SFX, bancos de assets
│   └── reactbits.md          # catálogo de animações
└── assets/
    ├── example_project.py    # projeto completo de exemplo (copiar e adaptar)
    ├── example_motion.py     # exemplo de motion explicativo (RSD, sistema solar)
    ├── marca_template.json   # modelo do marca.json
    ├── decisoes_template.json # modelo do registro de decisões
    ├── formatos.json         # padrões de máquina de cada formato
    ├── *.ttf + OFL.txt       # fontes (SIL Open Font License)
    └── yunet.onnx            # modelo de detecção de rosto (MIT)
```

## Comandos do projeto

Dentro da pasta do vídeo (`~/reels/<nome>/`), com o Python do ambiente (`~/reelsenv/Scripts/python`
no Windows, `~/reelsenv/bin/python` no macOS/Linux). `<skill>` é `~/.claude/skills/cinex`:

| Comando | Para quê |
|---|---|
| `python project.py preview 1 5.7 19.3 --debug` | Quadros-chave renderizados (com zonas de segurança) |
| `python project.py check` | Texto sobre o rosto, fora da área segura ou SFX demais |
| `python project.py cuts` | Em cada corte: zoom ou não, e por quê |
| `python project.py motion` | Velocidade de pan/zoom e tremidas — deve dar **SMOOTH** |
| `python project.py strip 5.2 6.2` | Quadros consecutivos para julgar suavidade |
| `python project.py looks 12` | O mesmo quadro em todos os ajustes de cor |
| `python project.py color` | Correção de cor por plano + `color.jpg` (antes / corrigido / + look) |
| `python project.py full render.mp4` | Render final (+ `final_sheet.jpg` para conferência) |
| `python <skill>/scripts/qa.py final.mp4 --project project.py` | Controle de qualidade — qualquer FALHA bloqueia a entrega |
| `python <skill>/scripts/decisions.py check` / `report` | Registro completo? Tabela de notas para a entrega |
| `python <skill>/scripts/export_ig.py final.mp4 --name X --cover 4.3` | Arquivos para o Instagram em Downloads |

## Formatos

Depois do perfil da marca, a skill recomenda **3 formatos** para o vídeo (e mostra os 13 se você quiser).
Cada formato define estrutura, ritmo, duração, disposição na tela, motions e traz um **guia de gravação** —
se o material não serve ao formato escolhido, a skill avisa e explica como gravar.

| Grupo | Formatos |
|---|---|
| Fala para câmera | Fala + pop-ups · Dicas rápidas · História / narrativa |
| Prova e reação | Depoimento de cliente · React (tela dividida) · Clone |
| Imagem + texto/voz | Frase de identificação · Conteúdo na legenda · Voiceover |
| Recorrência e visual | Série com episódios · Gancho visual forte / Dia X · Multitarefa |
| Sem vídeo gravado | **Motion explicativo** — texto cinético + diagrama de sistema animado (`motion_lib.py`) |

Formatos com mais de uma fonte são montados antes da edição com `scripts/compose.py`
(`split` para React, `clone` para Clone, `assemble` para clipes + narração). Detalhes em
[references/formatos.md](references/formatos.md).

## Perfil da marca

Na primeira edição de cada marca, a skill faz um **briefing curto** (quem produz, o que vende, para
quem, objetivo, tom, cores, CTA, o que evitar) e **analisa o Instagram**: Reels publicados, "Ver insights"
de 8–12 Reels (visualizações, % de não seguidores, tempo médio, compartilhamentos, visitas ao perfil)
e a visão geral da conta. Daí saem as regras de edição daquela marca.

- **Login:** feito por você no navegador (de preferência o Chrome com a extensão Claude, já logado).
  A skill **nunca digita senha** e **só lê** — não curte, não comenta, não segue, não altera nada.
  Sem navegador, dá para mandar prints.
- **Onde fica:** `~/instagram-legendas/<arroba>/` — a mesma pasta da skill `legendas-instagram`,
  então as duas compartilham o que já sabem sobre a marca.

| Arquivo | Conteúdo |
|---|---|
| `perfil.md` | Negócio, público, voz, insights (compartilhado com as legendas) |
| `video.md` | Análise dos Reels e direção de edição recomendada |
| `marca.json` | Padrões aplicados automaticamente: @, CTA, cores, fontes, logo, estilo de legenda, cor, termos da transcrição |
| `videos.md` | Histórico de Reels entregues |

```bash
python ~/.claude/skills/cinex/scripts/brand.py list
```

Mostra as marcas que já têm perfil. Para ver ou apagar, é só abrir a pasta — são arquivos de texto.

## Banco (referências, fontes, motions, efeitos)

Seu acervo fica em `~/reels-banco` — fora do Git, porque fontes, motions e sons licenciados não podem ser
redistribuídos. Criar e conferir:

```bash
python ~/.claude/skills/cinex/scripts/banco.py init
```

```bash
python ~/.claude/skills/cinex/scripts/banco.py check
```

| Pasta | O que colocar | Uso |
|---|---|---|
| `referencias/<formato>/referencias.md` | links + o que copiar de cada referência | a skill segue o padrão do formato escolhido |
| `fontes/` | `.ttf`/`.otf` + licença | cada arquivo vira uma família; a marca escolhe no `marca.json` |
| `motions/<categoria>/` | `.mov` ProRes 4444 / `.webm` com transparência, `.gif`, pasta de PNGs | sobrepostos no vídeo |
| `sfx/<categoria>/` | `.wav`/`.mp3` (pop, whoosh, click, ding, riser, impact, flash, tick, error) | sons dos eventos-chave |

`.mogrt`/`.aep` e Lottie precisam ser exportados antes (ProRes 4444 com alfa / WebM com transparência).
Detalhes em [references/banco.md](references/banco.md).

## Efeitos sonoros

Seguindo o manual, os sons são **seletivos**: só nos eventos-chave (gancho, card principal, prova, CTA),
no máximo ~2 a cada 10 s e nunca em corte simples. A skill **não baixa sons sozinha**. Salve arquivos licenciados em:

```
~/reels-banco/sfx/pop/pop_01.wav
~/reels-banco/sfx/whoosh/whoosh_01.wav
~/reels-banco/sfx/click/click_01.wav
~/reels-banco/sfx/ding/ding_01.wav
```

(A pasta antiga `~/reels-sfx/` continua funcionando.)

**Jeito mais fácil:** baixe os sons no Pixabay (ou outro banco), solte os arquivos com qualquer nome em
`~/reels-banco/sfx/_entrada/` e peça ao Claude para organizar — ou rode:

```bash
python ~/.claude/skills/cinex/scripts/sfx_ingest.py --origem Pixabay
```

Cada som é classificado pelo nome e pela análise do áudio, tem o silêncio cortado e o volume igualado, e vai
para a pasta da categoria. O que não der para classificar fica em `sfx/_revisar/`.

Se você salvar direto nas pastas das categorias (sem o `sfx_ingest.py`), o nome do arquivo precisa começar
pela categoria (`pop_03.wav`). Fontes gratuitas com uso comercial permitido: **Mixkit** e **Pixabay**. Se a pasta não existir, o vídeo sai sem SFX e o render avisa quais categorias faltam.

## Áudio com Adobe Podcast

Com o conector **Adobe for creativity** ativo no Claude, só a trilha de voz é enviada ao Adobe
(a imagem nunca sai do computador). O resultado volta em faixas separadas (voz limpa, ambiente,
reverb) e é mixado localmente. Sem o conector, a skill normaliza o áudio original.

> No app desktop (aba Code), o resultado do Adobe chega por um painel que pode demorar a aparecer.
> Alternativa manual: enviar `voice.wav` em podcast.adobe.com/enhance e devolver o arquivo tratado.

## Privacidade e segurança

- **Tudo roda no seu computador.** Vídeo, transcrição, rostos e render ficam locais. Só a trilha de voz sai,
  e só se você usar o conector Adobe.
- **Nada de dados de clientes no Git.** O `.gitignore` bloqueia vídeos, áudios e imagens. O perfil das marcas
  (`~/instagram-legendas`), o banco (`~/reels-banco`) e os projetos (`~/reels`) ficam fora do repositório.
- **Instagram só leitura.** O login é seu; a skill nunca digita senha nem código e não curte, comenta ou
  altera nada.
- **Sem downloads por conta própria.** A skill não baixa sons, motions ou vídeos sem o seu OK.
- **Sem telemetria.** Os scripts não fazem nenhuma chamada de rede; os comandos externos (ffmpeg) são
  chamados sem shell, com os argumentos em lista.
- As dependências Python têm versões delimitadas em [requirements.txt](requirements.txt).

Detalhes em [TERMOS_DE_USO.md](TERMOS_DE_USO.md).

## Limitações

- Texto atrás da pessoa, texto "preso" no cenário em 3D e máscara do sujeito exigem Premiere,
  After Effects ou CapCut.
- A câmera virtual só simula ângulos (zoom/enquadramento); ângulos reais exigem outra gravação.
- LUTs `.cube` e templates `.mogrt/.aep` não são aplicados pelo motor.

## Solução de problemas

| Sintoma | Causa / solução |
|---|---|
| Erro de SSL ao baixar o modelo | Antivírus/proxy — a skill já usa `truststore`; rode de novo |
| `venv` falha no Windows | Caminho longo demais — mantenha o ambiente em `~/reelsenv` |
| Palavra cortada no meio | Alargar o limite daquele corte em 0,1–0,2 s e renderizar de novo |
| Rosto pequeno não é seguido | Baixar `min_face` para ~28 no `project.py` |
| Legenda com texto errado | Corrigir no `FIX` do projeto ou direto no `words.json` |

## Documentação detalhada

- [docs/FLUXO.md](docs/FLUXO.md) — tudo o que acontece do vídeo à entrega, e as ferramentas usadas
- [SKILL.md](SKILL.md) — as instruções que o Claude segue
- [references/style-guide.md](references/style-guide.md) — regras de ritmo, zoom, proporção e legendas
- [references/visual-references.md](references/visual-references.md) — estilos, cor, SFX e bancos de assets
- [CHANGELOG.md](CHANGELOG.md) — o que mudou em cada versão

## Licença

[MIT](LICENSE.md) — uso livre, inclusive comercial, sem pedir autorização; mantenha o aviso de copyright.
Fontes e o modelo de rosto incluídos seguem as próprias licenças ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).
