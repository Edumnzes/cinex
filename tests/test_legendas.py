"""Caption tools merged from legendas-instagram: the checker runs and the Word file is a valid .docx."""
import json, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path

S = Path(__file__).resolve().parent.parent / "scripts"
TXT = "12 placas em série passam de 400 V ⚡\n\n✔ um\n✔ dois\n\nManda pra quem tá pensando nisso ☀️\n\n#energiasolar #irece"


class TestLegendas(unittest.TestCase):
    def test_checker(self):
        out = subprocess.run([sys.executable, str(S / "checar_legenda.py"), "-", "--formato", "reels"], input=TXT,
                             capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("Hashtags (2)", out)

    def test_docx(self):
        with tempfile.TemporaryDirectory() as d:
            spec, out = Path(d) / "l.json", Path(d) / "l.docx"
            posts = [dict(tema=f"Post {i}", txt=TXT, kw="placa solar", sinal="envio", ganchos=["a"], capa="c", alt="x",
                          data=f"Ter 0{i}/12", arq=f"v{i}.mp4") for i in (1, 2)]
            spec.write_text(json.dumps(dict(titulo="T", intro=["i"], posts=posts), ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(S / "legenda_docx.py"), str(spec), str(out)], check=True, capture_output=True)
            with zipfile.ZipFile(out) as z:
                self.assertIn("word/document.xml", z.namelist())
                doc = z.read("word/document.xml").decode("utf-8")
            self.assertIn("<w:tbl>", doc)                       # posting-order table with 2+ posts
            self.assertIn("✔ dois", doc)                        # caption kept line by line
            self.assertIn("Manda pra quem tá pensando nisso", doc)


if __name__ == "__main__":
    unittest.main()
