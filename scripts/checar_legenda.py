"""Confere uma legenda de Instagram: prévia antes do "mais", tamanho, hashtags e alertas.

Uso: python checar_legenda.py legenda.txt [--formato reels|carrossel|foto]
     (ou passe o texto por stdin: ... | python checar_legenda.py -)
"""
import argparse
import re
import sys

LIMITE = 2200
PREVIA = 125
MAX_HASHTAGS = 5
MAX_MENCOES = 20
FAIXAS = {"reels": (150, 400), "carrossel": (400, 1500), "foto": (125, 600)}

# Expressões que costumam denunciar texto genérico/de IA em português.
CLICHES = [
    "você sabia que", "já parou para pensar", "já parou pra pensar", "no mundo de hoje",
    "descubra", "prepare-se", "jornada", "transformador", "transformadora", "incrível",
    "potencializar", "alavancar", "desvendar", "mergulhe", "mergulhar", "próximo nível",
    "não é apenas", "neste post", "nesse post vou", "fique por dentro", "sem mais delongas",
    "curta, comente", "curte, comenta",
]

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF]"
)


def previa(texto: str) -> str:
    """Aproxima o que aparece antes do 'mais': até 125 caracteres ou 2 quebras de linha."""
    linhas = texto.split("\n")
    corte = "\n".join(linhas[:2])
    return corte[:PREVIA]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo")
    ap.add_argument("--formato", choices=FAIXAS.keys())
    a = ap.parse_args()

    if a.arquivo == "-":
        texto = sys.stdin.read()
    else:
        with open(a.arquivo, encoding="utf-8") as f:
            texto = f.read()
    texto = texto.strip()

    n = len(texto)
    palavras = len(texto.split())
    hashtags = re.findall(r"#[\wÀ-ÿ]+", texto)
    mencoes = re.findall(r"@[\w.]+", texto)
    emojis = EMOJI_RE.findall(texto)
    primeira = texto.split("\n", 1)[0]

    print("=== PRÉVIA (antes do 'mais') ===")
    print(previa(texto) + ("…" if len(texto) > len(previa(texto)) else ""))
    print()
    print(f"Caracteres: {n}/{LIMITE} | Palavras: {palavras} | Linhas: {texto.count(chr(10)) + 1}")
    print(f"Hashtags ({len(hashtags)}): {' '.join(hashtags) or '-'}")
    print(f"Menções ({len(mencoes)}): {' '.join(mencoes) or '-'}")
    print(f"Emojis: {len(emojis)} ({len(set(emojis))} diferentes)")
    print(f"1ª linha: {len(primeira)} caracteres")

    alertas = []
    if n > LIMITE:
        alertas.append(f"Passou do limite: {n} > {LIMITE} caracteres.")
    if len(hashtags) > MAX_HASHTAGS:
        alertas.append(f"{len(hashtags)} hashtags; o Instagram aceita no máximo {MAX_HASHTAGS}.")
    if len(set(h.lower() for h in hashtags)) < len(hashtags):
        alertas.append("Hashtag repetida.")
    if len(mencoes) > MAX_MENCOES:
        alertas.append(f"{len(mencoes)} menções; máximo {MAX_MENCOES}.")
    if len(primeira) > PREVIA:
        alertas.append("1ª linha maior que a prévia: o gancho pode ser cortado pelo 'mais'.")
    if primeira.startswith("#") or not re.sub(EMOJI_RE, "", primeira).strip(" ️‍"):
        alertas.append("Legenda começa com hashtag/emoji solto: a prévia fica sem gancho.")
    if re.search(r"https?://|www\.", texto):
        alertas.append("Link na legenda não é clicável; use 'link na bio' ou o direct.")
    if len(set(emojis)) > 4:
        alertas.append(f"{len(set(emojis))} tipos de emoji: confira se combina com a voz do perfil.")
    baixo = texto.lower()
    achados = [c for c in CLICHES if c in baixo]
    if achados:
        alertas.append("Expressões com cara de texto genérico/IA: " + ", ".join(achados))
    if a.formato:
        mn, mx = FAIXAS[a.formato]
        if n < mn or n > mx:
            alertas.append(
                f"Fora da faixa típica de {a.formato} ({mn}–{mx}). Tudo bem se for intencional."
            )

    print()
    if alertas:
        print("=== ALERTAS ===")
        for x in alertas:
            print("- " + x)
    else:
        print("Sem alertas.")


if __name__ == "__main__":
    main()
