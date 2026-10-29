"""Adobe Podcast Enhance Speech from the app (D-02): a separate, locked-down `claude -p` call with a fixed prompt, only
the Adobe connector + the two network tools of `cinex_mcp.py --voz`, and the local fallback.
No test touches the real `claude`, Adobe or the internet: `mcp list` and `-p` come from tests/fake_claude.py and
upload/download go to a local http.server."""
import json, os, shutil, subprocess, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests.base import C, FAKE, P, PY, REPO, ProjectCase, ServerCase

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
        if self.path == "/r":                    # redirect off the allowed hosts: refused before any connection
            self.send_response(302); self.send_header("Location", "https://evil.com/x"); self.send_header("Content-Length", "0")
            return self.end_headers()
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
            with self.assertRaises(ValueError): M._get(url[:-2] + "/r", dest)
            self.assertEqual(dest.read_bytes(), _H.body)
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


def lavfi(out, src, *extra):
    subprocess.run([P._ff(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, *extra, str(out)], check=True, capture_output=True)


class TestAudioFinal(ProjectCase):
    """The export's audio step with chat_ai.adobe_voice mocked: Adobe voice, local fallback (announced), failure."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.TemporaryDirectory(); cls.media = Path(cls._media.name) / "m.mp4"
        subprocess.run([P._ff(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=180x320:rate=30:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2", "-c:v", "libx264", "-preset",
                        "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cls.media)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls): cls._media.cleanup()

    def setUp(self):
        super().setUp(); self.d = self.make_project("t1")
        for f in ("render.mp4", "cut.mp4"): shutil.copy(self.media, self.d / f)

    def run_final(self, voz, estado=None, fundo=True):
        vd, seen = self.d / "voz", {}
        def fake(name):
            seen["voice"] = (vd / "voice.wav").is_file() and P._has_audio(vd / "voice.wav")
            r = dict(estado=estado, fala=None, fundo=None, detalhe=None)
            if estado == "ok":
                lavfi(vd / "fala.wav", "sine=frequency=300:sample_rate=48000:duration=2"); r["fala"] = vd / "fala.wav"
                if fundo: lavfi(vd / "fundo.wav", "anoisesrc=d=2:a=0.05:r=48000"); r["fundo"] = vd / "fundo.wav"
            return r
        with mock.patch.object(C, "adobe_voice", side_effect=fake) as av, \
                mock.patch.object(P.subprocess, "run", wraps=subprocess.run) as spy:
            got = P._audio_final("t1", self.d, voz, [])
        mix = [c.args[0] for c in spy.call_args_list if len(c.args[0]) > 1 and str(c.args[0][1]).endswith("mix_audio.py")]
        self.assertEqual(len(mix), 1, mix)
        self.assertTrue(P._has_audio(self.d / "final.mp4"))
        if voz: av.assert_called_once_with("t1"); self.assertTrue(seen["voice"])
        else: av.assert_not_called()
        return got, mix[0]

    def test_ok(self):
        got, cmd = self.run_final("adobe", "ok")
        self.assertEqual(got, (P.TXT_ADOBE_OK, {}))
        self.assertEqual((cmd[2], Path(cmd[3]), cmd[4]), ("render.mp4", self.d / "voz" / "fala.wav", "final.mp4"))
        self.assertEqual((Path(arg(cmd, "--bg")), arg(cmd, "--bg-level")), (self.d / "voz" / "fundo.wav", "0.35"))
        self.assertNotIn("--clean", cmd); self.assertNotIn("--sfx", cmd)

    def test_local(self):
        vd = self.d / "voz"; vd.mkdir(); (vd / "enviado").write_text("1"); (vd / "fala.wav").write_bytes(b"velho")   # last try
        got, cmd = self.run_final("adobe", "indisponivel")
        self.assertEqual(got, (P.TXT_ADOBE_LOCAL, {}))
        self.assertEqual(cmd[2:5], ["render.mp4", "cut.mp4", "final.mp4"]); self.assertIn("--clean", cmd)
        self.assertEqual(sorted(p.name for p in vd.iterdir()), ["voice.wav"])     # every try starts clean

    def test_falhou(self):
        got, cmd = self.run_final("adobe", "falhou")
        self.assertEqual(got, (P.TXT_ADOBE_FALHOU, {"kind": "warn", "acao": "adobe"}))
        self.assertEqual(cmd[2:], ["render.mp4", "render.mp4", "final.mp4"])

    def test_plain(self):
        got, cmd = self.run_final(None)
        self.assertIsNone(got); self.assertEqual(cmd[2:], ["render.mp4", "render.mp4", "final.mp4"])
        self.assertFalse((self.d / "voz").exists())

    def test_sfx(self):
        lavfi(self.d / "sfx.wav", "sine=frequency=900:sample_rate=48000:duration=1")
        for estado in ("ok", "indisponivel"):
            with self.subTest(estado=estado):
                _, cmd = self.run_final("adobe", estado, fundo=False)
                self.assertEqual(arg(cmd, "--sfx"), "sfx.wav"); self.assertNotIn("--bg", cmd)


class RouteCase(ServerCase):
    def setUp(self):
        super().setUp(); self.make_project("t1")

    def export(self, body): return self.req("POST", "/api/p/t1/export", body)

    def offer(self, acao, **kw):
        P.say("t1", "Posso limpar sua voz com o Adobe Podcast.", acao=acao, **kw); return len(P.load("t1")["chat"]) - 1

    def wait_export(self):           # the export the click starts fails fast (no video), before the audio step
        self.wait_for(lambda: P.read_job("t1", "export").get("done"), 60, "a exportação não terminou")

    def started(self, spy): return [c.args[0] for c in spy.call_args_list if "app_project.py" in str(c.args[0])][0]


class TestAdobeRoute(RouteCase):
    def test_bad_voz(self):
        for voz in ("x", "", 1, True, ["adobe"]):
            with self.subTest(voz=voz): self.assertEqual(self.export({"voz": voz}), (400, {"error": "opção inválida"}))
        self.assertFalse((P.folder("t1") / "export.json").exists())

    def test_click(self):
        j = self.offer("adobe")
        with mock.patch.object(self.server.subprocess, "Popen", wraps=subprocess.Popen) as spy:
            self.assertEqual(self.export({"voz": "adobe", "msg": j}), (200, {"ok": True}))
        self.assertEqual(self.started(spy)[-4:], ["export", "t1", "--voz", "adobe"])
        self.assertEqual(P.read_job("t1", "export")["voz"], "adobe")
        self.assertIs(P.load("t1")["chat"][j]["feita"], True)
        self.assertEqual(self.export({"voz": "adobe", "msg": j})[0], 400)    # use-once
        self.wait_export()

    def test_retry_after_failure(self):
        j = self.offer("adobe", kind="warn")                                  # TXT_ADOBE_FALHOU + "Tentar de novo"
        self.assertEqual(self.export({"voz": "adobe", "msg": j}), (200, {"ok": True}))
        self.wait_export()

    def test_wrong_kind(self):
        k, j = self.offer("export"), self.offer("adobe")
        self.assertEqual(self.export({"voz": "adobe", "msg": k})[0], 400)    # a "Gerar agora" can't send audio
        self.assertEqual(self.export({"msg": j})[0], 400)                     # and "Enviar ao Adobe" always sends voz
        self.assertFalse((P.folder("t1") / "export.json").exists())

    def test_running(self):
        j = self.offer("adobe"); P.job("t1", "export", done=False)
        self.assertEqual(self.export({"voz": "adobe", "msg": j})[0], 409)
        self.assertNotIn("feita", P.load("t1")["chat"][j])

    def test_plain_no_voz(self):
        P.job("t1", "export", done=True, voz="adobe")                         # the last export used Adobe
        with mock.patch.object(self.server.subprocess, "Popen", wraps=subprocess.Popen) as spy:
            self.assertEqual(self.export({}), (200, {"ok": True}))
        self.assertNotIn("--voz", self.started(spy)); self.assertIsNone(P.read_job("t1", "export").get("voz"))
        self.wait_export()


class TestNoEgressWithoutClick(RouteCase):
    def test_offer_only(self):
        C.CLAUDE_CMD = [PY, str(FAKE), "confirmar_adobe"]
        P.say("t1", "limpa a minha voz", who="user"); C.kick("t1"); self.wait_idle("t1")
        r = [m for m in P.load("t1")["chat"] if m["who"] == "cinex"][-1]
        self.assertEqual((r["text"], r.get("acao")), ("Posso limpar sua voz com o Adobe Podcast.", "adobe"))
        self.assertFalse((P.folder("t1") / "export.json").exists())
        self.assertFalse((P.folder("t1") / "voz").exists())
        self.assertNotIn("mcp", [e["ev"] for e in self.fake_log()])
