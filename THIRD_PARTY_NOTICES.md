# Avisos de terceiros

O Software inclui ou depende dos componentes abaixo, cada um sob a sua própria licença.
A licença MIT do repositório ([LICENSE.md](LICENSE.md)) cobre só o código e a documentação do Cinex;
estes componentes seguem as licenças abaixo.

## Incluídos no repositório (`assets/`)

| Arquivo | Componente | Autor | Licença |
|---|---|---|---|
| `Montserrat.ttf` | Montserrat (variável) | The Montserrat Project Authors | SIL Open Font License 1.1 |
| `SerifItalic.ttf` | Libre Baskerville Italic | Impallari Type | SIL Open Font License 1.1 |
| `BebasNeue-Regular.ttf` | Bebas Neue | Dharma Type | SIL Open Font License 1.1 |
| `Caveat.ttf` | Caveat | Impallari Type | SIL Open Font License 1.1 |
| `yunet.onnx` | YuNet face detector (OpenCV Zoo) | Shiqi Yu et al. / OpenCV | MIT |

As fontes são distribuídas com o texto da licença em [assets/OFL.txt](assets/OFL.txt), como a
OFL exige. As fontes podem ser usadas livremente, inclusive em vídeos comerciais; não podem ser
vendidas isoladamente.

## Instalados pelo `setup_env.py` (não incluídos no repositório)

| Pacote | Licença |
|---|---|
| faster-whisper (SYSTRAN) e modelos Whisper (OpenAI) | MIT |
| opencv-python | Apache 2.0 (binários com componentes de terceiros próprios) |
| Pillow | MIT-CMU (HPND) |
| NumPy | BSD 3-Clause |
| imageio-ffmpeg | BSD 2-Clause; o binário do **FFmpeg** baixado é LGPL/GPL conforme a build |
| truststore | MIT |
| mediapipe (Google) e modelo selfie_multiclass_256x256 | Apache 2.0 |
| hyperframes (HeyGen, instalado à parte em ~/cinex-hf) + GSAP incluído nele | Apache 2.0 / licença do GSAP |

## Serviços e referências (não incluídos)

- **Adobe Podcast Enhance Speech / Creative Cloud**: acessado via conector Adobe for creativity,
  sujeito aos termos da Adobe.
- **Claude / Claude Code**: sujeito aos termos da Anthropic.
- **React Bits** (reactbits.dev, MIT + Commons Clause): nenhum código incluído; `scripts/fx.py`
  recria alguns efeitos de forma independente para quadros de vídeo.
- Bancos de assets citados (Motion Array, Envato Elements, Artlist, Mixkit, Pixabay, Freesound):
  nenhum arquivo incluído; cada download segue a licença do respectivo banco.
