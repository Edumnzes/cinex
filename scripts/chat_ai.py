"""Cinex app chat, automatic mode: one worker per project runs `claude -p` with only the Cinex tools
(scripts/cinex_mcp.py, bound to that project) and answers in the app's chat. Called by app/server.py (kick).

The AI has no built-in tool at all (no Bash, Read, Edit, WebFetch): its only hands are the MCP server's tools.
The user's text goes through stdin, never argv.
"""
import datetime, json, os, re, shutil, signal, subprocess, sys, threading
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
_CHAT, _CHAT_LOCK = {}, threading.Lock()   # name -> {"proc": Popen | None, "stop": False}: one worker per project
_USO_LOCK = threading.Lock()               # daily counter: only the server process writes it

# status line (D-08): what the AI is doing, in plain Portuguese. Shown with textContent only.
RESERVA = "Trabalhando no seu pedido…"
LABEL = {"ver_projeto": "Lendo o projeto…", "revisar": "Olhando o vídeo e as legendas…",
         "corrigir_texto": "Corrigindo o texto da legenda…", "ressincronizar": "Acertando o tempo das legendas…"}


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


def pick_model(text, passo):
    """D-05 by keywords + page: creativity and analysis get the capable model, simple edits the fast one."""
    return MODEL_SMART if SMART.search(text or "") or passo == "revisao" else MODEL_FAST


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
            elif b.get("type") == "text": step = "Escrevendo a resposta…"
    elif t == "result": S["result"] = ev
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
    """Start the project's worker unless one is already draining its queue."""
    with _CHAT_LOCK:
        if name in _CHAT: return
        _CHAT[name] = {"proc": None, "stop": False}
    threading.Thread(target=_worker, args=(name,), daemon=True).start()


def _worker(name):
    try:
        while True:
            with _CHAT_LOCK:                   # claim + pop under kick's lock: no message stranded between them
                got = P.claim(name, "auto", 1)
                if not got: _CHAT.pop(name, None); return
            try: run_ai(name, *got[0])
            except Exception: P.say(name, TXT_FALHA, kind="warn")   # never leave the chat silent
    except BaseException:
        with _CHAT_LOCK: _CHAT.pop(name, None)  # claim/say failed: don't leave the project marked busy
        raise


def run_ai(name, i, m):
    """One answer. The worker is the only writer of chat.json (busy, step, desde, idx, erro, modelo, reserva)."""
    model = pick_model(m["text"], m.get("passo"))
    S = {"pedido": model, "step": "Lendo o projeto…", "modelo": None, "result": None}
    P.job(name, "chat", busy=True, step=S["step"], desde=P._now(), idx=i, erro=None, modelo=None, reserva=False)
    try:
        base = base_cmd()
        if base is None: return P.say(name, TXT_FALHA, kind="warn")
        prompt = build_prompt(name, i, m)
        proc = subprocess.Popen(command(base, name, model), cwd=str(P.folder(name)),
                                env=child_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=NO_WINDOW, start_new_session=(os.name != "nt"))
        with _CHAT_LOCK: _CHAT[name].update(proc=proc, stop=False)
        try: proc.stdin.write(prompt.encode("utf-8")); proc.stdin.close()
        except OSError: pass                   # died before reading: no result below -> failure message
        with proc.stdout:
            for raw in proc.stdout:            # one JSON event per line
                try: on_event(name, json.loads(raw.decode("utf-8", "replace")), S)
                except ValueError: continue
        proc.wait()
        with _CHAT_LOCK:
            stopped, _CHAT[name]["stop"] = _CHAT[name]["stop"], False
        if stopped: return P.say(name, TXT_PARADO)    # stopped by the user: not counted
        result = S["result"]; text = (result or {}).get("result")
        if result and not result.get("is_error") and isinstance(text, str) and text.strip():
            P.say(name, text.strip()); _contar()
        else: P.say(name, TXT_FALHA, kind="warn")    # decided by is_error: "Not logged in" comes with subtype "success"
    finally: P.job(name, "chat", busy=False, step=None)
