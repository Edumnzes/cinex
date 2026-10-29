"""Project state (scripts/app_project.py): lock, atomic writes, concurrency, hard-linked versions."""
import json, os, subprocess, threading, time, unittest

from tests.base import PY, REPO, P, ProjectCase

CHILD = """
import sys; sys.path.insert(0, sys.argv[1]); import app_project as P
for _ in range(25): P.update(sys.argv[2], lambda s: s.update(contador=s.get("contador", 0) + 1))
"""


class TestUpdate(ProjectCase):
    def test_processes(self):
        self.make_project()
        ps = [subprocess.Popen([PY, "-c", CHILD, str(REPO / "scripts"), "t1"]) for _ in range(4)]
        self.assertEqual([p.wait(120) for p in ps], [0] * 4)
        st = P.load("t1")
        self.assertEqual((st["contador"], st["rev"]), (100, 100))

    def test_busy(self):
        d = self.make_project(); (d / ".cinex.lock").touch()
        old = P.LOCK_TRIES; P.LOCK_TRIES = 5
        try:
            t = time.time()
            with self.assertRaisesRegex(TimeoutError, "projeto ocupado"): P.update("t1", lambda s: None)
            self.assertLess(time.time() - t, 1)
        finally: P.LOCK_TRIES = old

    def test_stale(self):
        d = self.make_project(); lock = d / ".cinex.lock"; lock.touch()
        os.utime(lock, (time.time() - 60,) * 2)
        self.assertEqual(P.update("t1", lambda s: s.update(x=1))["x"], 1)
        self.assertFalse(lock.exists())

    def test_rev(self):
        self.make_project()
        for i in range(1, 4): self.assertEqual(P.update("t1", lambda s: None)["rev"], i)


class TestAtomic(ProjectCase):
    def test_readers(self):
        self.make_project(); P.job("t1", "export", step="x", pct=1)
        errors = []

        def run(fn, n):
            try:
                for _ in range(n): fn()
            except Exception as e: errors.append(repr(e))

        ts = [threading.Thread(target=run, args=(lambda: P.update("t1", lambda s: s.update(x=s.get("x", 0) + 1)), 200))]
        ts += [threading.Thread(target=run, args=(lambda: P.load("t1"), 300)) for _ in range(2)]
        ts += [threading.Thread(target=run, args=(lambda: P.read_job("t1", "export"), 300))]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(P.load("t1")["x"], 200)


class TestHardLink(ProjectCase):
    def test_words(self):
        d1 = self.make_project("t1"); d2 = P.folder("t2"); d2.mkdir()
        old = (d1 / "words_raw.json").read_text(encoding="utf-8")
        os.link(d1 / "words_raw.json", d2 / "words_raw.json")
        P._write_json(d1 / "words_raw.json", [dict(w="novo", s=0, e=1)])
        self.assertEqual((d2 / "words_raw.json").read_text(encoding="utf-8"), old)
        self.assertEqual(json.loads((d1 / "words_raw.json").read_text(encoding="utf-8"))[0]["w"], "novo")

    def test_state(self):
        d1 = self.make_project("t1"); d2 = P.folder("t2"); d2.mkdir()
        os.link(d1 / "cinex.json", d2 / "cinex.json")
        P.update("t1", lambda s: s.update(x=1))
        self.assertNotIn("x", json.loads((d2 / "cinex.json").read_text(encoding="utf-8")))


class TestClaim(ProjectCase):
    """CHAT-05: the worker ("auto") and the open session ("sessao") take messages through the same claim: each exactly once."""

    def test_default(self):
        self.assertEqual(P.chat_mode(), "auto")
        with self.assertRaises(ValueError): P.set_chat_mode("x")
        P.set_chat_mode("sessao"); self.assertEqual(P.chat_mode(), "sessao")

    def test_race(self):
        self.make_project()
        P.update("t1", lambda s: s["chat"].extend(dict(who="user", text=f"m{i}", t="", seen=False) for i in range(30)))
        got, errors, done = [], [], threading.Event()

        def take(mode, limit):
            try:
                while not done.is_set():
                    got.extend((i, mode) for i, _ in P.claim("t1", mode, limit))
                    if all(m["seen"] for m in P.load("t1")["chat"]): done.set()
            except Exception as e: errors.append(repr(e)); done.set()

        def toggle():
            k = 0
            while not done.is_set(): P.set_chat_mode(("auto", "sessao")[k % 2]); k += 1; time.sleep(.01)

        ts = [threading.Thread(target=take, args=("auto", 1)) for _ in range(3)]
        ts += [threading.Thread(target=take, args=("sessao", None)) for _ in range(2)] + [threading.Thread(target=toggle)]
        for t in ts: t.start()
        for t in ts: t.join(60)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(i for i, _ in got), list(range(30)))   # every message once, none twice
        c = P.load("t1")["chat"]
        for i, mode in got: self.assertEqual(c[i]["by"], mode)

    def test_wait_subprocess(self):
        self.make_project(); P.set_chat_mode("sessao"); P.say("t1", "corta o fim", who="user")
        r = subprocess.run([PY, str(REPO / "scripts" / "app_project.py"), "wait", "t1", "--timeout", "5"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(r.stdout.count("corta o fim"), 1, r.stdout + r.stderr)
        m = P.load("t1")["chat"][0]
        self.assertEqual((m["seen"], m["by"]), (True, "sessao"))
        self.assertEqual(P.claim("t1", "auto"), [])


if __name__ == "__main__":
    unittest.main()
