# Legendas para Instagram

Parte do Cinex (antes era a skill separada `legendas-instagram`). Serve para os vídeos editados aqui e
para qualquer post (carrossel, foto, Reels de fora). Os dados da marca ficam na mesma pasta do perfil
do Cinex: `~/instagram-legendas/<arroba>/` (`perfil.md`, `historico.md`, `marca.json`, `video.md`).

Objetivo: uma legenda que (1) faça a pessoa parar e abrir o "mais", (2) seja encontrada
pela busca do Instagram e do Google, (3) gere envio, salvamento ou comentário — os sinais
que levam o post a quem ainda não segue — e (4) soe como o dono do perfil escrevendo,
não como uma IA ou uma agência genérica. Se tiver que escolher entre um truque de
engajamento e a naturalidade, fique com a naturalidade: texto que parece robótico
perde confiança e o público rola a tela.

Fale com o usuário em português simples, sem jargão de marketing.

## Visão geral do fluxo

1. **Perfil de voz** — carregar ou criar o arquivo do perfil (feito uma vez, reaproveitado).
2. **Conteúdo** — entender o que vai ser publicado.
3. **Estratégia** — decidir objetivo, público do post, palavra-chave, ângulo e CTA.
4. **Escrever** — rascunho, depois revisão de naturalidade.
5. **Checar e entregar** — rodar o script de verificação e apresentar.

Leia `references/legendas-tecnicas.md` antes de escrever a primeira legenda da sessão: ele tem
tamanhos por formato, modelos de gancho, estruturas, regras de hashtag e formatação.

Se o `perfil.md` da marca tem uma seção **"Modelo aprovado pelo dono"**, ela manda: escreva no formato
daquele exemplo. Ela vem de uma legenda que deu certo e de uma que o dono recusou.

---

## 1. Perfil de voz (a base de tudo)

A qualidade da legenda depende de entender o negócio e o jeito de escrever do dono.
Por isso a análise é salva em arquivo e reaproveitada — ninguém quer responder às
mesmas perguntas a cada post.

**Onde fica:** `~/instagram-legendas/<arroba>/perfil.md` (sem o @). Na mesma pasta,
`historico.md` guarda as legendas já entregues.

- Se o arquivo existe: leia-o e siga. Pergunte só se algo parecer desatualizado
  (ex.: novo produto, mudança de público). Leia também as últimas ~10 entradas do
  `historico.md` para não repetir ganchos, aberturas e CTAs.
- Se não existe: crie a partir de `references/legendas-perfil-template.md`, coletando como abaixo.

### Como coletar (use o que estiver disponível, na ordem)

1. **Perfil público no navegador.** Peça o @ e abra `instagram.com/<arroba>/` no
   navegador disponível. Se o Claude in Chrome estiver conectado, prefira-o (o usuário
   já está logado e o Instagram mostra mais). Colete: nome, bio, link, destaques,
   categoria, nº aproximado de seguidores, e abra **12–20 posts recentes** para ler as
   legendas completas, os formatos e os comentários. Nunca curta, comente, siga ou
   altere nada — só leitura.
2. **Material do usuário.** Se o navegador não conseguir (login, bloqueio), peça prints
   do perfil e de algumas legendas, ou que cole 5–10 legendas antigas de que ele gosta.
3. **Insights.** Peça um print de *Painel profissional → Insights → Público*
   (idade, gênero, cidades), *Visualizações* e *Interações* (seguidores × não seguidores)
   e *Horários de maior atividade*. Isso é o **público atual** de fato, não o imaginado.
   Compare as duas divisões: se não seguidores são boa parte das visualizações mas quase
   não interagem, o conteúdo já chega a desconhecidos e o problema é gancho/CTA falando só
   com quem já conhece a marca. Poucos toques no link da bio → CTA direto (Direct/WhatsApp).
   Com a conta logada no navegador, dá para ler sozinho: `instagram.com/accounts/insights/`
   (visão da conta) e o botão **"Ver insights"** de cada post (visualizações, % de não
   seguidores, compartilhamentos, salvamentos, visitas ao perfil). Leia os de ~10 posts
   variados e monte uma tabela no perfil: curtida engana — o que importa para alcance são
   compartilhamentos e % de não seguidores, e para venda são as visitas ao perfil.
   Idade e cidades só aparecem no app → peça print.
4. **Entrevista curta** para o que não dá para ver (no máximo 5–6 perguntas de uma vez):
   o que o negócio vende e para quem; o diferencial; quem é o **cliente ideal**
   (público-alvo) e o que ele pesquisa/teme/deseja; região de atuação; objetivo
   principal do Instagram (vender, autoridade, gerar orçamento, comunidade); palavras
   ou temas proibidos; se usa automação de DM ("comente X e receba").

### O que extrair das legendas antigas (a identidade de escrita)

Isto é o que torna a legenda "dele". Observe e registre com exemplos reais:
- pessoa do discurso (eu / a gente / nós / marca em 3ª pessoa) e como chama o leitor
  (você, vocês, "meu amigo", apelido da comunidade);
- tamanho típico de frase, ritmo, se usa frases soltas de uma linha;
- vocabulário e expressões recorrentes, gírias, regionalismos, bordões;
- nível de formalidade, humor, uso de emoji (quais, quantos, onde);
- como abre e como fecha os textos; CTAs que já usa;
- quais legendas tiveram mais comentários — o que elas têm em comum.

Se o perfil é novo ou as legendas antigas são fracas/genéricas, diga isso com
franqueza e proponha uma voz com base no negócio e no público; confirme com o usuário.

### Público atual × público-alvo

Compare o que os Insights e os comentários mostram com o cliente ideal descrito.
Registre a **lacuna** (ex.: "seguidores são outros instaladores; cliente ideal é o
dono de casa em Campinas que paga conta de luz alta"). Essa lacuna orienta vocabulário
e ganchos: para alcançar quem ainda não segue, escreva na língua do público-alvo,
sem perder quem já segue.

Mostre ao usuário um resumo do perfil (5–8 linhas) e peça confirmação antes de salvar.

---

## 2. Entender o conteúdo

Olhe o material de verdade, não só a descrição:
- **Carrossel:** leia todos os slides em ordem. Identifique a promessa da capa, o
  conteúdo de cada slide e o slide final. A legenda complementa — não copia os slides.
- **Post de foto:** o que a imagem mostra, contexto, pessoas, lugar, produto.
- **Reels:** peça o roteiro/fala ou transcreva. Se houver ffmpeg, extraia alguns
  quadros para ver o que aparece (`ffmpeg -i video.mp4 -vf fps=1/3 q%02d.jpg`). Se a
  edição foi feita aqui no Cinex, reutilize a transcrição do projeto (`words.json`). Anote o texto que
  aparece na tela e o gancho dos 3 primeiros segundos.
- Pergunte, se não for óbvio: objetivo do post (alcance, venda, autoridade, relacionamento),
  alguma oferta/data/link, e se é collab ou tem alguém a marcar.

---

## 3. Estratégia (pense antes de escrever)

Defina rapidamente — e mostre em 3–5 linhas ao entregar:
- **Objetivo do post** e **quem ele deve alcançar** (atual, alvo ou ambos).
- **Palavra-chave principal** que esse público digitaria na busca (ex.: "energia solar
  para casa", "quanto custa placa solar"). Ela entra de forma natural na 1ª ou 2ª frase
  e de novo no corpo. É o que faz o post ser encontrado na busca e no Google.
- **Sinal de alcance a buscar:** envio (conteúdo que a pessoa quer mandar para alguém),
  salvamento (conteúdo de consulta), ou comentário (opinião, pergunta, palavra-chave).
  Envios são o sinal mais forte para chegar a não seguidores; pense "para quem essa
  pessoa mandaria isso?".
- **Ângulo/gancho** que ainda não foi usado recentemente (confira o histórico).
- **Tamanho** conforme o formato (ver `references/legendas-tecnicas.md`).

---

## 4. Escrever

Estrutura base: **Gancho → Contexto/valor → Conversa (CTA)**, com hashtags ao final.

- **Gancho (primeiros ~125 caracteres):** é tudo que aparece antes do "mais". Precisa
  funcionar sozinho e, idealmente, conter a palavra-chave. Não repita literalmente o
  texto da capa/do vídeo — complemente ou provoque por outro ângulo.
- **Corpo:** entregue algo — contexto, história curta, o porquê, um dado, um erro comum.
  Frases curtas, uma ideia por parágrafo, linha em branco entre blocos.
- **CTA:** um só, específico e coerente com o sinal escolhido, separado por linha em
  branco. Prefira CTAs que soem como conversa ("Manda pra quem tá pensando em colocar
  placa esse ano") a ordens genéricas ("Curta, comente e compartilhe!").
- **Hashtags:** até 5 (limite atual do Instagram), específicas do tema + nicho/região.

### Revisão de naturalidade (obrigatória antes de entregar)

Releia como se fosse o dono do perfil lendo em voz alta. Corte o que ele nunca diria.
Marcas típicas de texto de IA a remover:
- aberturas feitas ("Você sabia que…?", "Já parou para pensar…", "No mundo de hoje…",
  "Descubra…", "Prepare-se para…") — a menos que a pessoa realmente escreva assim;
- palavras infladas: "incrível", "transformador", "jornada", "potencializar",
  "alavancar", "desvendar", "mergulhar", "elevar ao próximo nível", "não é apenas X, é Y";
- listas de três adjetivos, travessões em excesso, emoji no início de toda linha;
- frases motivacionais vazias no final;
- tom genérico que caberia em qualquer perfil do nicho — inclua algo concreto do
  negócio (cidade, caso real, número, bastidor, jeito de falar).

Siga o nível de formalidade e emoji do perfil de voz, mesmo que as "boas práticas"
digam outra coisa. A identidade vence a regra geral.

---

## 5. Checar e entregar

Salve a legenda em um arquivo `.txt` e rode:

```
python scripts/checar_legenda.py legenda.txt --formato reels|carrossel|foto
```

Ele mostra a prévia antes do "mais", contagem de caracteres/palavras, hashtags,
menções, emojis e alertas (passou de 2.200, mais de 5 hashtags, gancho longo, link
não clicável, frases típicas de IA). Corrija os alertas que fizerem sentido.

### Formato da entrega: arquivo Word (.docx), não .txt

O dono quer as legendas num documento que abre no Word / Google Docs. Monte um JSON com os posts e gere:

```
python scripts/legenda_docx.py legendas.json ~/Downloads/<nome>_legendas.docx
```

`legendas.json` = `{"titulo": "...", "intro": ["parágrafo", ...], "posts": [{"tema", "txt", "kw", "sinal", "ganchos": [...],
"capa", "alt", "data"?, "arq"?, "estrategia"?}]}`. Com 2 posts ou mais, entra a tabela da ordem de postagem (data, arquivo,
tema, sinal). A legenda vai num bloco cinza, linha por linha, pronta para copiar. Abra o arquivo antes de entregar
(no Windows, Word via PowerShell `Word.Application`) e confirme que existe na pasta.

Na conversa, resuma o mesmo conteúdo:

```
**Estratégia:** objetivo · público · palavra-chave · sinal buscado (2–4 linhas)

**Legenda** (pronta para copiar, em bloco de código para preservar quebras de linha)

**Ganchos alternativos:** 2 opções de primeira frase com ângulos diferentes

**Texto alternativo (acessibilidade):** 1–2 frases descrevendo a imagem/vídeo com a palavra-chave
**Extras** (só se fizer sentido): texto de capa do Reels, sugestão de 1º comentário,
marcações, convite de colaboração (collab), localização, melhor horário para postar
(dos Insights salvos no perfil)
```

Depois de entregar, acrescente ao `historico.md`: data, formato, tema, gancho usado,
CTA e palavra-chave. Se o usuário corrigir algo na voz ("eu não falo assim", "menos
emoji"), atualize o `perfil.md` na hora — é assim que a skill vai ficando com a cara dele.

## Pedidos parciais

- "Só hashtags" / "só o gancho" / "melhora essa legenda": use o perfil de voz e faça só
  a parte pedida. Numa reescrita, preserve as ideias e frases boas do usuário.
- Vários posts de uma vez: faça a estratégia de cada um e varie ganchos e CTAs entre eles.
