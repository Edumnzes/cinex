"""Cinex app chat, automatic mode: one worker per project runs `claude -p` with only the Cinex tools
(scripts/cinex_mcp.py, bound to that project) and answers in the app's chat. Called by app/server.py (kick).

The AI has no built-in tool at all (no Bash, Read, Edit, WebFetch): its only hands are the MCP server's tools.
The user's text goes through stdin, never argv.
"""
import json, os, re, shutil, subprocess, sys, threading
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
_CHAT, _CHAT_LOCK = {}, threading.Lock()   # name -> {"proc": Popen | None, "stop": False}: one worker per project


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
    base = base_cmd()
    if base is None: return P.say(name, TXT_FALHA, kind="warn")
    prompt = build_prompt(name, i, m)
    proc = subprocess.Popen(command(base, name, pick_model(m["text"], m.get("passo"))), cwd=str(P.folder(name)),
                            env=child_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=NO_WINDOW, start_new_session=(os.name != "nt"))
    _CHAT[name]["proc"] = proc
    try: proc.stdin.write(prompt.encode("utf-8")); proc.stdin.close()
    except OSError: pass                       # died before reading: no result below -> failure message
    result = None
    with proc.stdout:
        for raw in proc.stdout:                # one JSON event per line; unknown types are ignored (the CLI self-updates)
            try: ev = json.loads(raw.decode("utf-8", "replace"))
            except ValueError: continue
            if isinstance(ev, dict) and ev.get("type") == "result": result = ev
    proc.wait()
    text = (result or {}).get("result")
    if result and not result.get("is_error") and isinstance(text, str) and text.strip(): P.say(name, text.strip())
    else: P.say(name, TXT_FALHA, kind="warn")  # decided by is_error: "Not logged in" comes with subtype "success"
