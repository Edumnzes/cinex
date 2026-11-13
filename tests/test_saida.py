"""Delivery folder and readable names (saida.py): Marca - Tema - NN - Formato Plataforma."""
import json, os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import saida as S


class TestSaida(unittest.TestCase):
    def test_nome(self):
        self.assertEqual(S.nome("Ynvest - Entrega Euroville", "vertical", 4), "Ynvest - Entrega Euroville - 04 - Reels 9x16 Instagram")
        self.assertEqual(S.nome("IMG_5054_app", "horizontal", 1), "IMG 5054 app - 01 - Horizontal 16x9 YouTube")
        self.assertEqual(S.nome("Ynvest: a/b?", "4x3", 12), "Ynvest- a-b - 12 - 4x3 Telão")
        self.assertEqual(S.nome("Unijus - IA", "vertical", 2, plataforma="TikTok"), "Unijus - IA - 02 - Reels 9x16 TikTok")

    def test_sequencia_por_marca(self):
        with tempfile.TemporaryDirectory() as d:
            for f in ("Ynvest - A - 01 - Reels 9x16 Instagram.mp4", "Ynvest - B - 02 - Reels 9x16 Instagram.mp4",
                      "Unijus - X - 07 - Reels 9x16 Instagram.mp4", "antigo sem numero.mp4"):
                (Path(d) / f).touch()
            self.assertEqual(S.sequencia("Ynvest - C", d), 3)              # próxima da marca
            self.assertEqual(S.sequencia("Ynvest - A", d), 1)              # nova versão do mesmo tema mantém o número
            self.assertEqual(S.sequencia("Unijus - Y", d), 8)
            self.assertEqual(S.sequencia("Nova - Z", d), 1)
            self.assertEqual(S.nome("Ynvest - C", folder=d), "Ynvest - C - 03 - Reels 9x16 Instagram")

    def test_pasta(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.environ.get("CINEX_ROOT"); os.environ["CINEX_ROOT"] = d
            try:
                self.assertEqual(S.pasta(), Path.home() / "Downloads")          # nothing configured
                (Path(d) / "_config.json").write_text(json.dumps({"saida": str(Path(d) / "entrega")}), encoding="utf-8")
                self.assertEqual(S.pasta(), Path(d) / "entrega")
                self.assertTrue((Path(d) / "entrega").is_dir())
            finally:
                if old is None: os.environ.pop("CINEX_ROOT")
                else: os.environ["CINEX_ROOT"] = old


if __name__ == "__main__":
    unittest.main()
