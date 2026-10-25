# Termos de Uso e Privacidade

Última atualização: 29/09/2026

Estes termos valem para qualquer pessoa autorizada a usar a skill **Cinex** (antigo Reels Editor)
(o "Software"). O uso do Software também está sujeito à [LICENSE.md](LICENSE.md).
Ao usar o Software, você concorda com estes termos.

## 1. O que o Software é
Um conjunto de instruções e scripts que orienta o Claude Code (Anthropic) a editar vídeos
curtos no seu computador. O Software **não** é um serviço hospedado: o processamento de vídeo
acontece localmente, exceto nas integrações opcionais descritas na seção 4.

## 2. Suas responsabilidades sobre o conteúdo
Ao editar um vídeo, você declara que:
- tem os direitos sobre o material de origem ou autorização de quem os tem;
- tem o **consentimento das pessoas que aparecem** no vídeo para uso da imagem e da voz
  (art. 5º, X, da Constituição Federal e Código Civil, art. 20), especialmente em uso comercial;
- tem autorização para usar marcas, logotipos e nomes de terceiros exibidos (clientes,
  fornecedores, eventos);
- conferiu as informações exibidas na tela (dados técnicos, preços, datas, locais, @) antes
  de publicar. O Software sugere textos a partir da fala, mas **a revisão final é sua**.

É proibido usar o Software para produzir conteúdo enganoso, difamatório, que viole direitos
de terceiros ou a legislação, ou que imite pessoas ou empresas sem autorização.

## 3. Transcrições e textos gerados
Legendas e textos são gerados automaticamente (reconhecimento de fala) e podem conter erros.
O Software faz verificações, mas não garante exatidão. Revise antes de publicar.

## 4. Privacidade e dados (LGPD)
| Dado | Onde é processado |
|---|---|
| Vídeo (imagem) | Somente no seu computador |
| Transcrição | Localmente (faster-whisper); o texto também é lido pelo Claude durante a sessão |
| Quadros de conferência (miniaturas, prévias) | Lidos pelo Claude durante a sessão |
| Trilha de voz | Enviada ao **Adobe Creative Cloud / Adobe Podcast** somente se você usar o conector Adobe |
| Perfil da marca (briefing, análise do Instagram, métricas) | Salvo em texto no seu computador (`~/instagram-legendas/<arroba>/`); lido pelo Claude durante a sessão |

- O uso do Claude está sujeito aos termos e à política de privacidade da **Anthropic**.
- O uso do tratamento de voz está sujeito aos termos e à política de privacidade da **Adobe**;
  o arquivo de voz fica armazenado na sua conta Creative Cloud até que você o apague.
- Se o vídeo contiver dados pessoais de terceiros (rosto, voz, nome), você é o controlador
  desses dados nos termos da Lei nº 13.709/2018 (LGPD) e deve ter base legal para tratá-los.
- O Software não coleta telemetria nem envia dados ao titular.

### Acesso ao Instagram
- O login é feito **por você**, no seu navegador. O Software instrui o Claude a **nunca digitar senhas,
  códigos ou credenciais** e a apenas **ler** o perfil, os Reels e os Insights — sem curtir, comentar,
  seguir, enviar mensagens ou alterar configurações.
- Autorize a análise somente de contas que você administra ou para as quais tem autorização do titular.
- A leitura automatizada deve respeitar os Termos de Uso do Instagram/Meta; use-a com moderação
  (poucas dezenas de páginas, na sua própria conta).
- Os arquivos do perfil ficam só no seu computador. Para apagar, exclua a pasta
  `~/instagram-legendas/<arroba>/`.

## 5. Recursos de terceiros
- **Efeitos sonoros, músicas, imagens e vídeos de apoio** não acompanham o Software. Use apenas
  arquivos cuja licença permita o seu uso (ex.: Mixkit, Pixabay, Motion Array, Envato, Artlist),
  respeitando as condições de cada banco. O Software não baixa assets sem sua autorização.
- **Banco do usuário** (`~/reels-banco`: fontes, motions, sons, referências): é seu e fica só no seu
  computador. Você é responsável pelas licenças de cada item; registre a origem/licença junto do arquivo.
  Referências de outros perfis servem para estudar estrutura e decisões de edição — não copie conteúdo,
  roteiro, marca ou assets de terceiros.
- **Fontes e modelo de detecção** incluídos seguem as licenças em
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- **Estilos de referência** citados na documentação (criadores e perfis públicos) servem apenas
  como inspiração de princípios; não copie obras de terceiros.
- Conteúdo publicado deve respeitar as regras das plataformas (Instagram, TikTok, YouTube).

## 6. Limitação de responsabilidade
O Software é fornecido "no estado em que se encontra". O titular não se responsabiliza por
conteúdo publicado, perdas de arquivos, custos de serviços de terceiros (Anthropic, Adobe,
bancos de assets) ou danos decorrentes do uso. Mantenha cópia dos seus vídeos originais.

## 7. Alterações
Estes termos podem ser atualizados; a versão válida é a deste repositório.
