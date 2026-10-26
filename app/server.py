"""Cinex app — local server. Run with the reelsenv python:

    python app/server.py [--port 8765] [--open]

Serves the editor at http://127.0.0.1:8765 . Only this computer can reach it (bound to 127.0.0.1), and
requests from other websites are refused (Host/Origin checks + a custom header the page must send),
so a page you visit can't read your projects or start exports.
All edits go to ~/reels/<name>/cinex.json, the same file Claude Code reads and edits (scripts/app_project.py).
"""
import json, mimetypes, os, re, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

APP = Path(__file__).resolve().parent
SCRIPTS = APP.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import app_project as P  # noqa: E402

STATIC = APP / "static"
PORT = 8765
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)       # no console window flashing on Windows
MAX_BODY = 25 * 1024 * 1024                     # font uploads
EDITABLE = {"segments", "captions", "cut_locked", "keywords", "fix", "format", "camera", "color", "motions", "sfx"}
WEIGHTS = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]
_FONTS = {}


def fonts():
    """Built-in + ~/reels-banco/fontes families, as the render engine sees them."""
    if not _FONTS:
        import reels_lib as R
        for fam, f in R.FONTS.items():
            fp = Path(f); fp = fp if fp.is_absolute() else R.ASSETS / fp
            label = {"sans": "Montserrat", "serif": "Libre Baskerville Itálico", "cond": "Bebas Neue", "hand": "Caveat"}.get(fam, fam)
            _FONTS[fam] = dict(id=fam, label=label, path=str(fp), weights=WEIGHTS if fam == "sans" else [])
    return _FONTS


def running(name):
    j = P.read_job(name, "export")
    return j and not j.get("done", True)


class H(BaseHTTPRequestHandler):
    server_version = "Cinex"
    protocol_version = "HTTP/1.1"     # keep-alive: closing right after the body can cut large responses on Windows

    def log_message(self, fmt, *args):            # quiet: only errors
        if args and str(args[1])[0] in "45": sys.stderr.write("%s %s\n" % (self.command, self.path))

    # ---------------------------------------------------------------- guards
    def _allowed(self, write):
        ok_hosts = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        if self.headers.get("Host") not in ok_hosts: return False          # DNS rebinding
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc not in ok_hosts: return False
        if write and self.headers.get("X-Cinex") != "1": return False      # forces a CORS preflight we never answer
        return True

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
                                                    "font-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(body)

    def _err(self, code, msg): self._send(code, {"error": msg})

    def _json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1024 * 1024: raise ValueError("corpo grande demais")
        return json.loads(self.rfile.read(n) or b"{}")

    def _file(self, path, ctype=None):
        path = Path(path)
        if not path.is_file(): return self._err(404, "arquivo não encontrado")
        size = path.stat().st_size; ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        a, b = 0, size - 1
        if rng and (rng.group(1) or rng.group(2)):
            if rng.group(1): a = int(rng.group(1)); b = int(rng.group(2)) if rng.group(2) else size - 1
            else: a = size - int(rng.group(2))
            b = min(b, size - 1)
            if a > b: return self._send(416, b"", extra={"Content-Range": f"bytes */{size}"})
        self.send_response(206 if rng and (rng.group(1) or rng.group(2)) else 200)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1)); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")      # always revalidate: app updates show up on reload
        if rng and (rng.group(1) or rng.group(2)): self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(a); left = b - a + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk: break
                try: self.wfile.write(chunk)
                except (ConnectionResetError, BrokenPipeError): return
                left -= len(chunk)

    # ---------------------------------------------------------------- routes
    def do_GET(self):
        if not self._allowed(False): return self._err(403, "origem não permitida")
        u = urlparse(self.path); parts = [p for p in u.path.split("/") if p]
        try:
            if not parts: return self._file(STATIC / "index.html", "text/html; charset=utf-8")
            if parts[0] == "static" and len(parts) == 2:
                f = (STATIC / parts[1]).resolve()
                if f.parent != STATIC.resolve(): return self._err(404, "não encontrado")
                return self._file(f)
            if parts == ["api", "projects"]: return self._send(200, P.projects())
            if parts == ["api", "fonts"]:
                return self._send(200, [dict(id=f["id"], label=f["label"], weights=f["weights"]) for f in fonts().values()])
            if parts == ["api", "sfx"]:                 # sound categories of ~/reels-banco/sfx
                import banco
                return self._send(200, {k: len(v) for k, v in sorted(banco.sfx().items())})
            if parts[:2] == ["api", "sfx"] and len(parts) == 3:
                import banco
                if parts[2] not in banco.sfx(): return self._err(404, "categoria sem sons")
                f = banco.sfx_file(parts[2], float(parse_qs(u.query).get("t", ["0"])[0] or 0))
                return self._file(f)
            if parts[:2] == ["api", "font"] and len(parts) == 3:
                fid = parts[2]
                if fid in fonts(): return self._file(fonts()[fid]["path"], "font/ttf")
                proj = parse_qs(u.query).get("p", [""])[0]
                f = (P.folder(proj) / "fonts" / fid).resolve()
                if f.parent != (P.folder(proj) / "fonts").resolve(): return self._err(404, "não encontrado")
                return self._file(f, "font/ttf")
            if parts[:2] == ["api", "p"] and len(parts) >= 3:
                name = parts[2]; d = P.folder(name)
                if not (d / "cinex.json").exists() and not (d / "prep.json").exists(): return self._err(404, "projeto não existe")
                sub = parts[3] if len(parts) > 3 else ""
                if sub == "":
                    st = P.load(name) if (d / "cinex.json").exists() else None
                    return self._send(200, dict(state=st, prep=P.read_job(name, "prep"), export=P.read_job(name, "export"),
                                                project_fonts=sorted(p.name for p in (d / "fonts").glob("*")) if (d / "fonts").exists() else []))
                if sub == "poll":
                    rev = P.load(name)["rev"] if (d / "cinex.json").exists() else -1
                    return self._send(200, dict(rev=rev, prep=P.read_job(name, "prep"), export=P.read_job(name, "export")))
                if sub == "words": return self._file(d / "words_raw.json", "application/json")
                if sub == "waveform": return self._file(d / "waveform.json", "application/json")
                if sub == "faces":                     # preview only needs the biggest face centre (0..1) per 0.1 s
                    p = d / "faces_preview.json"
                    if not p.exists(): return self._err(404, "rostos ainda não analisados")
                    out = []
                    for fr in json.loads(p.read_text(encoding="utf-8")):
                        g = max(fr["f"], key=lambda x: x[3], default=None)
                        out.append([round((g[0] + g[2] / 2) / 360, 3), round((g[1] + g[3] / 2) / 640, 3)] if g else 0)
                    return self._send(200, out)
                if sub == "preview.mp4": return self._file(d / "preview.mp4", "video/mp4")
            return self._err(404, "rota não encontrada")
        except ValueError as e: return self._err(400, str(e))

    def do_HEAD(self): return self.do_GET()

    def do_PUT(self): return self.do_POST()

    def do_POST(self):
        if not self._allowed(True): return self._err(403, "origem não permitida")
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        try:
            if parts == ["api", "projects"]:
                body = self._json(); src = Path(str(body.get("src", "")).strip().strip('"')).expanduser()
                if not src.is_file(): return self._err(400, f"vídeo não encontrado: {src}")
                name = body.get("name") or re.sub(r"[^A-Za-z0-9_.-]", "_", src.stem)[:64]
                P.folder(name).mkdir(parents=True, exist_ok=True)
                P.job(name, "prep", step="Começando", pct=1, done=False, error=None)
                subprocess.Popen([sys.executable, str(SCRIPTS / "app_project.py"), "new", str(src), "--name", name],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                return self._send(200, {"name": name})
            if parts[:2] != ["api", "p"] or len(parts) != 4: return self._err(404, "rota não encontrada")
            name, sub = parts[2], parts[3]
            if not (P.folder(name) / "cinex.json").exists(): return self._err(404, "projeto não existe")
            if sub == "state":
                body = {k: v for k, v in self._json().items() if k in EDITABLE}
                if body.get("format", "vertical") not in ("vertical", "horizontal"): return self._err(400, "formato inválido")
                if not all(isinstance(body.get(k, {}), dict) for k in ("camera", "color", "captions")): return self._err(400, "valor inválido")
                for m in body.get("motions", []):
                    if not (isinstance(m, dict) and m.get("type") in P.MOTIONS and isinstance(m.get("t0"), (int, float))
                            and isinstance(m.get("t1"), (int, float)) and m["t1"] > m["t0"]): return self._err(400, "motion inválido")
                for s_ in body.get("sfx", []):
                    if not (isinstance(s_, dict) and isinstance(s_.get("t"), (int, float)) and isinstance(s_.get("cat"), str)):
                        return self._err(400, "som inválido")
                if "segments" in body:
                    for g in body["segments"]:
                        if not (isinstance(g.get("s"), (int, float)) and isinstance(g.get("e"), (int, float)) and isinstance(g.get("keep"), bool)):
                            return self._err(400, "segmento inválido")
                st = P.update(name, lambda s: s.update(body))
                return self._send(200, {"rev": st["rev"]})
            if sub == "chat":
                text = str(self._json().get("text", "")).strip()[:4000]
                if not text: return self._err(400, "mensagem vazia")
                P.say(name, text, who="user"); return self._send(200, {"ok": True})
            if sub == "export":
                if running(name): return self._err(409, "exportação já em andamento")
                P.job(name, "export", step="Começando", pct=1, done=False, error=None, out=None)
                subprocess.Popen([sys.executable, str(SCRIPTS / "app_project.py"), "export", name],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
                return self._send(200, {"ok": True})
            if sub == "font":
                fn = Path(self.headers.get("X-Filename", "")).name
                if not re.fullmatch(r"[\w .()-]{1,80}\.(ttf|otf)", fn, re.I): return self._err(400, "envie um arquivo .ttf ou .otf")
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 < n <= MAX_BODY: return self._err(400, "arquivo grande demais (máx. 25 MB)")
                data = self.rfile.read(n)
                if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"): return self._err(400, "não parece uma fonte TrueType/OpenType")
                d = P.folder(name) / "fonts"; d.mkdir(exist_ok=True); (d / fn).write_bytes(data)
                P.update(name, lambda s: s["captions"].update(font=fn))
                return self._send(200, {"font": fn})
            return self._err(404, "rota não encontrada")
        except (ValueError, KeyError, json.JSONDecodeError) as e: return self._err(400, str(e))
        except TimeoutError as e: return self._err(503, str(e))


def main():
    global PORT
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=PORT); ap.add_argument("--open", action="store_true")
    a = ap.parse_args(); PORT = a.port
    sys.stdout.reconfigure(encoding="utf-8")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Cinex rodando em {url}  (Ctrl+C para parar)", flush=True)
    if a.open: threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
