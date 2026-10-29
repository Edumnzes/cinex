"""scripts/cinex_mcp.py: the chat AI's only tools, bound to the project in argv (CHAT-02, D-03, D-04)."""
import json, subprocess

from tests.base import P, PY, REPO, ProjectCase

MCP = REPO / "scripts" / "cinex_mcp.py"
ALLOWLIST = {"ver_projeto", "cortar_ou_manter", "corrigir_texto", "ajustar", "camera_lenta", "versao_curta",
             "revisar", "ressincronizar", "voltar_como_estava", "confirmar"}
FORBIDDEN = {"name", "nome", "projeto", "project", "path", "caminho", "arquivo", "file", "src", "url"}


class TestMcp(ProjectCase):
    def setUp(self):
        super().setUp(); self.make_project("t1"); self.make_project("t2")

    def mcp(self, name, *reqs):
        """One MCP session: initialize + initialized, then each (method, params). -> [result | error] by request."""
        msgs = [dict(jsonrpc="2.0", id=0, method="initialize", params=dict(protocolVersion="2025-11-25", capabilities={},
                                                                            clientInfo=dict(name="teste", version="1"))),
                dict(jsonrpc="2.0", method="notifications/initialized")]
        msgs += [dict(jsonrpc="2.0", id=i + 1, method=m, params=p) for i, (m, p) in enumerate(reqs)]
        r = subprocess.run([PY, str(MCP), name], input="".join(json.dumps(m) + "\n" for m in msgs).encode("utf-8"),
                           capture_output=True, timeout=60)
        out = [json.loads(x) for x in r.stdout.decode("utf-8").splitlines() if x.strip()]
        self.assertEqual(out[0]["result"]["protocolVersion"], "2025-11-25", r.stderr)
        return [x.get("result", x.get("error")) for x in out[1:]]

    def call(self, name, tool, **args):
        return self.mcp(name, ("tools/call", dict(name=tool, arguments=args)))[0]

    def tools(self): return self.mcp("t1", ("tools/list", {}))[0]["tools"]

    def test_allowlist(self):
        self.assertEqual({t["name"] for t in self.tools()}, ALLOWLIST)

    def test_no_project_param(self):
        for t in self.tools():
            with self.subTest(tool=t["name"]):
                self.assertFalse(set(t["inputSchema"]["properties"]) & FORBIDDEN)
                self.assertIs(t["inputSchema"]["additionalProperties"], False)

    def test_bad_argv(self):
        (P.ROOT / "semjson").mkdir()
        for name in ("..\\x", "a/b", "semjson", "naoexiste"):
            with self.subTest(name=name):
                r = subprocess.run([PY, str(MCP), name], input=b"", capture_output=True, timeout=30)
                self.assertNotEqual(r.returncode, 0); self.assertEqual(r.stdout, b"")

    def test_edit_only_own_project(self):
        r = self.call("t1", "ajustar", campo="captions", valor={"size": 80})
        self.assertFalse(r["isError"], r); self.assertIn("legendas:", r["content"][0]["text"])
        self.assertEqual(P.load("t1")["captions"]["size"], 80)
        self.assertEqual((P.load("t2")["captions"]["size"], P.load("t2")["rev"]), (62, 0))

    def test_bad_value(self):
        for args in (dict(campo="captions", valor={"size": "enorme"}), dict(campo="captions", valor={"nada": 1}),
                     dict(campo="music", valor={"src": "C:/x.mp3"}), dict(campo="motion_engine", valor="outro")):
            with self.subTest(args=args):
                self.assertTrue(self.call("t1", "ajustar", **args)["isError"])
        st = P.load("t1"); self.assertEqual((st["captions"]["size"], st["rev"], st.get("music")), (62, 0, None))

    def test_snapshot_once(self):
        r = self.mcp("t1", ("tools/call", dict(name="ajustar", arguments=dict(campo="captions", valor={"size": 80}))),
                     ("tools/call", dict(name="ajustar", arguments=dict(campo="captions", valor={"size": 90}))))
        self.assertFalse(any(x["isError"] for x in r), r)
        snap = json.loads((P.folder("t1") / "ponto_salvo.json").read_text(encoding="utf-8"))
        self.assertEqual((snap["captions"]["size"], snap["rev"]), (62, 0))
        P.say("t1", "volta como estava", who="user"); rev = P.load("t1")["rev"]
        r = self.call("t1", "voltar_como_estava")
        self.assertFalse(r["isError"], r)
        st = P.load("t1")
        self.assertEqual(st["captions"]["size"], 62)
        self.assertEqual(st["chat"][-1]["text"], "volta como estava")
        self.assertGreater(st["rev"], rev)

    def test_version_exists(self):
        d = P.folder("t1_15s"); d.mkdir(); (d / "meu.txt").write_text("editado")
        r = self.call("t1", "versao_curta", segundos=15)
        self.assertTrue(r["isError"]); self.assertIn("já existe", r["content"][0]["text"])
        self.assertTrue((d / "meu.txt").exists())

    def test_confirmar(self):
        r = self.call("t1", "confirmar", acao="exportar")
        self.assertFalse(r["isError"], r); self.assertIn("Não diga que já foi feito", r["content"][0]["text"])
        self.assertEqual(P.load("t1")["rev"], 0)                        # shows a button, changes nothing
        self.assertFalse((P.folder("t1") / "ponto_salvo.json").exists())
        self.assertFalse((P.folder("t1") / "export.json").exists())
        self.assertTrue(self.call("t1", "confirmar", acao="apagar")["isError"])
        self.assertTrue(self.call("t1", "confirmar")["isError"])
