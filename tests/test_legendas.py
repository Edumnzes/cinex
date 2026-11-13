"""Caption checker (merged from legendas-instagram). Captions are delivered in the chat, no Word file (2026-11-12)."""
import subprocess, sys, unittest
from pathlib import Path

S = Path(__file__).resolve().parent.parent / "scripts"
TXT = "12 placas em série passam de 400 V ⚡\n\n✔ um\n✔ dois\n\nManda pra quem tá pensando nisso ☀️\n\n#energiasolar #irece"


class TestLegendas(unittest.TestCase):
    def test_checker(self):
        out = subprocess.run([sys.executable, str(S / "checar_legenda.py"), "-", "--formato", "reels"], input=TXT,
                             capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("Hashtags (2)", out)


if __name__ == "__main__":
    unittest.main()
