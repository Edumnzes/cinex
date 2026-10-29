"""scripts/chat_ai.py: the locked-down `claude -p` command, clean env, model choice and the auto worker (CHAT-01/02, D-05).
Every worker run uses tests/fake_claude.py (C.CLAUDE_CMD): the real CLI is never called."""
import json, os, time, unittest
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
