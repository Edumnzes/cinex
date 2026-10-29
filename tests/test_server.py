"""app/server.py security: Host/Origin/X-Cinex guards, names and paths, PUT /state limited to EDITABLE."""
import unittest

from tests.base import P, ServerCase


class TestGuards(ServerCase):
    def setUp(self):
        super().setUp(); self.make_project()

    def test_host(self):
        port = self.srv.server_address[1]
        self.assertEqual(self.req("GET", "/api/projects", headers={"Host": "evil.com"})[0], 403)
        self.assertEqual(self.req("GET", "/api/projects", headers={"Host": f"localhost:{port}"})[0], 200)

    def test_writes(self):
        chat = lambda **h: self.req("POST", "/api/p/t1/chat", {"text": "oi"}, headers=h)[0]
        self.assertEqual(chat(Origin="http://evil.com"), 403)
        self.assertEqual(chat(Origin="null"), 403)
        self.assertEqual(chat(**{"X-Cinex": None}), 403)
        self.assertEqual(chat(**{"X-Cinex": "0"}), 403)
        self.assertEqual(chat(), 200)
        self.assertEqual(P.load("t1")["chat"][-1]["text"], "oi")


class TestNames(ServerCase):
    def test_paths(self):
        self.make_project()
        for path, code in [("/api/p/..%2Fx/poll", 400), ("/api/p/a%2Fb", 400), ("/api/p/" + "a" * 65, 400),
                           ("/static/..%2fserver.py", 404), ("/api/estilos/x/../y", 404),
                           ("/api/font/x?p=../y", 400), ("/api/p/naoexiste", 404)]:
            with self.subTest(path=path): self.assertEqual(self.req("GET", path)[0], code)


class TestState(ServerCase):
    def setUp(self):
        super().setUp(); self.make_project()

    def put(self, body): return self.req("PUT", "/api/p/t1/state", body)

    def test_editable(self):
        code, r = self.put({"name": "outro", "chat": [{"who": "user", "text": "x"}], "captions": dict(P.CAPTIONS, size=70)})
        self.assertEqual(code, 200); self.assertEqual(r["rev"], 1)
        st = P.load("t1")
        self.assertEqual((st["name"], st["chat"], st["captions"]["size"]), ("t1", [], 70))

    def test_invalid(self):
        segs = [dict(g, keep="sim") for g in P.load("t1")["segments"]]
        for body, msg in [({"segments": segs}, "segmento inválido"), ({"format": "x"}, "formato inválido"),
                          ({"motions": [{"type": "nada", "t0": 0, "t1": 1}]}, "motion inválido"),
                          ({"order": ["a"]}, "ordem inválida")]:
            with self.subTest(msg=msg): self.assertEqual(self.put(body), (400, {"error": msg}))
        self.assertEqual(P.load("t1")["rev"], 0)


class TestValidate(unittest.TestCase):
    def test_filter(self):
        self.assertEqual(P.validate_patch({"rev": 9, "captions": {}}), {"captions": {}})

    def test_invalid(self):
        with self.assertRaises(ValueError): P.validate_patch({"camera": []})


if __name__ == "__main__":
    unittest.main()
