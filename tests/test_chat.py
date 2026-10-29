"""scripts/chat_ai.py: the locked-down `claude -p` command, clean env, model choice and the auto worker (CHAT-01/02, D-05).
Every worker run uses tests/fake_claude.py (C.CLAUDE_CMD): the real CLI is never called."""
import json, os, time, unittest
from pathlib import Path
from unittest import mock

from tests.base import C, FAKE, P, PY, REPO, ProjectCase, ServerCase


def arg(cmd, flag): return cmd[cmd.index(flag) + 1]


class TestCommand(ProjectCase):
    def test_locked_down(self):
        cmd = C.command(["claude.exe"], "t1", "haiku")
        self.assertEqual(cmd[:2], ["claude.exe", "-p"])
        for flag, val in [("--output-format", "stream-json"), ("--max-turns", "25"), ("--tools", ""),
                          ("--setting-sources", ""), ("--permission-mode", "dontAsk"), ("--allowedTools", "mcp__cinex"),
                          ("--system-prompt-file", str(C.PROMPT_FILE)), ("--fallback-model", "sonnet"), ("--model", "haiku")]:
            with self.subTest(flag=flag): self.assertEqual(arg(cmd, flag), val)
        for flag in ("--verbose", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
            self.assertIn(flag, cmd)
        for bad in ("Bash", "dangerously", "bypassPermissions"):
            self.assertFalse([a for a in cmd if bad in a], bad)
        srv = json.loads(arg(cmd, "--mcp-config"))["mcpServers"]["cinex"]
        self.assertEqual(srv["args"], [str(REPO / "scripts" / "cinex_mcp.py"), "t1"])
        self.assertTrue(C.PROMPT_FILE.is_file())

    def test_sonnet_no_fallback(self):
        self.assertNotIn("--fallback-model", C.command(["claude.exe"], "t1", "sonnet"))

    def test_prompt(self):
        self.make_project()
        P.say("t1", "oi", who="user"); P.say("t1", "Olá!")
        P.say("t1", "/model opus", who="user", passo="estilo")
        st = P.load("t1"); i = len(st["chat"]) - 1
        p = C.build_prompt("t1", i, st["chat"][i])
        self.assertTrue(p.startswith("Projeto: t1. Página: estilo."))
        self.assertIn(P.show_text("t1"), p)
        self.assertIn("Você: oi", p); self.assertIn("Cinex: Olá!", p)
        self.assertTrue(p.rstrip().endswith("/model opus"))


class TestEnv(unittest.TestCase):
    def test_clean(self):
        leak = {"CLAUDECODE": "1", "CLAUDE_CODE_SIMPLE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli",
                "CLAUDE_AGENT_SDK_X": "1", "ANTHROPIC_BASE_URL": "http://127.0.0.1:9"}
        with mock.patch.dict(os.environ, leak):
            env = C.child_env()
        for k in leak: self.assertNotIn(k, env)
        self.assertEqual(env["CLAUDE_CODE_MAX_RETRIES"], "2")


class TestModel(unittest.TestCase):
    def test_pick(self):
        self.assertEqual(C.pick_model("deixa a legenda maior", "estilo"), "haiku")
        self.assertEqual(C.pick_model("reescreve o gancho", "corte"), "opus")
        self.assertEqual(C.pick_model("corta o trecho 3", "revisao"), "opus")


class TestAuto(ServerCase):
    def setUp(self):
        super().setUp(); self.make_project()

    def test_reply(self):
        C.CLAUDE_CMD = [PY, str(FAKE), "edita"]
        code, _ = self.req("POST", "/api/p/t1/chat", {"text": "deixa a legenda maior", "passo": "estilo"})
        self.assertEqual(code, 200)
        last = self.wait_for(lambda: (lambda m: m if m["who"] == "cinex" else None)(P.load("t1")["chat"][-1]))
        self.assertEqual(last["text"], "Deixei a legenda maior.")
        self.wait_idle("t1")
        st = P.load("t1")
        self.assertEqual(st["captions"]["size"], 72); self.assertGreaterEqual(st["rev"], 3)   # say, claim, edit, reply
        user = [m for m in st["chat"] if m["who"] == "user"]
        self.assertEqual([(m["seen"], m["by"]) for m in user], [(True, "auto")])
        start = [e for e in self.fake_log() if e["ev"] == "start"]
        self.assertEqual(len(start), 1)
        self.assertIn("deixa a legenda maior", start[0]["stdin"])
        self.assertTrue(start[0]["stdin"].startswith("Projeto: t1."))
        self.assertFalse([a for a in start[0]["argv"] if "legenda maior" in a])
        self.assertTrue(os.path.samefile(start[0]["cwd"], P.folder("t1")))

    def test_one_worker(self):
        C.CLAUDE_CMD = [PY, str(FAKE), "lento"]
        P.say("t1", "oi", who="user")
        C.kick("t1"); C.kick("t1")
        self.wait_for(lambda: [e for e in self.fake_log() if e["ev"] == "start"])
        time.sleep(.5)
        self.assertEqual(len([e for e in self.fake_log() if e["ev"] == "start"]), 1)
        self.assertIn("t1", C._CHAT)
        C._CHAT["t1"]["proc"].kill()
        self.wait_idle("t1")
        self.assertEqual(P.load("t1")["chat"][-1]["text"], C.TXT_FALHA)


class TestStatus(ServerCase):
    def setUp(self):
        super().setUp(); self.make_project()

    def test_labels(self):
        for (tool, a), want in [(("cortar_ou_manter", {"trecho": "12", "manter": False}), "Cortando o trecho 12…"),
                                (("cortar_ou_manter", {"trecho": "12", "manter": True}), "Devolvendo o trecho 12…"),
                                (("ajustar", {"campo": "captions"}), "Ajustando a legenda…"),
                                (("ajustar", {"campo": "broll"}), "Colocando a imagem de apoio…"),
                                (("camera_lenta", {"trecho": 4}), "Deixando o trecho 4 em câmera lenta…"),
                                (("versao_curta", {"segundos": 15}), "Montando a versão de 15 segundos…"),
                                (("ver_projeto", {}), "Lendo o projeto…"), (("revisar", {}), "Olhando o vídeo e as legendas…"),
                                (("corrigir_texto", {}), "Corrigindo o texto da legenda…"),
                                (("ressincronizar", {}), "Acertando o tempo das legendas…"), (("xyz", {}), "Trabalhando no seu pedido…")]:
            with self.subTest(tool=tool, a=a): self.assertEqual(C.label(tool, a), want)

    def test_stream(self):
        C.CLAUDE_CMD = [PY, str(FAKE), "ferramentas"]
        P.say("t1", "corta o trecho 12 e aumenta a legenda", who="user"); C.kick("t1")
        steps, desde = set(), []
        def done():
            j = P.read_job("t1", "chat"); steps.add(j.get("step")); desde.append(j.get("desde"))
            return "t1" not in C._CHAT
        self.wait_for(done, 15)
        self.assertLessEqual({"Cortando o trecho 12…", "Ajustando a legenda…"}, steps)
        self.assertTrue([d for d in desde if d])
        self.assertIs(P.read_job("t1", "chat")["busy"], False)
        self.assertEqual(P.load("t1")["chat"][-1]["text"], "Cortei o trecho 12 e aumentei a legenda.")

    def test_unknown_event(self):
        P.job("t1", "chat", step="Lendo o projeto…")
        S = {"pedido": "haiku", "step": "Lendo o projeto…", "modelo": None, "result": None}
        C.on_event("t1", {"type": "coisa_nova"}, S)
        self.assertEqual(P.read_job("t1", "chat")["step"], "Lendo o projeto…")
        self.assertEqual(S["step"], "Lendo o projeto…")

    def test_reserva(self):
        C.CLAUDE_CMD = [PY, str(FAKE), "reserva"]
        P.say("t1", "reescreve o gancho", who="user"); C.kick("t1"); self.wait_idle("t1")
        j = P.read_job("t1", "chat")
        self.assertIn("sonnet", j["modelo"]); self.assertIs(j["reserva"], True)
        C.CLAUDE_CMD = [PY, str(FAKE), "ok"]
        P.say("t1", "deixa a legenda maior", who="user"); C.kick("t1"); self.wait_idle("t1")
        j = P.read_job("t1", "chat")
        self.assertIn("haiku", j["modelo"]); self.assertIs(j["reserva"], False)


class TestStop(ServerCase):
    def test_stop(self):
        self.make_project()
        C.CLAUDE_CMD = [PY, str(FAKE), "lento"]
        n0 = C.uso()
        P.say("t1", "oi", who="user"); C.kick("t1")
        self.wait_for(lambda: [e for e in self.fake_log() if e["ev"] == "start"])
        self.wait_for(lambda: (C._CHAT.get("t1") or {}).get("proc"))
        proc = C._CHAT["t1"]["proc"]
        self.assertEqual(self.req("POST", "/api/p/t1/ia", {"acao": "parar"}), (200, {"ok": True}))
        self.wait_for(lambda: "t1" not in C._CHAT or proc.poll() is not None, 5, "a IA não parou em 5 s")
        self.wait_idle("t1")
        self.assertEqual(P.load("t1")["chat"][-1]["text"], C.TXT_PARADO)
        self.assertIs(P.read_job("t1", "chat")["busy"], False)
        self.assertEqual(C.uso(), n0)


class TestUso(ServerCase):
    def test_count(self):
        self.make_project()
        self.assertEqual(C.uso(), 0)
        P.say("t1", "oi", who="user"); P.say("t1", "e aí", who="user"); C.kick("t1"); self.wait_idle("t1")
        self.assertEqual(C.uso(), 2)
        self.assertEqual(self.req("GET", "/api/p/t1/poll")[1]["uso"], 2)

    def test_new_day(self):
        P._write_json(P.ROOT / "_chat_uso.json", {"dia": "2000-01-01", "n": 5})
        self.assertEqual(C.uso(), 0)


class FailCase(ServerCase):
    """Failure paths (D-06, D-12, D-13, A-05..A-07). rede_ok() is patched whenever it can run: no test touches the network."""

    def setUp(self):
        super().setUp(); self.make_project()

    def use(self, scen): C.CLAUDE_CMD = [PY, str(FAKE), scen]

    def starts(self, name=None):
        return [e for e in self.fake_log() if e["ev"] == "start" and (name is None or Path(e["cwd"]).name == name)]

    def cinex(self, name="t1"): return [m for m in P.load(name)["chat"] if m["who"] == "cinex"]

    def job(self, name="t1"): return P.read_job(name, "chat")

    def ia(self, body, name="t1"): return self.req("POST", f"/api/p/{name}/ia", body)


class TestErrors(FailCase):
    def test_missing(self):
        C.CLAUDE_CMD = None
        with mock.patch.object(C, "claude_exe", return_value=None):
            self.assertEqual(self.req("POST", "/api/p/t1/chat", {"text": "oi"})[0], 200)
            self.wait_idle("t1")
            self.assertEqual([(m.get("kind"), m.get("reason")) for m in self.cinex()], [("setup", "missing")])
            self.assertEqual(self.cinex()[0]["text"], C.TXT_SETUP["missing"])
            self.assertIs(P.load("t1")["chat"][0]["seen"], False)
            self.assertEqual(self.job()["erro"], "nao_instalado")
            self.assertEqual(self.req("POST", "/api/p/t1/chat", {"text": "e aí"})[0], 200)
            self.wait_idle("t1")
            self.assertEqual(len(self.cinex()), 1)               # A-05: no second card
            self.assertEqual(self.job()["erro"], "nao_instalado")

    def login_card(self):
        self.use("nao_logado")
        P.say("t1", "oi", who="user"); C.kick("t1"); self.wait_idle("t1")
        self.assertEqual([(m.get("kind"), m.get("reason")) for m in self.cinex()], [("setup", "login")])
        self.assertEqual(self.job()["erro"], "nao_logado")
        self.assertIs(P.load("t1")["chat"][0]["seen"], False)

    def test_login(self):
        self.login_card()

    def test_testar(self):
        self.login_card(); self.use("ok")
        with mock.patch.dict(os.environ, {"FAKE_AUTH": '{"loggedIn": true}'}), mock.patch.object(C, "rede_ok", return_value=True):
            code, r = self.ia({"acao": "testar"})
            self.assertEqual((code, r), (200, {"instalado": True, "logado": True, "rede": True, "ok": True}))
            self.wait_for(lambda: len(self.cinex()) == 2); self.wait_idle("t1")
        self.assertEqual([m["text"] for m in self.cinex()], [C.TXT_SETUP["login"], "Pronto."])   # A-06: one answer
        auth = [e for e in self.fake_log() if e["ev"] == "auth"]
        self.assertTrue(auth); self.assertNotIn("-p", auth[0]["argv"])
        self.assertIsNone(self.job()["erro"])

    def test_testar_fail(self):
        self.login_card(); n = len(self.starts())
        with mock.patch.dict(os.environ, {"FAKE_AUTH": '{"loggedIn": false}'}), mock.patch.object(C, "rede_ok", return_value=True):
            code, r = self.ia({"acao": "testar"})
        self.assertEqual(code, 200); self.assertIs(r["ok"], False); self.assertIs(r["logado"], False)
        time.sleep(.3)
        self.assertEqual(len(self.starts()), n)

    def test_testar_offline(self):
        """Logged in but no network: not ok, yet the message goes back to the worker (the network pause resends it)."""
        self.login_card(); self.use("ok")
        with mock.patch.dict(os.environ, {"FAKE_AUTH": '{"loggedIn": true}'}), mock.patch.object(C, "rede_ok", return_value=False):
            code, r = self.ia({"acao": "testar"})
            self.assertEqual((code, r["ok"], r["rede"]), (200, False, False))
            self.wait_for(lambda: len(self.cinex()) == 2); self.wait_idle("t1")


class TestLimit(FailCase):
    def test_offline(self):
        C.NET_RETRY = .3; self.use("offline")
        with mock.patch.object(C, "rede_ok", return_value=False):
            P.say("t1", "oi", who="user"); C.kick("t1")
            self.wait_for(lambda: self.job().get("erro") == "sem_rede", 5, "sem_rede não chegou em 5 s")
            self.assertEqual(self.job()["k"], 1)
            proc = C._CHAT["t1"]["proc"]
            self.wait_for(lambda: proc.poll() is not None, 3, "o fake offline continuou vivo")
            self.use("ok")
        with mock.patch.object(C, "rede_ok", return_value=True):
            self.wait_for(lambda: self.cinex(), 5); self.wait_idle("t1")
        self.assertEqual(self.cinex()[0]["text"], "Pronto.")
        self.assertIsNone(self.job()["erro"])

    def test_limite(self):
        self.use("limite")
        with mock.patch.dict(os.environ, {"FAKE_RESET": "2"}):
            P.say("t1", "oi", who="user"); C.kick("t1")
            self.wait_for(lambda: self.job().get("erro") == "limite", 5)
            self.assertRegex(self.job()["ate"], r"^\d\d:\d\d$")
            fim = C._PAUSA["ate"]; self.use("ok")
            self.make_project("t2"); P.say("t2", "oi", who="user"); C.kick("t2")
            self.wait_for(lambda: self.cinex("t1") and self.cinex("t2"), 10); self.wait_idle("t1"); self.wait_idle("t2")
        t2 = self.starts("t2")
        self.assertEqual(len(t2), 1); self.assertGreaterEqual(t2[0]["t"], fim - .05)   # no call during the pause
        self.assertEqual((self.cinex("t1")[0]["text"], self.cinex("t2")[0]["text"]), ("Pronto.", "Pronto."))

    def test_backoff(self):
        C.LIMIT_RETRY = .2; self.use("limite"); esperas, real = [], C._pausar
        def spy(erro, ate=None):
            real(erro, ate); esperas.append((C._PAUSA["n"], C._PAUSA["ate"] - time.time()))
        with mock.patch.dict(os.environ, {"FAKE_RESET": "0"}), mock.patch.object(C, "_pausar", spy):
            P.say("t1", "oi", who="user"); C.kick("t1")
            self.wait_for(lambda: self.job().get("erro") == "limite", 5)
            self.assertIsNone(self.job()["ate"])                 # reset time unknown
            self.wait_for(lambda: len(esperas) >= 2, 5); self.use("ok")
            self.wait_for(lambda: self.cinex(), 5); self.wait_idle("t1")
        self.assertEqual([n for n, _ in esperas[:2]], [1, 2])
        self.assertAlmostEqual(esperas[1][1], 2 * esperas[0][1], delta=.08)
        C._PAUSA["n"] = 20; C._pausar("limite")
        self.assertLessEqual(C._PAUSA["ate"] - time.time(), C.LIMIT_MAX)
        C._PAUSA.update(erro=None, n=0)


class TestCancel(FailCase):
    def test_all(self):
        C.LIMIT_RETRY = 30; self.use("limite")
        with mock.patch.dict(os.environ, {"FAKE_RESET": "0"}):
            P.say("t1", "oi", who="user"); C.kick("t1")
            self.wait_for(lambda: self.job().get("erro") == "limite", 5)
            P.say("t1", "e aí", who="user")
            self.assertEqual(self.ia({"acao": "cancelar"}), (200, {"ok": True, "n": 2}))
            self.wait_idle("t1")
        user = [m for m in P.load("t1")["chat"] if m["who"] == "user"]
        self.assertEqual([(m.get("cancelada"), m["seen"]) for m in user], [(True, True), (True, True)])
        self.assertEqual(len(self.starts()), 1)
        self.assertIsNone(self.job()["erro"])

    def test_one(self):
        P.say("t1", "a", who="user"); P.say("t1", "b", who="user")
        self.assertEqual(self.ia({"acao": "cancelar", "msgs": [0]}), (200, {"ok": True, "n": 1}))
        c = P.load("t1")["chat"]
        self.assertIs(c[0].get("cancelada"), True); self.assertIsNone(c[1].get("cancelada")); self.assertIs(c[1]["seen"], False)
        self.assertEqual(self.ia({"acao": "cancelar", "msgs": ["x"]})[0], 400)
        self.assertEqual(self.ia({"acao": "cancelar", "msgs": 1})[0], 400)


class TestRetry(FailCase):
    def test_falha(self):
        self.use("falha")
        P.say("t1", "corta o trecho 2", who="user"); C.kick("t1"); self.wait_idle("t1")
        w = self.cinex()[-1]
        self.assertEqual((w["text"], w.get("kind"), w.get("acao"), w.get("ref")), (C.TXT_FALHA, "warn", "tentar", 0))
        j = len(P.load("t1")["chat"]) - 1
        self.use("ok")
        self.assertEqual(self.ia({"acao": "tentar", "msg": j}), (200, {"ok": True}))
        self.wait_for(lambda: len(self.cinex()) == 2); self.wait_idle("t1")
        st = self.starts()
        self.assertEqual(len(st), 2)
        for e in st: self.assertTrue(e["stdin"].endswith("Pedido do usuário:\ncorta o trecho 2"))   # the same request
        c = P.load("t1")["chat"]
        self.assertEqual(len([m for m in c if m["who"] == "user"]), 1)   # A-07: no new user bubble
        self.assertIs(c[j]["feita"], True); self.assertEqual(c[-1]["text"], "Pronto.")
        self.assertEqual(self.ia({"acao": "tentar", "msg": j})[0], 400)
        self.assertEqual(self.ia({"acao": "tentar", "msg": 0})[0], 400)
        self.assertEqual(self.ia({"acao": "tentar", "msg": "0"})[0], 400)


class TestTimeout(FailCase):
    def test_timeout(self):
        C.TIMEOUT = 1; self.use("lento")
        P.say("t1", "oi", who="user"); C.kick("t1")
        proc = self.wait_for(lambda: (C._CHAT.get("t1") or {}).get("proc"))
        self.wait_for(lambda: self.cinex(), 5, "o tempo esgotado não chegou em 5 s"); self.wait_idle("t1")
        w = self.cinex()[0]
        self.assertEqual((w["text"], w.get("acao"), w.get("ref")), (C.TXT_TEMPO, "tentar", 0))
        self.assertIsNotNone(proc.poll())


class TestModelFallback(FailCase):
    def test_opus_to_sonnet(self):
        self.use("modelo")
        P.say("t1", "reescreve o gancho", who="user"); C.kick("t1"); self.wait_idle("t1")
        st = self.starts()
        self.assertEqual([arg(e["argv"], "--model") for e in st], ["opus", "sonnet"])
        self.assertEqual(self.cinex()[-1]["text"], "Pronto.")
        self.assertIs(self.job()["reserva"], True); self.assertIn("opus", C.MODEL_BLOCK)
        P.say("t1", "escreve uma ideia de roteiro", who="user"); C.kick("t1"); self.wait_idle("t1")
        self.assertEqual(arg(self.starts()[-1]["argv"], "--model"), "sonnet")
