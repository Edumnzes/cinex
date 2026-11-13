# Aprendizado contínuo — como a Cinex aprende sem mudar nada sozinha

Implementa o guia `CINEX-EDICAO-E-APRENDIZADO` (requisitos do dono). Ferramenta: `scripts/aprendizado.py`
(rode sem argumentos para ver todos os comandos). Tudo em JSON, só a biblioteca padrão.

## Princípios (valem acima de qualquer conveniência)

1. **Autonomia consultiva.** A Cinex registra, analisa e **propõe**. Regras globais, perfis de formato, técnicas e
   preferências de marca só mudam com `aprovar <id> --por "<nome>"` depois que o dono disse "sim" na conversa.
   Nunca aprove por conta própria. Instrução explícita do dono ("quero que…", "não use mais…") é aprovação daquela
   mudança, naquele escopo — registre como proposta e aprove citando a frase na `--nota`.
2. **Três escopos isolados.** Global (técnica e formato, sem dado de cliente), marca (só dela), projeto (só daquele vídeo).
   Nada de uma marca aparece em outra; o escopo global recusa texto que cite qualquer marca.
3. **Precedência.** padrão < regra global < perfil do formato < preferência da marca < preferência da marca para o
   formato < instrução do projeto. `aprendizado.py regras` mostra o valor vigente **e de onde veio**.
4. **Fato ≠ hipótese.** Correção isolada, métrica de 1–2 vídeos ou experimento pequeno é hipótese. Correlação não é
   causa. Qualidade técnica, qualidade editorial, aderência à marca e desempenho são avaliados separadamente.
5. **Saber quando NÃO usar.** Toda técnica do catálogo tem `quando_evitar`; anti-padrões ficam na lista `evitar` do formato.
6. **Rastreável e reversível.** Cada aprovação grava versão nova, guarda a anterior (`conhecimento/historico/` ou
   `<marca>/aprendizado/historico/`) e pode ser revertida (`reverter`). Rejeições ficam no histórico, sem virar regra.
7. **Sem treinar modelo.** Memória estruturada, avaliações e regras auditáveis.

## Onde fica cada coisa

| Escopo | Oficial (só muda por aprovação) | Registro (evidência) |
|---|---|---|
| Global | `conhecimento/tecnicas.json`, `formatos.json`, `regras.json`, `padrao.json` (no repositório) | `~/cinex-aprendizado/`: `evidencias.jsonl` (anônimas), `pesquisa.jsonl`, `experimentos/`, `propostas/` |
| Marca | `~/instagram-legendas/<arroba>/aprendizado/preferencias.json` (`regras` + `formatos.<id>`) | mesma pasta: `correcoes.jsonl`, `avaliacoes.jsonl`, `metricas.jsonl`, `combinacoes.jsonl`, `propostas/` |
| Projeto | `~/reels/<projeto>/aprendizado.json → instrucoes` | mesmo arquivo: `correcoes`, `avaliacao`, `metricas` |

Dados de cliente nunca vão para o repositório. `conhecimento/` é público e só tem conhecimento geral.

## Durante cada edição

1. **Início (depois dos passos A e B do SKILL.md):**
   `aprendizado.py projeto <projeto> --marca <arroba> --formato <id> [--combina <id2>] --objetivo "<objetivo>"`
   e `aprendizado.py regras --projeto <projeto>`. Use as regras vigentes na direção (3b) e no `project.py`.
   `aprendizado.py sugerir --formato <id> --marca <arroba> --objetivo "..."` lista técnicas para usar, para evitar e
   o que o Cinex ainda não executa (diga isso ao usuário em vez de improvisar).
2. **Instrução só deste vídeo** ("aqui corta essa parte", "nesse use verde"): `instrucao <projeto> <chave> <valor> --texto "..."`.
3. **Cada correção do usuário ou problema achado** (QA, revisão, fala técnica errada) vira registro classificado:
   `corrigir <projeto> --tipo <tipo> --area <area> --texto "..." [--tecnica id] [--chave k --valor v --antes v]`.
   Classifique antes de registrar — uma alteração manual, sozinha, não prova que a versão anterior estava errada:
   - `erro_tecnico` — falha objetiva (pico de áudio, legenda sobre o rosto, frase cortada, rastreio pegou outra pessoa, fala técnica errada);
   - `preferencia_marca` — gosto ou identidade da marca (cor, fonte, tom);
   - `preferencia_formato` — vale para o formato (ex.: lista com cards menores);
   - `decisao_projeto` — escolha pontual deste vídeo; não orienta o futuro;
   - `melhoria_global` — possível regra para todos. Use `--texto-geral` sem nome de marca (o registro global é anônimo).
4. **Se o usuário pedir uma mudança permanente** ("daqui pra frente", "sempre", "não quero mais"): crie a proposta com
   o escopo certo e aprove citando a instrução. Se for algo que você deduziu, crie a proposta e **pergunte**.
5. **Ao entregar:** `avaliar <projeto> '{"dimensoes": {...}, "lentes": {...}, "notas": "..."}'` com notas 0–5:
   dimensões `narrativa`, `ritmo`, `direcao_visual`, `motion_graphics`, `audio`, `assets`; lentes `qualidade_tecnica`,
   `qualidade_editorial`, `aderencia_marca`. Desempenho não entra aqui: vem das métricas.
6. **Depois de publicado** (quando houver números): `metricas <projeto> '{"views":…, "retencao_3s_pct":…, "compart":…}'`.

## Objetivo e resultado de cada vídeo

Antes de publicar, cada vídeo ganha um objetivo mensurável: `objetivo <projeto> --tipo <tipo> [--metrica M] [--meta N]
[--tecnicas a,b]`. Tipos e métrica padrão: alcance → views, compartilhamento → compart, salvamento → salvos, engajamento →
comentarios, seguidores → seguiu, visitas → visitas, leads → cliques, vendas → conversoes, retencao → retencao_3s_pct.
Depois dos Insights (lidos no navegador com o login do dono, só leitura; tempo médio e retenção só aparecem no app → prints),
`resultados --marca X` diz, por vídeo: **cumpriu** (atingiu a meta, ou a mediana dos vídeos da marca no mesmo formato quando
não há meta), **não cumpriu**, ou **sem base** (menos de 3 vídeos comparáveis). Também lista **pistas**: formatos e técnicas
que aparecem mais nos que cumpriram do que nos que não cumpriram. Vídeo turbinado aparece marcado e fica fora das medianas.
O relatório fica em `<marca>/aprendizado/resultados.md`. Na revisão semanal, leia junto com o `desempenho.py relatorio` e só
transforme uma pista em proposta quando ela se repetir com amostra suficiente.

## Revisão semanal e pesquisa mensal (rotinas configuráveis)

`aprendizado.py status [--marca X]` mostra versões, propostas aguardando e se as rotinas estão atrasadas
(`~/cinex-aprendizado/config.json`: `pesquisa_dias` 30, `revisao_dias` 7). As rotinas dependem de haver dados e fontes.
- **Revisão:** `padroes --marca X --propor` e `padroes --propor` (global, exige 2+ marcas) agrupam correções repetidas
  em hipóteses com confiança (baixa < 3 casos, média 3–5, alta 6+) e criam **rascunhos**. Revise, ajuste, `enviar <id>`
  e apresente ao dono. `comparar --marca X --formato F --objetivo O` só compara vídeos comparáveis; abaixo de 5, é hipótese.
  `desempenho.py aplicar` também só cria proposta. No fim: `aprendizado.py rotina revisao`.
- **Pesquisa:** cada achado com origem: `pesquisa add '{"fonte","tecnica","formatos","tipo":"tendencia|tecnica_consistente|indefinido","custo","adequacao","comparacao_padrao"}'`.
  Pesquisa externa não é verdade: separe tendência passageira de técnica consistente e compare com o padrão atual.
  Um achado só vira técnica do catálogo por proposta aprovada. No fim: `aprendizado.py rotina pesquisa`.

## Experimentos (só com hipótese relevante)

Não gere versões de todo vídeo. Exemplo (talking head): A frase de impacto, B direto na fala, C B-roll com narração,
o resto igual. `experimento criar '{"hipotese","formato","variantes":{"A":"…","B":"…"},"constantes":[…],"metrica_principal":"retencao_3s_pct"}'`,
`experimento resultado <id> <variante> <projeto> '{...}'`, `experimento avaliar <id>`. Abaixo de 3 por variante ou
diferença < 20 % = inconclusivo. Mesmo com sinal, vira proposta, nunca regra direta.

## Central de Melhorias

`propor '<json>'` exige: `titulo`, `descricao`, `escopo` (global | formato | marca | projeto), `alvo`
(`global`, `padrao`, `formato:<id>`, `tecnica:<id>`, `combinacao:<id>`, `marca:<arroba>`, `marca:<arroba>/formato:<id>`,
`projeto:<nome>`), `tipo`, `problema`, `evidencias`, `confianca` (baixa | media | alta), `limitacoes`,
`efeitos_colaterais`, `mudancas` ([{chave, para} | {chave, remover: true}]), `impacto_esperado`; opcionais `amostra`,
`comparabilidade`, `formato`, `fontes`. Estados: rascunho → aguardando_aprovacao → aprovada | rejeitada → (revertida).
`propostas [--status S] [--marca X]`, `mostrar`, `aprovar --por`, `rejeitar --por --motivo`, `reverter --por --motivo`,
`historico`. Aprovar num formato não propaga para outros formatos. Ao apresentar uma proposta ao dono, mostre em
linguagem simples: o que muda, por quê, com quantos casos, o risco e como desfazer.

## Formatos e combinações

Os 8 perfis oficiais estão em `conhecimento/formatos.json` (explicação em `references/formatos.md`). Cada um tem
`aprende` (o que aquele formato aprende), parâmetros, técnicas, anti-padrões e versão própria. Combinações
(`--combina`) somam as técnicas dos formatos de origem; o formato principal vence nos parâmetros. Cada uso fica
registrado em `<marca>/aprendizado/combinacoes.jsonl` (contexto e, depois, resultado).
