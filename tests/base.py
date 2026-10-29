"""Shared test helpers: a temporary projects root (P.ROOT + CINEX_ROOT) and a server on port 0.

Run from the repository root:  ~/reelsenv/Scripts/python -m unittest discover -s tests -t . -v
"""
import http.client, json, os, sys, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "app")]
import app_project as P  # noqa: E402


class ProjectCase(unittest.TestCase):
    """Each test gets its own empty ~/reels (subprocesses inherit it through CINEX_ROOT)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._root, self._env = P.ROOT, os.environ.get("CINEX_ROOT")
        P.ROOT = Path(self._tmp.name); os.environ["CINEX_ROOT"] = self._tmp.name

    def tearDown(self):
        P.ROOT = self._root
        if self._env is None: os.environ.pop("CINEX_ROOT", None)
        else: os.environ["CINEX_ROOT"] = self._env
        self._tmp.cleanup()

    def make_project(self, name="t1", **extra):
        """Minimal cinex.json + words_raw.json, no video."""
        d = P.folder(name); d.mkdir(parents=True, exist_ok=True)
        segs = [dict(id=i, s=i * 3.0, e=i * 3.0 + 3, keep=True, reason="", text=f"frase {i}") for i in range(3)]
        st = dict(version=1, rev=0, name=name, src="x.mp4", duration=10, segments=segs, captions=dict(P.CAPTIONS),
                  camera=dict(P.CAMERA), color=dict(P.COLOR), motions=[], sfx=[], format="vertical", keywords=[], fix={},
                  chat=[], cut_locked=False, **extra)
        P._write_json(d / "cinex.json", st)
        P._write_json(d / "words_raw.json", [dict(w=f"palavra{i}", s=i * 3.0 + .5, e=i * 3.0 + 1) for i in range(3)])
        return d


class ServerCase(ProjectCase):
    """ProjectCase + app/server.py listening on 127.0.0.1:<free port> (never the user's 8765)."""

    def setUp(self):
        super().setUp()
        import server
        self.server = server
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        self._port = server.PORT; server.PORT = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.server.PORT = self._port
        super().tearDown()

    def req(self, method, path, body=None, headers=None):
        """-> (status, json or None). Default headers are those of the app; a header set to None is removed."""
        port = self.srv.server_address[1]
        h = {"Host": f"127.0.0.1:{port}", "X-Cinex": "1", "Content-Type": "application/json", **(headers or {})}
        h = {k: v for k, v in h.items() if v is not None}
        data = None if body is None else json.dumps(body).encode("utf-8")
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for k, v in h.items(): c.putheader(k, v)
            c.putheader("Content-Length", str(len(data or b"")))
            c.endheaders(data)
            r = c.getresponse(); raw = r.read()
            try: return r.status, json.loads(raw) if raw else None
            except ValueError: return r.status, None
        finally: c.close()
