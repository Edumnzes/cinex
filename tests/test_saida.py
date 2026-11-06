"""Delivery folder and readable names (saida.py)."""
import json, os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import saida as S


class TestSaida(unittest.TestCase):
    def test_nome(self):
        self.assertEqual(S.nome("Ynvest - Entrega Euroville", "vertical", "2026-11-06"), "2026-11-06 Ynvest - Entrega Euroville (Reels 9x16)")
        self.assertEqual(S.nome("IMG_5054_app", "horizontal", "2026-10-25"), "2026-10-25 IMG 5054 app (Horizontal 16x9)")
        self.assertEqual(S.nome("2026-01-02 Já datado: a/b?", "led"), "2026-01-02 Já datado- a-b (Painel LED 512x384)")

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
