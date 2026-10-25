# Manual de edição — critérios da skill

Fonte: *Manual Técnico de Edição Profissional para Social Media* v1.0 (set/2026), do autor da skill
(o PDF não é distribuído no repositório). Este arquivo transforma o manual em regras
operacionais. **Quando outra referência da skill contradisser este arquivo, vale este arquivo.**

## Conteúdo
1. Modelo mental: 5 camadas
2. Plano editorial (antes de cortar)
3. Corte, pausas e jump cut
4. B-roll
5. Áudio e efeitos sonoros
6. Motion
7. Legendas e tipografia
8. Composição
9. Cor: correção antes do look
10. Instagram (destino atual)
11. Acessibilidade
12. Controle de qualidade da exportação
13. Nota 0–5 e registro de decisões
14. Regras de comportamento e erros a rejeitar

---

## 1. Modelo mental: 5 camadas, nesta ordem
1. **Objetivo** — informar, vender, autoridade, demonstrar produto, contar história, tráfego…
2. **Mensagem** — a informação principal que o espectador precisa entender e lembrar.
3. **Narrativa** — a sequência que produz compreensão e interesse.
4. **Execução** — cortes, enquadramento, B-roll, texto, motion, áudio, cor.
5. **Distribuição** — plataforma, proporção, duração, safe zones, legendas, formato de entrega.

Nunca começar pela camada 4. Todo efeito precisa de uma função (narrativa, informativa, estética ou
de continuidade); "está disponível" não é função.

## 2. Plano editorial (antes de cortar)
Depois da análise e antes do `phrases.json`, escreva o plano e mostre ao usuário junto com o mapa.
Ele vai para `decisoes.json → objective, audience, duration_target, editorial_strategy`.

| Item | Como decidir |
|---|---|
| Objetivo | Do briefing (`marca.json`) + o que o vídeo de fato diz |
| Público | Do perfil da marca; se o vídeo fala com outro público, dizer |
| Mensagem central | Uma frase. Se não couber numa frase, o vídeo tem assunto demais |
| Duração alvo | `marca.json → edicao.duracao_alvo_s`, ajustada ao conteúdo |
| Estrutura | Uma da tabela abaixo |
| Sequência | Gancho → contexto → desenvolvimento → prova → conclusão → CTA, com o trecho de fala de cada parte |

| Estrutura | Quando usar |
|---|---|
| Problema → solução | produto, serviço, tutorial, anúncio |
| Antes → depois | transformação, resultado, demonstração |
| Curiosidade → revelação | educativo, entretenimento |
| Afirmação → prova | autoridade, cases, vendas |
| Erro → correção | educação, conteúdo técnico |
| Processo → resultado | bastidores, obra, fabricação, agro |
| História → aprendizado | marca pessoal |

Regras da sequência:
- **Gancho** nos primeiros segundos: promessa, problema, curiosidade, contraste ou dado relevante,
  coerente com o que o vídeo entrega. Uma frase forte do meio pode virar abertura (cold open).
- **Contexto** só o suficiente para entender. Introdução longa é o erro que mais derruba retenção.
- **Prova** sempre que existir: número, resultado, exemplo, demonstração.
- **CTA só depois de o benefício estar claro.** CTA antes do benefício é erro.
- Se a ordem gravada não serve à narrativa, reordene as frases (o `phrases.json` aceita qualquer ordem).

Diagnóstico de baixa retenção para checar no plano: gancho lento ou desconectado; introdução longa;
mesma ideia repetida; plano longo sem mudança relevante; efeitos competindo com a mensagem; áudio ruim;
texto ilegível ou excessivo; conclusão tardia; CTA sem contexto.

## 3. Corte, pausas e jump cut
- Remover: erros, repetições, hesitações, falsas largadas e **pausas sem função**.
- **Manter pausas com função** — ênfase antes de um número, humor, emoção, tempo para entender algo
  visual. No `phrases.json`: `[s, e, {"hold": [t], "why": "ênfase antes do resultado"}]`
  (`plan_cut.py` mantém a pausa, no máximo `--hold-max` 0,7 s). Registre em `kept_pauses`.
- Cortar antes que um plano fique visualmente redundante; usar o corte para dirigir a atenção.
- **Mais cortes ≠ mais profissional.** Ritmo rápido não é ritmo adequado. Não sacrificar
  inteligibilidade por velocidade.
- Jump cut deve parecer deliberado. Para esconder quebra excessiva: B-roll, mudança de escala ou
  movimento. **Não** aplicar zoom a cada frase (o `jumpcuts="auto"` já decide por corte).
- Várias tomadas: escolher a que equilibra conteúdo, atuação, enquadramento e continuidade.
- Cada trecho removido vai para `cut_decisions` com o motivo.

## 4. B-roll
Relevância semântica acima de tudo: mostrar o que está sendo dito, nunca contradizer a fala.
Usar para esconder cortes e variar estímulo sem interromper a narrativa. Evitar imagem genérica
"para preencher". Manter coerência de luz, escala e direção. Cada uso vai para `b_roll_decisions`.

## 5. Áudio e efeitos sonoros
- Voz: reduzir ruído sem artefatos, equilibrar volume, EQ/compressão com moderação, sem voz metálica
  (Adobe Enhance Speech + `mix_audio.py`, −14 LUFS, pico ≤ −1 dBTP, medido na saída).
- Voz, ambiente, música e efeitos têm papéis diferentes e não competem entre si.
- **Música: ainda não configurada** na skill — não adicionar música por conta própria.
- **Efeitos sonoros são seletivos.** Um som por corte cansa e soa artificial. Usar só nos eventos-chave:
  entrada do gancho, o card principal, um resultado/prova, o CTA. Referência: no máximo ~2 a cada 10 s,
  nunca em corte simples. O `project.py check` avisa quando passa disso. Registrar em `sfx_strategy`.

## 6. Motion
Princípios: entrada, permanência (tempo para ler), ênfase quando necessário, saída clara, timing,
easing natural e hierarquia. Texto entra por fade, deslocamento, escala ou máscara conforme a
identidade visual — o objetivo é legibilidade e hierarquia, não quantidade de efeitos.
Cada motion vai para `motion_strategy` com a **função** (explicar, provar, situar, chamar para ação).

## 7. Legendas e tipografia
- Fonte legível em tela pequena, contraste suficiente, blocos curtos, sincronizadas com a fala.
- Não cobrir rosto, produto ou informação essencial; posição consistente.
- Destacar palavra-chave só quando ajuda a entender.
- **Não animar cada palavra separadamente.** O grupo de legenda entra de uma vez; a palavra falada
  recebe só ênfase (cor/peso/escala leve). Motor: `caption_anim="group"` (padrão).
- Revisar nomes, termos técnicos e pontuação da transcrição.

## 8. Composição
Priorizar rosto, produto ou ação principal; respeitar direção do olhar e do movimento; pensar na
proporção final antes do crop; evitar zoom digital que degrade a imagem (motor limita a 1,25).

## 9. Cor: correção antes do look
Ordem obrigatória: **1. correção** (exposição, balanço de branco, contraste, saturação, tons de pele,
igualar planos) → **2. look** (aparência intencional, coerente com a marca).
- O motor corrige por plano automaticamente (`correct=True`): balanço de branco pelos tons neutros
  e exposição só quando o plano está escuro; nunca escurece cena clara nem acinzenta o branco.
- `python project.py color` → `color.jpg` (antes / corrigido / + look) e ganhos por plano. Olhe a pele.
- Look padrão: `natural`; outros só com motivo (marca, gênero do vídeo).
- Erros: saturação exagerada, pele artificial, contraste que come detalhe, look incompatível com a marca.
- Registrar em `color_strategy` (correção por plano + look + motivo).

## 10. Instagram (destino atual)
Só Instagram por enquanto. Reels 9:16 1080×1920, 30 fps, até 180 s; elementos importantes dentro da
safe zone; áudio e texto legíveis. `export_ig.py` gera o Reel, a capa, a prévia do recorte 3:4 da
grade do perfil e, se passar de 60 s, as partes para Stories.

## 11. Acessibilidade
Legendas sincronizadas e revisadas; contraste suficiente; texto em tamanho legível; nada essencial
transmitido só por cor; legenda nunca sobre informação visual essencial. Se algo visual importante
não é dito em voz, colocar em texto na tela.

## 12. Controle de qualidade da exportação
Exportar é uma etapa de controle. `python scripts/qa.py final.mp4 --project project.py` verifica
resolução, proporção, fps, duração, áudio, volume, pico, distorção, quadros pretos, imagem congelada,
decodificação completa e (via `project.py check`) gráficos sobre rosto, safe zone e excesso de SFX.
Qualquer FALHA bloqueia a entrega. Itens manuais que continuam sendo seus: revisar legendas, nomes,
números e datas; cor consistente entre planos; conferir a folha final (`final_sheet.jpg`).

## 13. Nota 0–5 e registro de decisões
`decisoes.json` (criado com `decisions.py init`) registra todo o raciocínio no formato do manual:
objetivo, público, plataforma, duração, identidade, estratégia editorial, cortes e pausas mantidas
com motivo, B-roll, legendas, áudio, cor, motion (com função), SFX, saída final, QA, verificação dos
erros a rejeitar e as **notas**.

| Dimensão | 0–1 | 2–3 | 4–5 |
|---|---|---|---|
| Narrativa | confusa | compreensível | clara e bem estruturada |
| Ritmo | cansativo | adequado | preciso e intencional |
| Áudio | prejudica | aceitável | limpo e bem mixado |
| Texto | ilegível/excessivo | funcional | legível e hierárquico |
| Motion | distrai | funcional | reforça a informação |
| Cor | inconsistente | aceitável | consistente/intencional |
| Composição | mal enquadrada | funcional | clara e equilibrada |
| Plataforma | inadequado | publicável | otimizado para o destino |
| Acessibilidade | ignorada | parcial | bem implementada |
| Objetivo | não atende | parcialmente | claramente |

Seja honesto: a nota é uma ferramenta interna de QA, não propaganda. Nota ≤ 3 exige justificativa e,
quando possível, uma sugestão do que elevaria a nota (ex.: "gravar com lapela", "falta prova numérica").

## 14. Regras de comportamento e erros a rejeitar
Regras: identificar objetivo, público, plataforma e duração antes de editar; mensagem e narrativa antes
de efeitos; nenhum efeito sem função; inteligibilidade acima de velocidade; nunca inventar informação
visual que contradiga a fala; manter a identidade da marca; preservar a qualidade do original; na dúvida,
a opção que melhora a compreensão sem aumentar a complexidade; ritmo adaptado ao conteúdo; revisar o
vídeo completo; validar textos, nomes, números, datas e termos; checar áudio, cor, safe zones, legendas
e exportação antes da entrega.

Erros a rejeitar (cada um é marcado em `rejected_errors_check`):
transições em excesso · zoom em todas as frases · SFX em todos os cortes · legenda gigante cobrindo o
rosto · texto de baixo contraste · música mais alta que a fala · grading exagerado · cortes rápidos que
prejudicam a compreensão · B-roll sem relação com a fala · imagem gerada com fato incorreto · CTA antes
do benefício · tendência copiada sem objetivo · introdução longa · mesmo estilo para todo nicho.
