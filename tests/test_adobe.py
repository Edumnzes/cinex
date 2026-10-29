"""Adobe Podcast Enhance Speech from the app (D-02): a separate, locked-down `claude -p` call with a fixed prompt, only
the Adobe connector + the two network tools of `cinex_mcp.py --voz`, and the local fallback.
No test touches the real `claude`, Adobe or the internet: `mcp list` and `-p` come from tests/fake_claude.py and
upload/download go to a local http.server."""
import json, os, subprocess, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.base import C, FAKE, P, PY, REPO, ProjectCase

import cinex_mcp as M  # noqa: E402  (scripts/ is on sys.path through tests.base)

MCP = REPO / "scripts" / "cinex_mcp.py"
ADOBE = "claude.ai Adobe for creativity: https://adobe-creativity.adobe.io/mcp - ✔ Connected\n"


def arg(cmd, flag): return cmd[cmd.index(flag) + 1]


def mcp(argv, *reqs):
    """One MCP session of `cinex_mcp.py <argv...>`: initialize, then each (method, params) -> [result | error]."""
    msgs = [dict(jsonrpc="2.0", id=0, method="initialize", params=dict(protocolVersion="2025-11-25", capabilities={},
                                                                        clientInfo=dict(name="teste", version="1"))),
            dict(jsonrpc="2.0", method="notifications/initialized")]
    msgs += [dict(jsonrpc="2.0", id=i + 1, method=m, params=p) for i, (m, p) in enumerate(reqs)]
    r = subprocess.run([PY, str(MCP), *argv], input="".join(json.dumps(m) + "\n" for m in msgs).encode("utf-8"),
                       capture_output=True, timeout=60)
    out = [json.loads(x) for x in r.stdout.decode("utf-8").splitlines() if x.strip()]
    return [x.get("result", x.get("error")) for x in out[1:]]


class FakeCase(ProjectCase):
    """ProjectCase + the fake CLI (C.CLAUDE_CMD) logging to the temp folder; FAKE_MCP / ADOBE_HEADLESS restored."""

    def setUp(self):
        super().setUp(); self.make_project("t1")
        self._saved = (C.CLAUDE_CMD, C.ADOBE_HEADLESS, {k: os.environ.get(k) for k in ("FAKE_CLAUDE_LOG", "FAKE_MCP")})
        os.environ["FAKE_CLAUDE_LOG"] = str(Path(self._tmp.name) / "fake_claude.log")
        self.use("ok")

    def tearDown(self):
        C.CLAUDE_CMD, C.ADOBE_HEADLESS, env = self._saved
        for k, v in env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        super().tearDown()

    def use(self, scen): C.CLAUDE_CMD = [PY, str(FAKE), scen]

    def fake_log(self):
        p = Path(os.environ["FAKE_CLAUDE_LOG"])
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x] if p.exists() else []

    def evs(self): return [e["ev"] for e in self.fake_log()]

    def voice(self):
        vd = P.folder("t1") / "voz"; vd.mkdir(exist_ok=True)
        (vd / "voice.wav").write_bytes(b"RIFF....WAVE"); return vd


class TestAdobeServer(FakeCase):
    def test_found(self):
        self.assertEqual(C.adobe_server(), "claude_ai_Adobe_for_creativity")
        self.assertEqual(self.evs(), ["mcp"])

    def test_missing(self):
        os.environ["FAKE_MCP"] = "claude.ai Gmail: https://gmail.mcp.claude.com/mcp - ✔ Connected\n"
        self.assertIsNone(C.adobe_server())

    def test_needs_auth(self):
        os.environ["FAKE_MCP"] = "claude.ai Adobe for creativity: https://adobe-creativity.adobe.io/mcp - ! Needs authentication\n"
        self.assertIsNone(C.adobe_server())


class TestAdobeVoice(FakeCase):
    def test_off(self):
        self.voice(); C.ADOBE_HEADLESS = False
        self.assertEqual(C.adobe_voice("t1")["estado"], "indisponivel")
        self.assertEqual(self.evs(), [])

    def test_no_server(self):
        self.voice(); os.environ["FAKE_MCP"] = ""
        self.assertEqual(C.adobe_voice("t1")["estado"], "indisponivel")
        self.assertIn("mcp", self.evs()); self.assertNotIn("start", self.evs())

    def test_no_voice(self):
        self.assertEqual(C.adobe_voice("t1")["estado"], "indisponivel")
        self.assertNotIn("start", self.evs())

    def test_ok(self):
        vd = self.voice(); self.use("adobe_ok")
        r = C.adobe_voice("t1")
        self.assertEqual((r["estado"], Path(r["fala"]), r["fundo"]), ("ok", vd / "fala.wav", None))
        self.assertIn('"result"', (vd / "adobe.log").read_text(encoding="utf-8"))

    def test_meio(self):
        self.voice(); self.use("adobe_meio")
        self.assertEqual(C.adobe_voice("t1")["estado"], "falhou")

    def test_command(self):
        P.say("t1", "limpa minha voz SEGREDO-123", who="user")
        vd = self.voice(); self.use("adobe_ok"); C.adobe_voice("t1")
        st = [e for e in self.fake_log() if e["ev"] == "start"]
        self.assertEqual(len(st), 1)
        cmd, stdin = st[0]["argv"], st[0]["stdin"]
        for flag, val in [("--tools", ""), ("--permission-mode", "dontAsk"), ("--setting-sources", ""),
                          ("--allowedTools", "mcp__cinex,mcp__claude_ai_Adobe_for_creativity"),
                          ("--system-prompt-file", str(C.ADOBE_PROMPT_FILE)), ("--output-format", "stream-json")]:
            with self.subTest(flag=flag): self.assertEqual(arg(cmd, flag), val)
        self.assertEqual(json.loads(arg(cmd, "--mcp-config"))["mcpServers"]["cinex"]["args"][-2:], ["t1", "--voz"])
        self.assertNotIn("--strict-mcp-config", cmd)
        self.assertNotIn("SEGREDO-123", stdin); self.assertNotIn("SEGREDO-123", " ".join(cmd))
        self.assertIn(str(vd / "voice.wav"), stdin)
        self.assertEqual(Path(st[0]["cwd"]), P.folder("t1"))


class _H(BaseHTTPRequestHandler):
    body, got = b"", None
    def log_message(self, *a): pass
    def do_PUT(self):
        type(self).got = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers()
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Length", str(len(self.body))); self.end_headers()
        self.wfile.write(self.body)


class TestVozMcp(ProjectCase):
    def setUp(self):
        super().setUp(); self.make_project("t1")

    def names(self, *argv): return {t["name"] for t in mcp(argv, ("tools/list", {}))[0]["tools"]}

    def call(self, argv, tool, **args): return mcp(argv, ("tools/call", dict(name=tool, arguments=args)))[0]

    def test_tools(self):
        self.assertEqual(self.names("t1", "--voz"), {"enviar_audio", "baixar_voz"})
        self.assertFalse(self.names("t1") & {"enviar_audio", "baixar_voz"})

    def test_bad_mode(self):
        r = subprocess.run([PY, str(MCP), "t1", "--outro"], input=b"", capture_output=True, timeout=30)
        self.assertNotEqual(r.returncode, 0); self.assertEqual(r.stdout, b"")

    def test_url_ok(self):
        self.assertTrue(M.url_ok("https://storage.adobe.io/a?sig=1"))
        self.assertTrue(M.url_ok("https://adobe.com/a"))
        for u in ("http://x.adobe.io/a", "https://evil.com/a", "https://adobe.io.evil.com/a", "https://u:p@x.adobe.io/a",
                  "https://x.adobe.io:8443/a", "https://evil-adobe.io/a", "file:///C:/x.wav", "", None, 3):
            with self.subTest(u=u): self.assertFalse(M.url_ok(u))

    def test_put_get(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{srv.server_address[1]}/x"
            src = Path(self._tmp.name) / "voice.wav"; src.write_bytes(b"voz" * 1000)
            M._put(url, src); self.assertEqual(_H.got, src.read_bytes())
            _H.body = b"limpa" * 1000; dest = Path(self._tmp.name) / "fala.wav"; dest.write_bytes(b"velho")
            M._get(url, dest); self.assertEqual(dest.read_bytes(), _H.body)
            self.assertEqual([p.name for p in dest.parent.glob("*.tmp")], [])
        finally: srv.shutdown(); srv.server_close()

    def test_one_shot(self):
        vd = P.folder("t1") / "voz"; vd.mkdir(); (vd / "voice.wav").write_bytes(b"x"); (vd / "enviado").write_text("1")
        r = self.call(("t1", "--voz"), "enviar_audio", endereco="https://x.adobe.io/a")
        self.assertTrue(r["isError"]); self.assertIn("já foi enviado", r["content"][0]["text"])

    def test_bad_url_refused(self):
        vd = P.folder("t1") / "voz"; vd.mkdir(); (vd / "voice.wav").write_bytes(b"x")
        for tool, args in (("enviar_audio", dict(endereco="https://evil.com/a")), ("baixar_voz", dict(fala="http://x.adobe.io/a.wav")),
                           ("baixar_voz", dict(fala="https://x.adobe.io/a.wav", fundo="https://evil.com/b.wav"))):
            with self.subTest(tool=tool, args=args): self.assertTrue(self.call(("t1", "--voz"), tool, **args)["isError"])
        self.assertFalse((vd / "enviado").exists())
        self.assertEqual(sorted(p.name for p in vd.iterdir()), ["voice.wav"])

    def test_confirmar_adobe(self):
        r = self.call(("t1",), "confirmar", acao="adobe")
        self.assertFalse(r["isError"], r)
        self.assertFalse((P.folder("t1") / "voz").exists())
