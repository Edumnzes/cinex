"""Fake `claude` CLI for the tests: canned stream-json events per scenario; every call is logged.

    python fake_claude.py <scenario> [the args the worker built...]

Scenarios: ok (text answer), edita (captions.size += 10 in the project of the cwd, like a tool call would),
lento (init, then sleeps 60 s: the test kills it), ferramentas (two tool calls 0.8 s apart: status steps),
reserva (init reports sonnet: the fallback model answered), nao_logado ("Not logged in", exit 1),
offline (api_retry with no HTTP status, then sleeps 30 s), limite (rate_limit_event with resetsAt = now + FAKE_RESET s,
none when FAKE_RESET=0, then a 429 result), falha (is_error, exit 1), modelo (404 "model not available" with
--model opus, else like ok), pausa (sleeps FAKE_SLEEP s, default 0.5, then answers "ok: <request>"),
edita_lento (sleeps 1 s, then like edita). `auth status` prints FAKE_AUTH (default {"loggedIn": true}), exit 0 only if logged in.
Log: FAKE_CLAUDE_LOG, one JSON event per line ({"ev": "start", argv, stdin, cwd}, {"ev": "end"}, {"ev": "auth", argv}).
Unknown args are ignored. The init event reports model "claude-<alias>-test" from --model.
"""
import json, os, sys, time
from pathlib import Path


def log(**ev):
    p = os.environ.get("FAKE_CLAUDE_LOG")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(ev, pid=os.getpid(), t=time.time()), ensure_ascii=False) + "\n")


def emit(**ev):
    sys.stdout.write(json.dumps(ev, ensure_ascii=False) + "\n"); sys.stdout.flush()


def text(t): return dict(type="assistant", message=dict(role="assistant", content=[dict(type="text", text=t)]))


def tool(name, **inp):
    return dict(type="assistant", message=dict(role="assistant", content=[dict(type="tool_use", id="toolu_x", name=name, input=inp)]))


def erro(t, rc=1, **kw):
    emit(type="result", subtype="success", is_error=True, result=t, **kw)   # the CLI says "success" even then
    return rc


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    scen, args = (argv[1] if len(argv) > 1 else "ok"), argv[2:]
    if args[:2] == ["auth", "status"]:
        log(ev="auth", argv=args)
        out = os.environ.get("FAKE_AUTH", '{"loggedIn": true}'); print(out)
        return 0 if json.loads(out).get("loggedIn") else 1
    if "-p" not in args: return 0
    stdin = sys.stdin.buffer.read().decode("utf-8", "replace")
    log(ev="start", argv=args, stdin=stdin, cwd=os.getcwd())
    alias = args[args.index("--model") + 1] if "--model" in args else "haiku"
    try:
        emit(type="system", subtype="init", model=f"claude-{'sonnet' if scen == 'reserva' else alias}-test", tools=[],
             mcp_servers=[dict(name="cinex", status="connected")])
        if scen == "lento":
            time.sleep(60)
        elif scen == "nao_logado":
            return erro("Not logged in · Please run /login")
        elif scen == "offline":
            emit(type="system", subtype="api_retry", attempt=1, error_status=None, error="connection"); time.sleep(30)
        elif scen == "limite":
            reset = int(os.environ.get("FAKE_RESET", "1"))
            if reset: emit(type="rate_limit_event", rate_limit_info=dict(status="rejected", resetsAt=int(time.time()) + reset))
            return erro("Claude AI usage limit reached", api_error_status=429)
        elif scen == "falha":
            return erro("Erro inesperado")
        elif scen == "modelo" and alias == "opus":
            return erro("model not available for your plan", api_error_status=404)
        elif scen == "ferramentas":
            emit(**tool("mcp__cinex__cortar_ou_manter", trecho="12", manter=False)); time.sleep(.8)
            emit(**tool("mcp__cinex__ajustar", campo="captions", valor=dict(size=70))); time.sleep(.8)
            emit(**text("Cortei o trecho 12 e aumentei a legenda."))
            emit(type="result", subtype="success", is_error=False, result="Cortei o trecho 12 e aumentei a legenda.")
        elif scen == "pausa":
            time.sleep(float(os.environ.get("FAKE_SLEEP", ".5")))
            ped = [x.strip() for x in stdin.split("Pedido do usuário:")[-1].splitlines() if x.strip()]
            emit(type="result", subtype="success", is_error=False, result="ok: " + (ped[-1] if ped else ""))
        elif scen in ("edita", "edita_lento"):
            if scen == "edita_lento": time.sleep(1)
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            import app_project as P                  # CINEX_ROOT comes from the environment
            P.update(Path.cwd().name, lambda s: s["captions"].update(size=s["captions"]["size"] + 10))
            emit(type="assistant", message=dict(role="assistant", content=[dict(
                type="tool_use", id="toolu_1", name="mcp__cinex__ajustar", input=dict(campo="captions", valor=dict(size=72)))]))
            emit(type="user", message=dict(role="user", content=[dict(type="tool_result", tool_use_id="toolu_1", content="ok")]))
            emit(**text("Deixei a legenda maior."))
            emit(type="result", subtype="success", is_error=False, result="Deixei a legenda maior.")
        else:
            emit(**text("Pronto."))
            emit(type="result", subtype="success", is_error=False, result="Pronto.")
    finally:
        log(ev="end")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
