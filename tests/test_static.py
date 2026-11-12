"""The editor loads several classic <script>s that share one global scope: a top-level name declared twice
(`const el` in fx.js and app.js) is a SyntaxError that stops the whole editor from loading."""
import re, unittest
from collections import Counter
from tests.base import REPO

STATIC = REPO / "app" / "static"
DECL = re.compile(r"^(?:const|let|class|function\*?|async function)\s+([A-Za-z_$][\w$]*)", re.M)


class StaticScriptsTest(unittest.TestCase):
    def check_page(self, page):
        srcs = re.findall(r'<script src="/static/([\w.-]+\.js)"', (STATIC / page).read_text(encoding="utf-8"))
        self.assertTrue(srcs)
        names = Counter()
        for s in srcs:
            for n in set(DECL.findall((STATIC / s).read_text(encoding="utf-8"))): names[n] += 1
        dup = sorted(n for n, k in names.items() if k > 1)
        self.assertEqual(dup, [], f"{page}: declared in more than one script: {dup}")

    def test_editor_scripts_have_unique_globals(self): self.check_page("index.html")
    def test_guide_scripts_have_unique_globals(self): self.check_page("guia.html")
