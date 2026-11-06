"""Instagram captions -> Word document (.docx), standard library only.

Usage: python legenda_docx.py legendas.json out.docx
legendas.json: {"titulo": "...", "intro": ["paragraph", ...],
                "posts": [{"tema", "txt", "kw", "sinal", "ganchos": [...], "capa", "alt",
                           "data"?, "arq"?, "estrategia"?}, ...]}
With 2+ posts a posting-order table (date, file, theme, signal) comes first; each post then gets its own page:
keyword, signal, the caption line by line on a grey block (ready to copy), alternative hooks, cover text, alt text.
"""
import json, sys, zipfile
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def run(text, bold=False, size=None, color=None):
    rpr = ("<w:b/>" if bold else "") + (f'<w:color w:val="{color}"/>' if color else "") + (f'<w:sz w:val="{size}"/>' if size else "")
    return f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def p(text="", bold=False, size=None, color=None, after=None, shade=None, keep=False):
    ppr = ((f'<w:spacing w:after="{after}"/>' if after is not None else "") + (f'<w:shd w:val="clear" w:fill="{shade}"/>' if shade else "")
           + ("<w:keepNext/>" if keep else ""))
    return f'<w:p>{f"<w:pPr>{ppr}</w:pPr>" if ppr else ""}{run(text, bold, size, color)}</w:p>'


def label(k, v):
    return f'<w:p><w:pPr><w:spacing w:after="60"/></w:pPr>{run(k + ": ", True)}{run(v)}</w:p>' if v else ""


def table(rows):
    cell = lambda t, b: f'<w:tc><w:p><w:pPr><w:spacing w:after="0"/></w:pPr>{run(t, b, 18)}</w:p></w:tc>'
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:color="BFBFBF"/>' for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    return (f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{border}</w:tblBorders></w:tblPr>'
            + "".join("<w:tr>" + "".join(cell(c, i == 0) for c in r) + "</w:tr>" for i, r in enumerate(rows)) + "</w:tbl>")


def build(spec):
    posts, B = spec["posts"], [p(spec.get("titulo", "Legendas"), True, 34)]
    B += [p(t, color="555555") for t in spec.get("intro", [])]
    if len(posts) > 1:
        B += [p(), table([["#", "Data", "Arquivo", "Tema", "Sinal buscado"]]
                         + [[str(i), x.get("data", ""), x.get("arq", ""), x["tema"], x.get("sinal", "")] for i, x in enumerate(posts, 1)])]
    for i, x in enumerate(posts, 1):
        if len(posts) > 1 or i > 1: B.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        head = f'{i}. {x["data"]} · {x["tema"]}' if x.get("data") else x["tema"]
        B += [p(head, True, 30, after=60)]
        if x.get("arq"): B.append(p("Arquivo: " + x["arq"], color="777777", after=160))
        B += [label("Estratégia", x.get("estrategia")), label("Palavra-chave", x.get("kw")), label("Sinal buscado", x.get("sinal")),
              p("Legenda (copie daqui)", True, 24, after=80, keep=True)]
        B += [p(l, shade="F2F4F7", after=0) for l in x["txt"].rstrip("\n").split("\n")]
        if x.get("ganchos"): B += [p(), p("Ganchos alternativos", True, 24, after=60)] + [p("• " + g, after=40) for g in x["ganchos"]]
        B += [p(), label("Texto da capa", x.get("capa")), label("Texto alternativo", x.get("alt"))]
    return ("".join(B))


def write(spec, out):
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{build(spec)}'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
           '</w:body></w:document>')
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W}><w:docDefaults>'
              '<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>'
              '<w:sz w:val="22"/><w:lang w:val="pt-BR"/></w:rPr></w:rPrDefault>'
              '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
              '</w:docDefaults></w:styles>')
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{rel}/styles" Target="styles.xml"/></Relationships>')
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)


if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    write(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
    print("ok", sys.argv[2])
