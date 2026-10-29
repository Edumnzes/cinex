"""Cinex app chat, automatic mode: one worker per project runs `claude -p` with only the Cinex tools
(scripts/cinex_mcp.py, bound to that project) and answers in the app's chat. Called by app/server.py (kick).

The AI has no built-in tool at all (no Bash, Read, Edit, WebFetch): its only hands are the MCP server's tools.
The user's text goes through stdin, never argv.
"""
import datetime, json, os, re, shutil, signal, socket, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import app_project as P  # noqa: E402

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CLAUDE_CMD = None                          # test hook: command prefix that replaces the claude executable
MODEL_FAST, MODEL_SMART, MODEL_SAFE = "haiku", "opus", "sonnet"    # Pro plan: sonnet is the fallback (D-05)
SMART = re.compile(r"gancho|reescrev|roteiro|ideia|criativ|analis|perfil|revis|legenda do post|hashtag|sugest", re.I)
MAX_TURNS = 25
PROMPT_FILE = HERE / "chat_prompt.md"
TXT_FALHA = "Não consegui responder agora. Nada se perdeu: o que eu já tinha mudado ficou no projeto."
TXT_PARADO = ("Parei por aqui. O que eu já tinha mudado ficou no projeto. "
              "Se quiser voltar como estava antes, é só pedir: “volta como estava”.")
TXT_TEMPO = ("Este pedido passou de 10 minutos e eu parei para não gastar seu uso à toa. "
             "O que eu já tinha mudado ficou no projeto.")
TXT_SETUP = {"missing": "Falta instalar o Claude Code", "login": "Falta entrar na sua conta do Claude Code"}   # card title
TIMEOUT, NET_RETRY, LIMIT_RETRY, LIMIT_MAX = 600, 30, 300, 1800   # seconds (D-06, D-13); the tests shrink them
_CHAT, _CHAT_LOCK = {}, threading.Lock()   # name -> {"proc": Popen | None, "stop": False, "ev": Event}: one worker per project
# ponytail: one pause for the whole server on purpose: the usage limit belongs to the account and "no internet" to the
# machine, so while it lasts no project may spend a call. Lost on restart, which is fine: the messages stay unseen.
_PAUSA = {"erro": None, "ate": 0, "conhecido": False, "n": 0}   # erro: "sem_rede" | "limite"; n: limits in a row
MODEL_BLOCK = set()                        # aliases the account can't use (Pro plan: opus) -> MODEL_SAFE from now on
_USO_LOCK = threading.Lock()               # daily counter: only the server process writes it

# status line (D-08): what the AI is doing, in plain Portuguese. Shown with textContent only.
RESERVA = "Trabalhando no seu pedido…"
LABEL = {"ver_projeto": "Lendo o projeto…", "revisar": "Olhando o vídeo e as legendas…",
         "corrigir_texto": "Corrigindo o texto da legenda…", "ressincronizar": "Acertando o tempo das legendas…"}
ACOES = {"exportar": "export"}             # confirmar(acao) -> the button in the answer (D-01); anything else: no button


def claude_exe():
    """claude on PATH, else the native installer's spot (not on PATH on the user's machine)."""
    for c in (os.environ.get("CINEX_CLAUDE"), shutil.which("claude"),
              str(Path.home() / ".local/bin/claude.exe"), str(Path.home() / ".local/bin/claude")):
        if c and Path(c).is_file(): return c
    return None


def base_cmd():
    if CLAUDE_CMD: return list(CLAUDE_CMD)
    exe = claude_exe()
    return [exe] if exe else None


def child_env():
    """Drop what a parent Claude Code session leaks (the server is often started by one): CLAUDE_CODE_SIMPLE would
    force bare mode (no OAuth login) and ANTHROPIC_BASE_URL points at the parent's proxy."""
    e = dict(os.environ)
    for k in list(e):
        if k == "CLAUDECODE" or k.startswith(("CLAUDE_CODE_", "CLAUDE_AGENT_SDK")): e.pop(k)
    if "CLAUDE_CODE_ENTRYPOINT" in os.environ: e.pop("ANTHROPIC_BASE_URL", None)
    e["CLAUDE_CODE_MAX_RETRIES"] = "2"         # fail fast offline instead of retrying for minutes
    return e


def pick_model(text, passo, livre=False):
    """D-05 by keywords + page: creativity and analysis get the capable model, simple edits the fast one.
    A model the account refused (MODEL_BLOCK) becomes MODEL_SAFE, unless livre (what was asked, for `reserva`)."""
    m = MODEL_SMART if SMART.search(text or "") or passo == "revisao" else MODEL_FAST
    return MODEL_SAFE if m in MODEL_BLOCK and not livre else m


def command(base, name, model):
    """The locked-down call. Only fixed values and the already validated project name: never the user's text."""
    mcp = {"mcpServers": {"cinex": {"type": "stdio", "command": sys.executable, "args": [str(HERE / "cinex_mcp.py"), name]}}}
    return (base + ["-p", "--output-format", "stream-json", "--verbose", "--model", model]
            + (["--fallback-model", MODEL_SAFE] if model != MODEL_SAFE else [])
            + ["--max-turns", str(MAX_TURNS),
               "--tools", "",                     # no built-in tool: no Bash, Read, Edit, WebFetch, Agent
               "--mcp-config", json.dumps(mcp), "--strict-mcp-config",
               "--allowedTools", "mcp__cinex",    # every tool of OUR server, nothing else
               "--permission-mode", "dontAsk",    # anything not allowed is denied, never asks
               "--setting-sources", "",           # ignore user/project settings: no hooks, skills, allow rules
               "--disable-slash-commands", "--no-session-persistence",
               "--system-prompt-file", str(PROMPT_FILE)])


def build_prompt(name, i, msg):
    """stdin of the call: header (never starts with "/"), project state, recent chat, the request."""
    prev = [f"{'Você' if c['who'] == 'user' else 'Cinex'}: {c['text'][:300]}" for c in P.load(name)["chat"][:i][-6:]]
    lines = [f"Projeto: {name}. Página: {msg.get('passo') or 'editor'}.", "", "Estado atual do projeto:", P.show_text(name)[:12000], ""]
    if prev: lines += ["Conversa recente:", *prev, ""]
    return "\n".join(lines + ["Pedido do usuário:", msg["text"]])


def label(tool, a):
    """Status line for one Cinex tool call; RESERVA for anything without a translation."""
    a = a if isinstance(a, dict) else {}
    n = str(a.get("trecho", a.get("segundos", "")))[:12]
    if tool == "cortar_ou_manter" and n: return f"{'Devolvendo' if a.get('manter') else 'Cortando'} o trecho {n}…"
    if tool == "camera_lenta" and n: return f"Deixando o trecho {n} em câmera lenta…"
    if tool == "versao_curta" and n: return f"Montando a versão de {n} segundos…"
    if tool == "ajustar": return {"captions": "Ajustando a legenda…", "broll": "Colocando a imagem de apoio…"}.get(a.get("campo"), RESERVA)
    return LABEL.get(tool, RESERVA)


def on_event(name, ev, S):
    """One stream-json event -> S (step, modelo, result) and chat.json, written only when something changes.
    Unknown event types are ignored: the CLI updates itself and may add new ones."""
    if not isinstance(ev, dict): return
    t, step, model = ev.get("type"), None, None
    if t == "system" and ev.get("subtype") == "init": model = ev.get("model")
    elif t == "assistant":
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
        model = msg.get("model")
        for b in msg.get("content") or []:
            if not isinstance(b, dict): continue
            if b.get("type") == "tool_use" and str(b.get("name", "")).startswith("mcp__cinex__"):
                step = label(b["name"].removeprefix("mcp__cinex__"), b.get("input"))
                if b["name"] == "mcp__cinex__confirmar":
                    S["acao"] = ACOES.get((b.get("input") if isinstance(b.get("input"), dict) else {}).get("acao"))
            elif b.get("type") == "text": step = "Escrevendo a resposta…"
        if ev.get("error"): S["erro_assist"] = ev["error"]   # "authentication_failed", "rate_limit", ...
    elif t == "result": S["result"] = ev
    elif t == "rate_limit_event" and isinstance(ev.get("rate_limit_info"), dict) and ev["rate_limit_info"].get("status") == "rejected":
        S["limite"] = ev
    elif t == "system" and ev.get("subtype") == "api_retry":   # the CLI would retry for minutes: give up now
        if ev.get("error_status") == 429 or ev.get("error") == "rate_limit": S.setdefault("limite", ev)
        elif ev.get("error_status") is None: S["offline"] = True     # no HTTP answer at all
        if S.get("proc") and (S.get("limite") or S.get("offline")): kill_tree(S["proc"])
    kw = {}
    if step and step != S.get("step"): S["step"] = kw["step"] = step
    if isinstance(model, str) and model and model != S.get("modelo"):   # Pro plan: sonnet may answer for opus
        S["modelo"] = kw["modelo"] = model; kw["reserva"] = S["pedido"] not in model
    if kw: P.job(name, "chat", **kw)


def kill_tree(p):
    """Kill the AI and everything it started (claude -> cinex_mcp). Never os.kill(pid, 0) on Windows: it kills."""
    if p.poll() is not None: return
    if os.name == "nt": subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
    else: os.killpg(p.pid, signal.SIGTERM)    # Popen(start_new_session=True)


def stop(name):
    """D-09: stop the current answer (the queue goes on). What was already saved stays. -> True if something ran."""
    with _CHAT_LOCK:
        w = _CHAT.get(name)
        if not w or not w["proc"] or w["proc"].poll() is not None: return False
        w["stop"] = True; kill_tree(w["proc"])
    return True


def _uso_path(): return P.ROOT / "_chat_uso.json"    # computed on each call: tests swap P.ROOT


def uso():
    """Automatic answers today (D-07, local midnight)."""
    p = _uso_path()
    try: d = P._read_json(p) if p.exists() else {}
    except ValueError: d = {}
    return d.get("n", 0) if d.get("dia") == datetime.date.today().isoformat() else 0


def _contar():
    with _USO_LOCK: P._write_json(_uso_path(), {"dia": datetime.date.today().isoformat(), "n": uso() + 1})


def kick(name):
    """Start the project's worker unless one is already draining its queue (then just wake it up)."""
    with _CHAT_LOCK:
        if name in _CHAT: _CHAT[name]["ev"].set(); return
        _CHAT[name] = {"proc": None, "stop": False, "ev": threading.Event()}
    threading.Thread(target=_worker, args=(name,), daemon=True).start()


def _pendente(st):
    return any(m["who"] == "user" and not m.get("seen") for m in st["chat"])   # cancelled ones are seen


def set_mode(modo):
    """D-14: Automático / Sessão aberta for the whole app (A-02). Back to auto: answer what waited meanwhile."""
    P.set_chat_mode(modo)
    if modo != "auto": return
    for p in P.projects():
        try:
            if _pendente(P.load(p["name"])): kick(p["name"])
        except Exception: pass


def ensure(name, st):
    """Called by every poll: a message waiting in auto mode with no worker (lost, or the server restarted) restarts it.
    Not while the guide card waits for "Testar de novo": that would spend a call to hear "not logged in" again."""
    if (P.chat_mode() == "auto" and name not in _CHAT and _pendente(st)
            and P.read_job(name, "chat").get("erro") not in ("nao_instalado", "nao_logado")):
        kick(name)


def _presas(chat):
    """User messages the worker took (by auto) that never got an answer: the server died in the middle."""
    return [i for i, m in enumerate(chat) if m["who"] == "user" and m.get("seen") and m.get("by") == "auto"
            and not any(x["who"] == "cinex" for x in chat[i + 1:])]


def recover():
    """Server start: back to the queue whatever was being answered, then answer. Messages taken by the open session
    (by "sessao") are left alone: it may still be answering them. One broken project never blocks the others."""
    for f in P.ROOT.glob("*/cinex.json"):
        name = f.parent.name
        try:
            st = P.load(name)
            if _presas(st["chat"]): st = P.update(name, lambda s: [s["chat"][i].update(seen=False, by=None) for i in _presas(s["chat"])])
            if P.read_job(name, "chat").get("busy"): P.job(name, "chat", busy=False, step=None)
            if P.chat_mode() == "auto" and _pendente(st): kick(name)
        except Exception: pass


def _worker(name):
    try:
        while True:
            _esperar(name)
            with _CHAT_LOCK:                   # claim + pop under kick's lock: no message stranded between them
                got = P.claim(name, "auto", 1)
                if not got: _CHAT.pop(name, None); return
            i = got[0][0]
            try: r = run_ai(name, *got[0])
            except Exception: r = P.say(name, TXT_FALHA, kind="warn", acao="tentar", ref=i)   # never leave the chat silent
            if r == "sair":                    # Claude Code missing / not logged in: wait for "Testar de novo"
                with _CHAT_LOCK: _CHAT.pop(name, None)
                return
    except BaseException:
        with _CHAT_LOCK: _CHAT.pop(name, None)  # claim/say failed: don't leave the project marked busy
        raise


def classify(S, rc):
    """Why an answer didn't come -> None (it came) | nao_logado | limite | sem_rede | modelo | falha."""
    r = S.get("result") or {}
    txt = str(r.get("result") or "") if r.get("is_error") else ""   # an answer that talks about limits is still an answer
    ea, st = S.get("erro_assist"), r.get("api_error_status")
    if ea == "authentication_failed" or re.search(r"not logged in|/login|oauth|invalid api key", txt, re.I): return "nao_logado"
    if S.get("limite") or ea == "rate_limit" or st == 429 or re.search(r"usage limit|limit reached|hit your limit|rate.?limit", txt, re.I):
        return "limite"
    if S.get("offline"): return "sem_rede"
    if st == 404 or re.search(r"model.*(not (available|found|supported)|invalid|access)|(invalid|unknown) model", txt, re.I):
        return "modelo"
    ok = r and not r.get("is_error") and isinstance(r.get("result"), str) and r["result"].strip()
    return None if ok else "falha"


def ate_limite(S):
    """When the usage limit lifts (epoch seconds), if the stream said so: resetsAt, or "...|1700000000" in the text."""
    info = (S.get("limite") or {}).get("rate_limit_info") or {}
    r = info.get("resetsAt")
    if isinstance(r, (int, float)) and not isinstance(r, bool) and r > 0: return r / 1000 if r > 1e12 else float(r)
    m = re.search(r"\|(\d{10})", str((S.get("result") or {}).get("result") or ""))
    return float(m.group(1)) if m else None


def _pausar(erro, ate=None):
    """Pause every project: until `ate` when known, else NET_RETRY (no internet) or a limit wait that doubles up to LIMIT_MAX."""
    with _CHAT_LOCK:
        n = _PAUSA["n"]
        _PAUSA.update(erro=erro, conhecido=bool(ate), n=n + (erro == "limite"),
                      ate=ate or time.time() + (NET_RETRY if erro == "sem_rede" else min(LIMIT_MAX, LIMIT_RETRY * 2 ** n)))


def _esperar(name):
    """Before each claim: while the account/machine is paused, keep this project's messages waiting (D-13)."""
    ev, waited = _CHAT[name]["ev"], False
    while _PAUSA["erro"]:
        k = len([m for m in P.load(name)["chat"] if m["who"] == "user" and not m.get("seen")])   # cancelled ones are seen
        if not k: break
        waited = True
        P.job(name, "chat", busy=False, step=None, erro=_PAUSA["erro"], k=k,
              ate=time.strftime("%H:%M", time.localtime(_PAUSA["ate"])) if _PAUSA["conhecido"] else None)
        ev.wait(max(.05, min(2, _PAUSA["ate"] - time.time()))); ev.clear()   # woken by a new message or "cancelar"
        if _PAUSA["erro"] and time.time() >= _PAUSA["ate"]:
            # a call refused by the limit costs nothing, so the next call decides; offline waits for the socket
            if _PAUSA["erro"] == "limite" or rede_ok(): _PAUSA["erro"] = None
            else: _PAUSA["ate"] = time.time() + NET_RETRY
    if waited: P.job(name, "chat", erro=None, k=0)


def rede_ok():
    try: socket.create_connection(("api.anthropic.com", 443), 3).close(); return True
    except OSError: return False


def health():
    """ "Testar de novo" (D-12) without spending usage: installed? `claude auth status` logged in? network? Never the model."""
    base, logado = base_cmd(), False
    if base:
        try:
            r = subprocess.run(base + ["auth", "status"], capture_output=True, env=child_env(), creationflags=NO_WINDOW, timeout=20)
            logado = json.loads(r.stdout.decode("utf-8", "replace")).get("loggedIn") is True
        except OSError: base = None            # the executable vanished
        except (subprocess.TimeoutExpired, ValueError, AttributeError): pass
    return dict(instalado=bool(base), logado=logado, rede=rede_ok())


def retomar(name):
    """After a good "Testar de novo": clear the setup warning, lift a network pause if the network is back, answer."""
    P.job(name, "chat", erro=None)
    if _PAUSA["erro"] == "sem_rede" and rede_ok(): _PAUSA["erro"] = None
    kick(name)


def cancelar(name):
    """Messages were cancelled: wake the waiting worker so it sees the queue now."""
    with _CHAT_LOCK:
        if name in _CHAT: _CHAT[name]["ev"].set()


def _setup(name, i, reason):
    """Claude Code missing or not logged in: the message waits, one guide card (A-05), the worker stops."""
    P.unclaim(name, [i])
    last = next((m for m in reversed(P.load(name)["chat"]) if m["who"] == "cinex"), {})
    if (last.get("kind"), last.get("reason")) != ("setup", reason): P.say(name, TXT_SETUP[reason], kind="setup", reason=reason)
    P.job(name, "chat", busy=False, step=None, erro="nao_instalado" if reason == "missing" else "nao_logado")
    return "sair"


def run_ai(name, i, m, modelo=None):
    """One answer; every way out ends in an answer, a problem message or the guide card (never a silent chat).
    The worker is the only writer of chat.json (busy, step, desde, idx, erro, k, ate, modelo, reserva)."""
    model = modelo or pick_model(m["text"], m.get("passo"))
    S = {"pedido": pick_model(m["text"], m.get("passo"), livre=True), "step": "Lendo o projeto…", "modelo": None,
         "result": None, "proc": None, "outras": []}
    P.job(name, "chat", busy=True, step=S["step"], desde=P._now(), idx=i, erro=None, k=0, ate=None, modelo=None, reserva=False)
    timer = None
    try:
        base = base_cmd()
        if base is None: return _setup(name, i, "missing")
        prompt = build_prompt(name, i, m)
        try:
            proc = subprocess.Popen(command(base, name, model), cwd=str(P.folder(name)),
                                    env=child_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    creationflags=NO_WINDOW, start_new_session=(os.name != "nt"))
        except FileNotFoundError: return _setup(name, i, "missing")
        S["proc"] = proc
        with _CHAT_LOCK: _CHAT[name].update(proc=proc, stop=False)
        timer = threading.Timer(TIMEOUT, lambda: (S.update(tempo=True), kill_tree(proc)))   # D-06
        timer.daemon = True; timer.start()
        try: proc.stdin.write(prompt.encode("utf-8")); proc.stdin.close()
        except OSError: pass                   # died before reading: no result below -> failure message
        with proc.stdout:
            for raw in proc.stdout:            # one JSON event per line
                line = raw.decode("utf-8", "replace")
                try: on_event(name, json.loads(line), S)
                except ValueError:
                    if line.strip(): S["outras"] = (S["outras"] + [line.strip()])[-5:]   # technical detail, never shown
        rc = proc.wait()
        with _CHAT_LOCK:
            stopped, _CHAT[name]["stop"] = _CHAT[name]["stop"], False
        if stopped: return P.say(name, TXT_PARADO)    # stopped by the user: not counted
        if S.get("tempo"): return P.say(name, TXT_TEMPO, kind="warn", acao="tentar", ref=i)
        why = classify(S, rc)                  # decided by is_error: "Not logged in" comes with subtype "success"
        if why is None:
            P.say(name, S["result"]["result"].strip(), **({"acao": S["acao"]} if S.get("acao") else {})); _contar(); _PAUSA["n"] = 0
        elif why == "nao_logado": return _setup(name, i, "login")
        elif why in ("sem_rede", "limite"):
            P.unclaim(name, [i]); _pausar(why, ate_limite(S) if why == "limite" else None)
        elif why == "modelo" and model != MODEL_SAFE:   # Pro plan: no opus -> same message again with sonnet
            MODEL_BLOCK.add(model); return run_ai(name, i, m, MODEL_SAFE)
        else: P.say(name, TXT_FALHA, kind="warn", acao="tentar", ref=i, detalhe="\n".join(S["outras"])[-300:])
    finally:
        if timer: timer.cancel()
        P.job(name, "chat", busy=False, step=None)
