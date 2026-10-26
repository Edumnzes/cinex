# Changelog

## 3.0.0 — em desenvolvimento (branch `v3`)
- A ferramenta passa a se chamar **Cinex** (antes reels-editor): skill `cinex`, repositório `Edumnzes/cinex`
  (o link antigo redireciona), desenvolvimento na pasta `PROGRAMACAO/CINEX`, instalada em `~/.claude/skills/cinex`
  por uma junção (link de pasta) que aponta para ela.
- As pastas de dados não mudam: `~/reels-banco`, `~/instagram-legendas`, `~/reels`.
- **Licença MIT**: o uso deixa de depender de autorização do autor. Termos de uso reescritos como aviso de
  privacidade e responsabilidades (sem restringir a licença).
- Revisão da documentação: índice do README completo, passos de uso na ordem real (perfil → formato → análise),
  seção de privacidade e segurança, caminhos dos scripts a partir da pasta do projeto, regra de SFX seletivos
  também no FLUXO, `cuts=CUTS` (de cuts.json) em todos os guias, 13 formatos no diagrama.
- `sfx_ingest.py`: nunca sobrescreve um som do banco (antes, apagar um arquivo do meio da numeração fazia o
  próximo som importado substituir outro, e um original repetido em `_processados` interrompia a importação).
- Exemplos com marca fictícia ("Sol Exemplo", `suamarca`) no lugar de marcas reais; o PDF do manual de edição
  deixa de ser distribuído (as regras continuam em `references/manual-edicao.md`).
- **App Cinex (primeira fase)**: editor visual local (`app/server.py`, http://127.0.0.1:8765) com linha do
  tempo (trechos mantidos/cortados sobre a onda do áudio), prévia 9:16 que já pula os cortes e mostra as legendas,
  painel de legendas (estilos prontos, fonte embutida, do banco ou do computador, peso, cor, destaque, tamanho,
  contorno, posição, 1 ou 2 linhas, 1/3/5 palavras, caixa alta), aprovação do corte e exportação para Downloads.
  O Claude Code continua sendo o cérebro: propõe o corte e responde pela conversa do app
  (`scripts/app_project.py`: new, show, seg, say, wait, export). O servidor só aceita conexões deste computador
  e recusa pedidos de outros sites.
- Interface no estilo Premiere + Notion: painéis (inspetor, monitor de programa, conversa, sequência), trilhas C1/V1/A1
  com cabeçalho, timecode HH:MM:SS:QQ, transporte (quadro a quadro, trecho anterior/próximo, setas do teclado),
  linha do tempo que acompanha a reprodução, conversa em estilo de comentários e paleta neutra.
- Formato no app: **Mobile 9:16** (Reels) ou **Desktop 16:9** (mantém o horizontal). No Mobile o layout do programa
  muda: a prévia vertical fica em pé à esquerda, em toda a altura, e as ferramentas ocupam o resto. Prévia e exportação
  em cada um (`<nome>_cinex.mp4` / `<nome>_cinex_16x9.mp4`). Vídeo gravado em pé no 16:9 aparece inteiro, com
  fundo desfocado nas laterais (`cut.py --fit blur`). `qa.py --platform desktop` confere o 16:9.
- Painéis redimensionáveis: arraste a borda do inspetor, da conversa (Desktop), da prévia (Mobile) ou o topo da
  linha do tempo; cada layout guarda os próprios tamanhos e o duplo clique na borda volta ao padrão.
- **Fase 2 do app: câmera, zoom e cor.** Aba Câmera: seguir o rosto (câmera virtual parada quando a pessoa está
  parada, acompanhando suave quando ela anda), zoom de 100 a 125 % e degrau de zoom nos cortes (o motor decide
  em quais). Aba Cor: correção automática por plano e seis looks (Natural, Sem look, Quente suave, Teal e laranja,
  Moody, Dia vivo). Prévia aproximada no app; a exportação usa o motor completo.
- Motor: janela de corte com a proporção da saída, então vídeo horizontal vira 9:16 seguindo o rosto
  (`cut.py --fit keep` mantém o quadro inteiro para a câmera escolher o enquadramento).
- Servidor em HTTP/1.1 (respostas grandes não são mais cortadas) e o app não trava se um pedido demorar.
- **Fase 3 do app: motion e efeitos sonoros.** Trilha M1 com elementos (título, tópico numerado, nome, citação,
  frase grande, chamadas "siga" e "salve") adicionados no ponto da agulha, arrastáveis e com duração ajustável pela
  borda; texto e som de entrada editados no inspetor; prévia ao vivo no monitor. Trilha S1 com sons do banco
  (`~/reels-banco/sfx`), volume por som, prévia de áudio durante a reprodução e aviso quando passa do limite do
  manual (~2 sons a cada 10 s). Na exportação, cada elemento usa o modelo do `formats.py` (posicionado fora do
  rosto) e as legendas somem enquanto uma citação ou frase grande está na tela.
- **Reordenar frases no app:** lista "Ordem das frases" na aba Corte (arrastar, ↑ ↓, "abrir com esta frase" para cold
  open, restaurar a ordem original). Frase = trechos mantidos separados só por pausas curtas, então move a frase
  inteira. A prévia toca na nova ordem, a V1 numera as frases e legendas, motion e sons acompanham cada frase na
  exportação (`order` no cinex.json; `app_project.py order`). Edições por intervalo preservam os ids dos trechos.
- **Estilos de referência** (`scripts/estilo.py`): mede vídeos de referência (ritmo de cortes, look de cor em Lab,
  volume, ritmo de fala) e gera folhas para o Claude ler a tipografia e completar as regras; o perfil fica em
  `~/reels-banco/estilos/<id>/` e é aplicado no app com um clique (legenda, câmera e look copiado por
  transferência estatística de cor, `register_transfer` no motor).
- **Revisão "cara de IA"** (`scripts/revisao.py` e aba Revisão do app): aponta regularidade e repetição (planos
  iguais, motion e sons no compasso, som em todo elemento, uma palavra por legenda, CTA cedo) e compara com o
  estilo aplicado, sem exportar; o Claude completa com a leitura visual dos quadros.
- Legenda com **fonte e tamanho próprios para a palavra de ênfase** (ex.: legenda pequena e a palavra-chave grande em
  serifa itálica), no app e no motor. Perfis de estilo criados só por observação (`estilo.py criar`), com look base
  até a cor ser medida; 4 perfis observados nas referências do Instagram ficam no banco do usuário.
- **Protótipo de motion em HTML com HyperFrames** (`motion_html/`): renderizado com transparência e composto pelo
  motor; abre caminho para tipografia de designer, máscaras e 3D no motion.
- **Marca no app** (aba Marca): status do onboarding, ranking do que funciona no Instagram da marca
  (`scripts/desempenho.py`: views, retenção, engajamento, compartilhamentos e clientes por formato, tema, gancho,
  estilo e duração, comparados à mediana do perfil) e **referências do nicho por marca** (links ou vídeos enviados,
  medidos automaticamente no perfil de estilo `nicho_<arroba>`).
- **Motion em HTML na exportação**: os 7 elementos (título, tópico, nome, citação, frase grande, siga, salve) agora são
  renderizados com o HyperFrames a partir de modelos em `motion_html/templates/` (máscaras, molas, 3D leve, tipografia
  com serifa itálica), com cache por conteúdo e o motion clássico como reserva. Escolha no app em Motion › Motor.
- **Máscara: texto atrás da pessoa.** O motor recorta a pessoa quadro a quadro (MediaPipe, modelo
  `selfie_multiclass_256x256.tflite` em `~/reels-banco/modelos`, roda no processador, ~0,1 s por quadro, só nos trechos
  com elemento atrás) e monta as camadas vídeo → elemento atrás → pessoa → elementos da frente → legenda, com
  suavização entre quadros. Novo elemento **Palavra gigante** (modelo HTML que ocupa a largura e fica na altura da
  cabeça) e a opção **Atrás da pessoa** para qualquer elemento do motor HTML.
- **Texto 3D no cenário.** Novo elemento **Texto no cenário (3D)**: no app, marque a superfície (parede, tela, chão)
  com 4 cliques no preview e veja o texto em perspectiva. Na exportação, o texto é renderizado com letras em relevo
  (modelo `cenario`), rastreado na superfície (`scripts/plane_track.py`: pontos SIFT do fundo comparados ao quadro
  marcado, pessoas excluídas pela máscara, homografia RANSAC e suavização), deformado na perspectiva antes da câmera
  virtual e escondido atrás da pessoa quando ela passa na frente. Sem marcação (ou com fundo desfocado), vira
  elemento comum. O preview não recorta a pessoa; a exportação recorta.
- **Câmera lenta e trechos sem som.** Velocidade por trecho (0,5x, 0,35x, 0,25x, interpolada, sem som e sem
  legenda) e opção "sem som" (só imagem). **Câmera lenta no pico de ação**: acha o momento de mais movimento e
  brilho e separa 2 s em 0,35x (`app_project.py lenta`). A timeline, as legendas, o motion e o B-roll contam com a
  duração esticada.
- **Trilha licenciada com ducking automático** (aba Sons): abaixa ~19 dB sob a voz e volta sem fala
  (`mix_audio.py --music`). Música viral segue pelo editor do Instagram.
- **Fala de vários clipes.** Um projeto pode juntar vários vídeos numa sequência só (aba Corte › Clipes de fala, ou
  `app_project.py clips`): cada clipe é transcrito e cortado, e as frases de qualquer clipe podem ser reordenadas.
  `cut.py` aceita trechos de vários vídeos (`[início, fim, arquivo]`). Clipe sem áudio entra inteiro.
- **B-roll no app (trilha V2).** Aba B-roll para adicionar clipes ao projeto (caminho ou envio pelo navegador;
  prévia leve e faixa de quadros, HDR convertido) e cobrir a fala com eles: arrastar, esticar, escolher a entrada
  no clipe, tela cheia ou cartão, aproximação lenta. A prévia toca o clipe sincronizado com o corte; a exportação
  usa o B-roll do motor. CLI: `app_project.py media` e `app_project.py broll`.
- **Música:** a skill não gera trilhas; sugere músicas reais (de preferência virais do Instagram) para adicionar
  no editor do Instagram.
- Servidor do app: lê o corpo de toda requisição e fecha a conexão nas respostas de erro, para que um pedido não
  "vaze" no seguinte com a conexão reaproveitada (exportar e revisar podiam falhar de forma intermitente).
- **HDR do iPhone.** Vídeos HLG/PQ são detectados e convertidos para SDR (Rec.709) no corte, na prévia do app,
  no B-roll do motor e no `compose.py` (`scripts/hdr.py`). Antes saíam lavados e com a cor errada.
- `mix_audio.py --clean`: limpeza de voz só com ffmpeg, plano B quando o Adobe Enhance não está disponível.
- B-roll e `compose.py assemble` avisam e encurtam a janela quando o trecho pedido passa do fim do clipe
  (antes a timeline ficava mais curta sem aviso).
- Motor: legenda em duas linhas quando não cabe em uma, cor do texto configurável, `Reel.render()` com progresso.
- `cut.py` recorta para 9:16 em vez de esticar vídeos com outra proporção.
- `requirements.txt` com faixas de versão; `setup_env.py` passa a instalar a partir dele.

## 2.0.0 — 2026-10-25
- **Perfil da marca como primeiro passo**: briefing curto + análise somente leitura dos Reels e Insights
  do Instagram (login feito pela pessoa), salvo em `~/instagram-legendas/<arroba>/` e reaproveitado.
- Pasta compartilhada com a skill `legendas-instagram` (`perfil.md`), mais `video.md`, `marca.json` e `videos.md`.
- `scripts/brand.py` (list/show/init/log e `load_brand()` para o project.py) e `assets/marca_template.json`.
- `references/onboarding.md`: roteiro do briefing, o que ler no Instagram, regras de segurança e modelos.
- O perfil passa a definir termos da transcrição, direção visual, cores, CTA e duração alvo.
- Termos de uso: seção sobre acesso ao Instagram e dados do perfil.
- **Manual Técnico de Edição** incorporado (`references/manual-edicao.md`, PDF em `docs/`), com precedência
  sobre as outras referências:
  - plano editorial antes do corte (objetivo, mensagem central, estrutura, gancho → CTA; CTA só após o benefício);
  - pausas com função mantidas (`plan_cut.py` com `hold`);
  - efeitos sonoros seletivos (aviso no `check` acima de ~2 a cada 10 s ou em cortes simples);
  - legendas animadas por grupo (`caption_anim="group"`), sem animar cada palavra;
  - correção de cor automática por plano antes do look (`correct=True`, `project.py color`), look `natural` embutido.
- `scripts/qa.py`: controle de qualidade do arquivo final (bloqueia a entrega em caso de falha).
- `scripts/decisions.py` + `assets/decisoes_template.json`: registro de decisões no formato do manual e nota 0–5.
- `scripts/export_ig.py`: Reel, capa, prévia da grade 3:4 e Stories (>60 s). Destino: só Instagram por enquanto.
- **Formatos (templates)**: 12 formatos escolhidos a partir de referências validadas no Instagram, selecionados
  pelo usuário logo após o briefing (3 recomendados + lista completa). `references/formatos.md` (estrutura, edição,
  motions, guia de gravação), `assets/formatos.json` (padrões), `scripts/formats.py` (motions: dica numerada,
  progresso, capítulo, citação, nome, antes/depois, react, clone, frase grande, leia a legenda, série, próximo
  episódio, Dia X, CTAs) e `scripts/compose.py` (split / clone / assemble).
- Motion explicativo com efeitos sonoros: `Motion(draw, dur, sfx=[...])` usa o banco com as mesmas regras do motor de
  edição; `qa.py --silent` aceita trilha só com efeitos.
- `scripts/sfx_ingest.py`: efeitos sonoros baixados à mão (Pixabay etc.) são classificados pelo nome e pela análise
  do áudio, limpos (silêncio, volume) e organizados por categoria, com origem e licença em `sfx/sfx.json`. Reconhece duplicados, marca o tamanho de uso
  (ideal/longo/curto); o motor prefere os ideais, corta sons longos no tamanho útil e faz o riser terminar no evento.
- `assets/example_project.py` reescrito no padrão da v2 (perfil da marca, formato, motions de formato, SFX seletivo),
  sem conteúdo de clientes. Descrição da skill atualizada para 13 formatos e para pedidos de "vídeo em motion".
- **13º formato: Motion explicativo** (sem vídeo gravado): `scripts/motion_lib.py` (texto cinético, cards, chave,
  fios com energia fluindo, ícones de sistema solar, estados), `assets/example_motion.py`, `qa.py --silent`.
- **Banco do usuário** (`~/reels-banco`, fora do Git): referências por formato, fontes, motions e efeitos sonoros.
  `scripts/banco.py` (init / status / check / list); `references/banco.md`.
  - fontes do banco viram famílias de texto automaticamente;
  - motions sobrepostos com transparência (`overlays=[...]`): `.mov` ProRes 4444/Animation, `.webm` VP9 com alfa,
    `.gif`, sequência PNG; o `check` recusa arquivos sem transparência e avisa motion sobre o rosto;
  - SFX por categoria (`sfx/<categoria>/`), alternando entre os arquivos da categoria.
- Legendas e textos alinhados pela linha de base da fonte (`glyph_mid`/`baseline_for`): palavras com letras que
  descem ("que", "g") não sobem mais em relação às outras.
- Marca: `formatos_preferidos` e `series` no `marca.json`; registro: campo `formato` no `decisoes.json`.
- `mix_audio.py`: normalização em duas passadas (a de uma passada ficava em −15,7 LUFS em vídeos curtos)
  e medição no arquivo de saída.

## 1.0.0 — 2026-09-29
Primeira versão no GitHub (uso privado).

- Análise: transcrição com tempo por palavra (faster-whisper), mapa de energia, detecção de rostos (YuNet).
- Corte automático de pausas com verificação por re-transcrição; `cuts.json` com cortes exatos por quadro.
- Câmera virtual com decisão LOCK/TRACK por trecho, zoom só nos cortes e relatório `motion`.
- Legendas palavra por palavra em 3 estilos (hormozi, minimal, cinematic).
- Motion graphics com posicionamento fora do rosto (`slot()`), escala tipográfica fixa e animações de texto (`fx.py`).
- Ajustes de cor com comparação lado a lado (`looks`); ajustes personalizados por projeto.
- Integração com Adobe Podcast Enhance Speech via conector Adobe; mixagem e normalização a −14 LUFS.
- Efeitos sonoros a partir de biblioteca local licenciada (`~/reels-sfx`).
- Documentação: README, fluxo completo, licença proprietária, termos de uso e avisos de terceiros.
