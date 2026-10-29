"""scripts/chat_ai.py: the locked-down `claude -p` command, clean env, model choice and the auto worker (CHAT-01/02, D-05).
Every worker run uses tests/fake_claude.py (C.CLAUDE_CMD): the real CLI is never called."""
import json, os, subprocess, time, unittest
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


WAIT = [PY, str(REPO / "scripts" / "app_project.py"), "wait"]


class TestMode(FailCase):
    """CHAT-05 / D-14: Automático or Sessão aberta, global (A-02), and never an answer twice."""

    def modo(self, m): return self.ia({"acao": "modo", "modo": m})

    def test_sessao_no_worker(self):
        self.assertEqual(self.modo("sessao"), (200, {"ok": True, "modo": "sessao"}))
        self.assertEqual(self.req("POST", "/api/p/t1/chat", {"text": "oi"})[0], 200)
        time.sleep(1)
        self.assertEqual(self.starts(), []); self.assertNotIn("t1", C._CHAT)
        self.assertEqual(self.req("GET", "/api/p/t1/poll")[1]["modo"], "sessao")
        self.assertNotIn("t1", C._CHAT)                         # the poll doesn't start it either

    def test_back_to_auto(self):
        self.modo("sessao"); self.req("POST", "/api/p/t1/chat", {"text": "oi"})
        self.assertEqual(self.modo("auto"), (200, {"ok": True, "modo": "auto"}))
        self.wait_for(lambda: self.cinex()); self.wait_idle("t1")
        self.assertEqual([m["text"] for m in self.cinex()], ["Pronto."])
        self.assertEqual(len(self.starts()), 1)

    def test_no_double(self):
        self.modo("sessao")
        for t in ("a", "b"): self.req("POST", "/api/p/t1/chat", {"text": t})
        r = subprocess.run(WAIT + ["t1", "--timeout", "5"], capture_output=True, text=True, encoding="utf-8",
                           timeout=30, stdin=subprocess.DEVNULL)
        self.assertIn(": a", r.stdout); self.assertIn(": b", r.stdout)
        self.modo("auto"); self.req("GET", "/api/p/t1/poll"); time.sleep(.5)
        self.assertEqual(self.starts(), []); self.assertEqual(self.cinex(), [])
        self.assertEqual([m["by"] for m in P.load("t1")["chat"]], ["sessao", "sessao"])

    def test_invalid(self):
        self.assertEqual(self.modo("x")[0], 400)
        self.assertEqual(self.ia({"acao": "modo"})[0], 400)
        self.assertEqual(P.chat_mode(), "auto")


class TestQueue(FailCase):
    """CHAT-04: in order, one at a time per project; projects don't block each other; manual edits stay (D-10)."""

    def spans(self):
        """pid -> [project, start t, end t] from the fake's log."""
        out = {}
        for e in self.fake_log():
            if e["ev"] == "start": out[e["pid"]] = [Path(e["cwd"]).name, e["t"], None]
            elif e["ev"] == "end" and e["pid"] in out: out[e["pid"]][2] = e["t"]
        return sorted(out.values(), key=lambda x: x[1])

    def test_order(self):
        self.use("pausa")
        for t in ("A", "B", "C"): self.assertEqual(self.req("POST", "/api/p/t1/chat", {"text": t})[0], 200)
        self.wait_for(lambda: len(self.cinex()) == 3, 20); self.wait_idle("t1")
        self.assertEqual([m["text"] for m in self.cinex()], ["ok: A", "ok: B", "ok: C"])
        sp = self.spans(); self.assertEqual(len(sp), 3)
        for a, b in zip(sp, sp[1:]): self.assertGreaterEqual(b[1], a[2])   # never two at once

    def test_two_projects(self):
        self.use("pausa"); self.make_project("t2")
        with mock.patch.dict(os.environ, {"FAKE_SLEEP": "2"}):
            for n in ("t1", "t2"): self.req("POST", f"/api/p/{n}/chat", {"text": "oi"})
            self.wait_for(lambda: self.cinex("t1") and self.cinex("t2"), 20); self.wait_idle("t1"); self.wait_idle("t2")
        (_, s1, e1), (_, s2, e2) = self.spans()
        self.assertLess(max(s1, s2), min(e1, e2))                # the two ran at the same time

    def test_manual_edit_preserved(self):
        self.use("edita_lento")
        self.req("POST", "/api/p/t1/chat", {"text": "aumenta a legenda"})
        self.wait_for(self.starts)
        self.assertEqual(self.req("PUT", "/api/p/t1/state", {"color": {"correct": True, "look": "moody"}})[0], 200)
        self.wait_for(lambda: self.cinex(), 10); self.wait_idle("t1")
        st = P.load("t1")
        self.assertEqual((st["captions"]["size"], st["color"]["look"]), (P.CAPTIONS["size"] + 10, "moody"))


class TestRecover(FailCase):
    def test_restart(self):
        def fn(s):
            s["chat"] += [dict(who="user", text="velha", t="", seen=True, by="auto"), dict(who="cinex", text="Feito.", t="", seen=True),
                          dict(who="user", text="da sessão", t="", seen=True, by="sessao"),
                          dict(who="user", text="presa", t="", seen=True, by="auto")]
        P.update("t1", fn); P.job("t1", "chat", busy=True, step="Lendo o projeto…")
        C.recover()
        self.wait_for(lambda: len(self.cinex()) == 2); self.wait_idle("t1")
        c = P.load("t1")["chat"]
        self.assertEqual(c[-1]["text"], "Pronto.")
        self.assertEqual([e["stdin"].rsplit("\n", 1)[-1] for e in self.starts()], ["presa"])
        self.assertEqual((c[0]["by"], c[2]["by"], c[3]["by"]), ("auto", "sessao", "auto"))
        self.assertIs(self.job()["busy"], False)


class TestEnsure(FailCase):
    def test_poll_restarts(self):
        P.say("t1", "oi", who="user")                           # no kick: as if the worker had vanished
        self.req("GET", "/api/p/t1/poll")
        self.wait_for(lambda: self.cinex()); self.wait_idle("t1")
        self.assertEqual(self.cinex()[0]["text"], "Pronto.")

    def test_setup_waits(self):
        P.say("t1", "oi", who="user"); P.job("t1", "chat", erro="nao_logado")
        self.req("GET", "/api/p/t1/poll"); time.sleep(.3)
        self.assertNotIn("t1", C._CHAT); self.assertEqual(self.starts(), [])


class TestConfirm(FailCase):
    """D-01: "gera o vídeo" -> a "Gerar agora" button in the answer; the export only starts on the click, once.
    The export the click starts is a real `app_project.py export` on the fake project: it fails fast (no video)."""

    def ask(self, scen):
        self.use(scen); P.say("t1", "gera o vídeo", who="user"); C.kick("t1"); self.wait_idle("t1")
        return self.cinex()[-1]

    def export(self, body): return self.req("POST", "/api/p/t1/export", body)

    def offer(self):
        P.say("t1", "Está tudo pronto. É só tocar em Gerar agora.", acao="export"); return len(P.load("t1")["chat"]) - 1

    def wait_export(self):           # the export process must be done before tearDown removes the folder
        self.wait_for(lambda: P.read_job("t1", "export").get("done"), 60, "a exportação não terminou")

    def test_reply_has_action(self):
        r = self.ask("confirmar_exportar")
        self.assertEqual((r["text"], r.get("acao")), ("Está tudo pronto. É só tocar em Gerar agora.", "export"))
        self.assertFalse((P.folder("t1") / "export.json").exists())

    def test_unknown_action_ignored(self):
        r = self.ask("confirmar_estranho")
        self.assertEqual(r["text"], "Está tudo pronto. É só tocar em Gerar agora."); self.assertNotIn("acao", r)

    def test_click(self):
        j = self.offer()
        self.assertEqual(self.export({"msg": j}), (200, {"ok": True}))
        self.assertTrue((P.folder("t1") / "export.json").exists())
        self.assertIs(P.load("t1")["chat"][j]["feita"], True)
        self.assertEqual(self.export({"msg": j}), (400, {"error": "mensagem inválida"}))
        self.wait_export()

    def test_running(self):
        j = self.offer(); P.job("t1", "export", done=False)
        self.assertEqual(self.export({"msg": j})[0], 409)
        self.assertNotIn("feita", P.load("t1")["chat"][j])

    def test_bad_msg(self):
        P.say("t1", "gera o vídeo", who="user"); self.offer()          # no kick: nobody answers it
        P.say("t1", C.TXT_FALHA, kind="warn", acao="tentar", ref=0)
        for msg in (0, 2, 3, -1, "1", "x", True, 1.0):
            with self.subTest(msg=msg): self.assertEqual(self.export({"msg": msg})[0], 400)
        self.assertEqual(self.export([1])[0], 400)
        self.assertFalse((P.folder("t1") / "export.json").exists())

    def test_plain_export(self):
        self.assertEqual(self.export({}), (200, {"ok": True}))      # the Publicar page's button, as before
        self.wait_export()
