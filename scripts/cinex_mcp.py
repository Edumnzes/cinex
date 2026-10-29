"""Cinex MCP server for the app's chat: the AI's ONLY tools, bound to ONE project.

    python cinex_mcp.py <projeto>          the chat's tools
    python cinex_mcp.py <projeto> --voz    only enviar_audio / baixar_voz, for the separate Adobe call (chat_ai.adobe_voice)

Started by `claude -p` (scripts/chat_ai.py, --mcp-config). Speaks MCP over stdio (JSON-RPC 2.0, one message per
line). No tool takes a project name or a path: everything happens in the project given in argv. Before the first
change of the process (= one AI answer) the project gets a saved point (ponto_salvo.json), so "volta como estava"
undoes the whole answer (D-03).
"""
import contextlib, json, sys, urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import app_project as P  # noqa: E402

CAMPOS = ("captions", "camera", "color", "format", "motions", "sfx", "broll", "keywords", "fix", "order", "cut_locked",
          "motion_engine")       # not music (has a path), segments (cortar_ou_manter), guia, estilo, marca
DEFAULTS = {"captions": P.CAPTIONS, "camera": P.CAMERA, "color": P.COLOR}
MUTATING = {"cortar_ou_manter", "corrigir_texto", "ajustar", "camera_lenta", "ressincronizar"}


def need(a, k, t):
    """Argument a[k] of type t (bool is never a number); ValueError for the AI to fix its call."""
    v = a.get(k)
    if not isinstance(v, t) or (isinstance(v, bool) and bool not in (t if isinstance(t, tuple) else (t,))):
        raise ValueError(f"'{k}' inválido")
    return v


def same_kind(v, d):
    if isinstance(d, bool): return isinstance(v, bool)
    if isinstance(d, (int, float)): return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, type(d))


def t_show(name, a): return P.show_text(name)


def t_seg(name, a):
    P.set_seg(name, need(a, "trecho", str), need(a, "manter", bool), a.get("motivo") if isinstance(a.get("motivo"), str) else None)
    return P.show_text(name)


def t_text(name, a):
    P.edit_text(name, float(need(a, "inicio", (int, float))), float(need(a, "fim", (int, float))), need(a, "texto", str))
    return P.show_text(name)


# ponytail: one generic field tool reuses validate_patch instead of one tool per field; if the AI gets it wrong too
# often, add specific tools.
def t_adjust(name, a):
    campo, valor = need(a, "campo", str), a.get("valor")
    if campo not in CAMPOS: raise ValueError(f"campo não editável: {campo}")
    def fn(st):
        if campo in DEFAULTS:
            if not isinstance(valor, dict): raise ValueError("valor precisa ser um objeto com as chaves a mudar")
            bad = [k for k, v in valor.items() if k not in DEFAULTS[campo] or not same_kind(v, DEFAULTS[campo][k])]
            if bad: raise ValueError(f"chave inválida em {campo}: {', '.join(bad)}")
            patch = P.validate_patch({campo: {**(st.get(campo) or DEFAULTS[campo]), **valor}})
        else:
            if campo == "cut_locked" and not isinstance(valor, bool): raise ValueError("cut_locked precisa ser true ou false")
            if campo == "motion_engine" and valor not in ("html", "classico"): raise ValueError("motion_engine: html ou classico")
            if campo == "keywords" and not (isinstance(valor, list) and all(isinstance(k, str) for k in valor)):
                raise ValueError("keywords precisa ser uma lista de textos")
            if campo == "fix" and not (isinstance(valor, dict) and all(isinstance(v, str) for v in valor.values())):
                raise ValueError("fix precisa ser um objeto texto → texto")
            if campo in ("motions", "sfx", "broll", "order") and not isinstance(valor, list): raise ValueError(f"{campo} precisa ser uma lista")
            patch = P.validate_patch({campo: valor})
            if campo in ("motions", "sfx", "broll"):             # show_text lists items by id
                nxt = max((x["id"] for x in valor if isinstance(x.get("id"), int)), default=0) + 1
                for x in valor:
                    if not isinstance(x.get("id"), int): x["id"] = nxt; nxt += 1
        st.update(patch)
    P.update(name, fn)
    return P.show_text(name)


def t_slow(name, a):
    s, e, _ = P.slow_peak(name, need(a, "trecho", int))
    return f"Câmera lenta em {s:.2f}-{e:.2f} s.\n" + P.show_text(name)


def t_version(name, a):
    sec = need(a, "segundos", int)
    if not 5 <= sec <= 180: raise ValueError("segundos entre 5 e 180")
    new = P.version_name(name, sec)
    if P.folder(new).exists(): raise ValueError(f"essa versão já existe: {new}; abra ela no app")   # make_version would erase it
    new, total = P.make_version(name, sec)
    return f"Criei o projeto {new} ({total:.0f} s). O original não mudou.\n" + P.show_text(new)


def t_review(name, a):
    import revisao
    return json.dumps(revisao.review(name), ensure_ascii=False)[:6000]


def t_resync(name, a): P.resync_words(name); return P.show_text(name)


def t_restore(name, a): P.restore(name); return "Voltei ao ponto salvo.\n" + P.show_text(name)


ACOES_CONFIRMAR = ("exportar", "adobe")


def t_confirm(name, a):
    """D-01: does nothing. chat_ai sees the call in the stream and puts the confirmation button in the answer;
    the action itself only runs when the user clicks it (the AI has no tool that exports)."""
    if a.get("acao") not in ACOES_CONFIRMAR: raise ValueError("ação desconhecida")
    return "Ok: o botão de confirmação vai aparecer na sua resposta. Não diga que já foi feito."


S, N, B, I = {"type": "string"}, {"type": "number"}, {"type": "boolean"}, {"type": "integer"}
TOOLS = {   # name: (fn, description, properties, required)
    "ver_projeto": (t_show, "Lê o projeto agora: trechos (id, início-fim em segundos, KEEP/cut, texto), legenda, motions, sons, B-roll.", {}, []),
    "cortar_ou_manter": (t_seg, "Corta (manter=false) ou mantém (manter=true) um trecho: pelo id ('12') ou por intervalo em segundos da gravação ('12.3-14.0').",
                         {"trecho": S, "manter": B, "motivo": S}, ["trecho", "manter"]),
    "corrigir_texto": (t_text, "Corrige o que foi dito entre inicio e fim (segundos da gravação): legenda e textos acompanham.",
                       {"inicio": N, "fim": N, "texto": S}, ["inicio", "fim", "texto"]),
    "ajustar": (t_adjust, "Muda um campo do projeto. captions/camera/color: só as chaves a mudar (ex.: {\"size\": 80}). "
                          "Listas (motions, sfx, broll, order, keywords) vão inteiras. format: vertical, feed, quadrado, horizontal, 4x3, led.",
                {"campo": {"type": "string", "enum": list(CAMPOS)}, "valor": {"description": "novo valor (JSON)"}}, ["campo", "valor"]),
    "camera_lenta": (t_slow, "Câmera lenta (sem som) no pico de ação de um trecho mantido, pelo id do trecho.", {"trecho": I}, ["trecho"]),
    "versao_curta": (t_version, "Cria uma versão curta como projeto NOVO (<projeto>_<s>s) com as melhores frases. O original não muda.",
                     {"segundos": dict(I, minimum=5, maximum=180)}, ["segundos"]),
    "revisar": (t_review, "Revisão do projeto: ritmo, duração, motions, legenda, com sugestões.", {}, []),
    "ressincronizar": (t_resync, "Reajusta o tempo das palavras ao áudio (legenda fora de sincronia).", {}, []),
    "voltar_como_estava": (t_restore, "Volta o projeto ao ponto salvo antes da sua última resposta que mudou algo. A conversa fica.", {}, []),
    "confirmar": (t_confirm, "Mostra à pessoa, na sua resposta, um botão para ela confirmar a ação (exportar = gerar o vídeo final; "
                             "adobe = limpar a voz no Adobe Podcast). "
                             "NÃO executa nada: a ação só começa quando ela tocar no botão.",
                  {"acao": {"type": "string", "enum": list(ACOES_CONFIRMAR)}}, ["acao"]),
}


# ------------------------------------------------------------ --voz: the Adobe call's only network (D-02)
ADOBE_HOSTS = ("adobe.io", "adobe.com", "amazonaws.com")   # [ASSUMED] confirmed at the plan 08 checkpoint
MAX_VOZ = 500 * 1024 * 1024
EXTS = (".wav", ".mp3", ".m4a", ".aac", ".flac")


def url_ok(u):
    """https, port 443, no user:password, host = one of ADOBE_HOSTS or a subdomain of it (adobe.io.evil.com is not)."""
    try:
        p = urlparse(u) if isinstance(u, str) else None
        if not p or p.scheme != "https" or p.username or p.password or p.port not in (None, 443): return False
    except ValueError: return False                              # bad port
    h = (p.hostname or "").lower()
    return any(h == x or h.endswith("." + x) for x in ADOBE_HOSTS)


class _Redir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not url_ok(newurl): raise ValueError("redirecionamento para endereço não permitido")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_open = urllib.request.build_opener(_Redir).open


def _put(url, path):
    req = urllib.request.Request(url, data=Path(path).read_bytes(), method="PUT", headers={"Content-Type": "audio/wav"})
    with _open(req, timeout=300) as r:
        if not 200 <= r.status < 300: raise ValueError(f"upload recusado ({r.status})")


def _get(url, dest):
    tmp, n = dest.with_name(dest.name + ".tmp"), 0
    try:
        with _open(url, timeout=300) as r, open(tmp, "wb") as f:
            while b := r.read(1 << 20):
                n += len(b)
                if n > MAX_VOZ: raise ValueError("arquivo grande demais")
                f.write(b)
        P._replace(tmp, dest)
    finally: tmp.unlink(missing_ok=True)


def _voz(name): return P.folder(name) / "voz"


def t_send(name, a):
    """Always the fixed voz/voice.wav (no path argument), once per try (the export cleans voz/ before each try)."""
    u, vd = need(a, "endereco", str), _voz(name)
    if not url_ok(u): raise ValueError("endereço não permitido")
    if (vd / "enviado").exists(): raise ValueError("o áudio já foi enviado nesta tentativa")
    if not (vd / "voice.wav").is_file(): raise ValueError("áudio não encontrado")
    (vd / "enviado").write_text("1")          # before the PUT: a half-sent file still counts as "the audio left"
    _put(u, vd / "voice.wav")
    return "Áudio enviado."


def t_fetch(name, a):
    urls = {"fala": need(a, "fala", str)}
    if a.get("fundo") is not None: urls["fundo"] = need(a, "fundo", str)
    if not all(url_ok(u) for u in urls.values()): raise ValueError("endereço não permitido")   # all checked before any download
    for k, u in urls.items():
        ext = Path(urlparse(u).path).suffix.lower()
        _get(u, _voz(name) / (k + (ext if ext in EXTS else ".wav")))
    return "Voz baixada."


VOZ_TOOLS = {
    "enviar_audio": (t_send, "Envia o áudio da fala (o arquivo fixo deste projeto, uma vez) para o endereço de upload do Adobe.",
                     {"endereco": S}, ["endereco"]),
    "baixar_voz": (t_fetch, "Baixa a voz limpa (fala = enhanced_speech) e, se houver, o fundo (background) para o projeto.",
                   {"fala": S, "fundo": S}, ["fala"]),
}


def serve(name, tools):
    sys.stdin.reconfigure(encoding="utf-8"); sys.stdout.reconfigure(encoding="utf-8")
    out, saved = sys.stdout, False
    def reply(i, result=None, error=None):
        out.write(json.dumps({"jsonrpc": "2.0", "id": i, **({"error": error} if error else {"result": result})}, ensure_ascii=False) + "\n")
        out.flush()
    for line in sys.stdin:
        try: m = json.loads(line)
        except ValueError: continue
        if not isinstance(m, dict) or m.get("id") is None: continue          # notifications
        i, meth, prm = m["id"], m.get("method"), m.get("params") or {}
        if meth == "initialize":
            reply(i, {"protocolVersion": prm.get("protocolVersion"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "cinex", "version": "1"}})
        elif meth == "ping": reply(i, {})
        elif meth == "tools/list":
            reply(i, {"tools": [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": r,
                                                                             "additionalProperties": False}}
                                for n, (_, d, p, r) in tools.items()]})
        elif meth == "tools/call":
            n, a = prm.get("name"), prm.get("arguments") or {}
            try:
                if n not in tools: raise ValueError(f"ferramenta desconhecida: {n}")
                with contextlib.redirect_stdout(sys.stderr):             # stdout is the protocol channel
                    if n in MUTATING and not saved: P.snapshot(name); saved = True   # one answer = one saved point
                    text, err = tools[n][0](name, a if isinstance(a, dict) else {}), False
            except Exception as e: text, err = f"Não deu: {e}", True        # the AI sees it and can fix its call
            reply(i, {"content": [{"type": "text", "text": text}], "isError": err})
        else: reply(i, error={"code": -32601, "message": "método desconhecido"})


def main(argv):
    try:
        if argv[2:] not in ([], ["--voz"]) or len(argv) < 2: raise ValueError(f"argumentos: {argv[1:]}")
        if not (P.folder(argv[1]) / "cinex.json").is_file(): raise ValueError(f"projeto não encontrado: {argv[1:]}")
    except ValueError as e:
        sys.stderr.write(f"uso: cinex_mcp.py <projeto> [--voz] ({e})\n"); return 2
    serve(argv[1], VOZ_TOOLS if argv[2:] else TOOLS); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
