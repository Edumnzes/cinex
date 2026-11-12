# Formatos de vídeo — os 8 perfis oficiais

Parâmetros de máquina, técnicas e anti-padrões de cada formato ficam em `conhecimento/formatos.json` (versionado; muda
só por proposta aprovada, ver `references/aprendizado.md`). Motions em `scripts/formats.py`; montagens com mais de uma
fonte em `scripts/compose.py`. As regras do `manual-edicao.md` valem para todos.

**Como escolher (passo B do SKILL.md):** depois do perfil da marca, recomende **3 formatos** para este vídeo (pelo
material gravado, objetivo e o que funciona na marca: `aprendizado.py regras --marca X` mostra `marca.formatos_preferidos`
quando aprovados) e deixe ver a lista toda. Se o material não serve ao formato, diga e entregue o guia de gravação.
Formatos podem ser combinados (`--combina`): o principal define os parâmetros e as técnicas dos dois somam.

| id | Formato | Precisa de | Montagem |
|---|---|---|---|
| `talking_head` | Yap Content (Talking Head) | 1 vídeo falando, entrevista ou podcast | corte normal |
| `split_screen` | Tela Dividida | referência + reação, ou 2 takes em câmera fixa | `compose.py split` / `clone` |
| `lists_rankings` | Listas Rápidas e Rankings | 1 vídeo com 3–7 itens | corte normal |
| `before_after` | Antes e Depois | antes e depois do mesmo ângulo | `compose.py assemble` |
| `behind_the_scenes` | Bastidores da Instalação e Dia de Obra | muitos clipes curtos da obra | `compose.py assemble` (ou corte, com fala) |
| `myths_facts` | Mitos e Verdades | 1 vídeo falando + prova | corte normal |
| `visualization_3d` | Visualizações 3D e Fluxo de Energia | roteiro (sem vídeo) ou renders 3D prontos | `motion_lib.py` |
| `testimonial` | Depoimento Real do Cliente | vídeo do cliente (+ B-roll) | corte normal |

Combinações já descritas: Talking Head + Listas; Depoimento + Antes e Depois; Bastidores + 3D; Mitos e Verdades +
Talking Head; Tela Dividida + 3D.

---

## talking_head — Yap Content (Talking Head)
- **Aprende:** ganchos, pausas, cortes, enquadramento, zoom, legendas e ritmo de fala.
- **Quando:** explicar, opinar, anunciar; recortes de entrevista, palestra e podcast; histórias contadas para a câmera.
- **Estrutura:** gancho (cold open com a frase mais forte + título de 3 s) → contexto → desenvolvimento → prova → conclusão → CTA.
  História: nunca contar o final no gancho; ritmo mais lento na virada (pausa funcional).
- **Edição:** corte de pausas sem função, frases sempre completas, zoom só em jump cut visível, legenda por grupo sem
  borda nem brilho. Vídeo horizontal com várias pessoas: reenquadrar por âncoras e conferir com strip (o rastreio
  pode pular para outra pessoa). 20–60 s (Reels de recorte: 30–40 s).
- **Motions:** `hook_title`/pill no gancho, cards só onde explicam, `cta_follow`.
- **Gravar:** celular na vertical na altura dos olhos, luz de frente, lapela; frases curtas com 1 s de silêncio entre ideias.

## split_screen — Tela Dividida
- **Aprende:** proporções, sincronização, hierarquia visual, composição e equilíbrio entre painéis.
- **Quando:** reagir a um vídeo que circula (react) ou diálogo "eu cético × eu especialista" (clone).
- **Estrutura:** trecho que prende → reação/comparação → opinião do especialista → CTA.
- **Montagem:** react `compose.py split REFERENCIA.mp4 REACAO.MOV raw.mp4 --top-ss X --dur D` (referência em cima,
  áudio −14 dB); clone `compose.py clone TAKE_A.MOV TAKE_B.MOV raw.mp4 --seam 0.5`. Depois o fluxo normal. 15–45 s.
- **Edição:** `cap_y=960` (legenda na emenda), sem zoom, um painel principal claro.
- **Motions:** `react_label`, `speaker_tag`, `cta_follow`.
- **Direitos:** só referência sua, licenciada, ou trecho curto com comentário e crédito. Registre a origem.
- **Gravar:** reação com fone, reagindo de verdade; clone no tripé sem mexer, ninguém cruza a metade do quadro.

## lists_rankings — Listas Rápidas e Rankings
- **Aprende:** velocidade, progressão, animação de números e retenção entre itens.
- **Estrutura:** gancho com número ("3 sinais de que…") → item 1 → … → resumo → CTA salvar. Sem introdução.
- **Edição:** ritmo rápido, cada item entra num corte. 15–45 s.
- **Motions:** `tip_card(n, total, texto)` + `tip_progress`; `cta_save`. Card com o item em ≤ 8 palavras.
- **Gravar:** um item por take, começando já pelo item ("Dois: …").

## before_after — Antes e Depois
- **Aprende:** comparação, sincronização, evidências visuais, transições e revelação.
- **Estrutura:** depois (ou a tensão) primeiro → antes → processo resumido → revelação → número/prova → CTA.
- **Edição:** mesmo ângulo e mesma cor no antes e no depois (cor diferente vira prova falsa); revelação por corte
  seco, sem transição chamativa. 10–40 s.
- **Motions:** `before_after` (ex.: conta R$ 890 → R$ 49), `day_title`, `cta_follow`.
- **Gravar:** antes e depois do mesmo ponto, mesma altura e lente; anote os números reais.

## behind_the_scenes — Bastidores da Instalação e Dia de Obra
- **Aprende:** sequência operacional, planos de detalhe, timelapse, ambientação e narrativa documental.
- **Estrutura:** imagem que para a rolagem → contexto do dia → etapas em ordem → resultado → CTA.
- **Montagem:** `compose.py assemble` com clipes de 3–5 s (ou corte normal se houver fala/narração).
- **Edição:** alternar plano aberto, médio e detalhe; cortar no movimento, nunca no meio do gesto; timelapse curto
  para etapas longas. **EPI sempre visível**: troque ou cubra cena sem luva/capacete. 15–60 s.
- **Motions:** `day_title`, `chapter_label`, pills pontuais, `cta_follow`. Série recorrente ("Obra da semana"):
  `series_badge`/`next_episode` e identidade fixa na preferência da marca.
- **Gravar:** registre o dia em clipes curtos de cada etapa.

## myths_facts — Mitos e Verdades
- **Aprende:** suspense, explicação, ritmo e comprovação.
- **Estrutura:** mito em uma frase → pausa de suspense → veredito (MITO/VERDADE na tela) → explicação → prova ou norma → CTA.
- **Edição:** a afirmação técnica precisa estar conferida na norma ou no fabricante; fala errada é cortada ou
  corrigida, nunca publicada (ex.: DPS protege contra surto, não contra curto-circuito). 20–50 s.
- **Motions:** `big_phrase` no veredito, pill/card na prova, `cta_follow`.
- **Gravar:** mito, 1 s de pausa, veredito, exemplo concreto. Tenha a fonte em mãos.

## visualization_3d — Visualizações 3D e Fluxo de Energia
- **Aprende:** câmera, materiais, iluminação, animação e representação técnica.
- **Limite do Cinex:** não renderiza 3D. O fluxo de energia é **2D animado** (`scripts/motion_lib.py`); renders 3D
  feitos fora entram como clipe/B-roll.
- **Estrutura:** gancho em texto → título do conceito → o sistema montando → o problema (mudança de estado) →
  o número → a solução → CTA.
- **Estilo:** fundo claro, uma cor de marca, texto cinético preto, cards arredondados; fios com bolinhas no sentido
  da energia; cores fixas (CC azul, CA laranja, perigo vermelho, seguro verde); mudança de estado visível.
- **Motor:** `Motion(draw, dur).cli()` → `preview`, `check`, `full`; peças `ktext`, `ring`, `card`, `chip`, `label`,
  `toggle`, `Wires`, ícones `g_*`, `ambient`. Exemplo: `assets/example_motion.py`.
- **Texto = narração:** cada frase fica `read_time()` na tela; ≤ 12 palavras, nunca abaixo de `xs` (26 px).
- **Áudio:** sem voz, SFX nos eventos-chave; música no app do Instagram. QA com `qa.py --silent`.
- **Cuidados:** extraia ideias da fonte e reescreva; afirmações normativas e números são da marca — registre a fonte.

## testimonial — Depoimento Real do Cliente
- **Aprende:** seleção de falas, autenticidade, emoção, contexto, imagens de apoio e credibilidade.
- **Estrutura:** resultado primeiro (a melhor frase do cliente) → quem é → antes → decisão → depois com números → CTA.
- **Edição:** limpar pausas sem robotizar o cliente (corte mais leve); B-roll do projeto enquanto ele fala do
  resultado. 20–60 s.
- **Motions:** `name_card`, `before_after` quando o número é dito, `quote_card` opcional.
- **Gravar:** entreviste ("como era antes?", "o que mudou?", "quanto pagava e quanto paga?"). Autorização de uso
  de imagem do cliente obrigatória.
