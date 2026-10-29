"""Fake `claude` CLI for the tests: canned stream-json events per scenario; every call is logged.

    python fake_claude.py <ok|edita|lento> [the args the worker built...]

Scenarios: ok (text answer), edita (captions.size += 10 in the project of the cwd, like a tool call would),
lento (init, then sleeps 60 s: the test kills it). Log: FAKE_CLAUDE_LOG, one JSON event per line
({"ev": "start", argv, stdin, cwd} and {"ev": "end"}). Unknown args are ignored.
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


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    scen, args = (argv[1] if len(argv) > 1 else "ok"), argv[2:]
    if "-p" not in args: return 0
    stdin = sys.stdin.buffer.read().decode("utf-8", "replace")
    log(ev="start", argv=args, stdin=stdin, cwd=os.getcwd())
    try:
        emit(type="system", subtype="init", model="claude-haiku-4-5", tools=[],
             mcp_servers=[dict(name="cinex", status="connected")])
        if scen == "lento":
            time.sleep(60)
        elif scen == "edita":
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
