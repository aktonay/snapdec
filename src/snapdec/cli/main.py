"""snapdec CLI — Typer + Rich (§9).

Commands: init | mcp | daemon | doctor | agents | project-facts |
classify/check/score/rank | models (stub) | backend | uninstall | version
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .. import config
from .._brand import NAME, __version__
from ..decisions import policy as decision_policy
from ..decisions.envelope import SystemOneRequest, failure_envelope, make_envelope
from ..decisions.tier0.project_facts import project_facts
from ..hardware import detect as hw_detect
from ..hardware import select_profile
from ..integrations.registry import ALL_INTEGRATORS
from ..runtime import ipc
from ..runtime.daemon import run_daemon
from ..runtime.lifecycle import daemon_status, start_daemon, stop_daemon, warm_daemon

# cp1252 consoles crash on box/arrow glyphs — force UTF-8 (Py3.7+)
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help=f"{NAME} — local System One decision layer for coding agents")
daemon_app = typer.Typer(no_args_is_help=True, help="Daemon control")
agents_app = typer.Typer(no_args_is_help=True, help="Agent integrations")
app.add_typer(daemon_app, name="daemon")
app.add_typer(agents_app, name="agents")
err = Console(stderr=True)
out = Console()

HOSTED_PRESETS = {
    "typesafe": ("https://api.typesafe.ai", "jev-latest", "TYPESAFE_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "", "OPENROUTER_API_KEY"),
}


# ================================================================ init


def _print_hardware() -> None:
    rep = hw_detect()
    prof = select_profile(rep)
    t = Table(title="Hardware", show_header=False, box=None)
    t.add_row("machine", rep.oneline())
    t.add_row("profile", f"{prof.id} — {prof.label} ({prof.runtime})")
    if prof.default_model:
        t.add_row("candidate model", f"{prof.default_model} — {prof.note}")
    out.print(t)
    if rep.notes:
        for n in rep.notes:
            err.print(f"[yellow]note:[/yellow] {n}")


def _apply_key(cfg: config.Config, key: str) -> bool:
    """Paste-a-key = fully automatic: provider from prefix, model from
    device + free-first fallback chain, key stored 0600."""
    from ..backends.keydetect import detect_provider, pick_model

    guess = detect_provider(key)
    if guess.provider.startswith("unsupported"):
        err.print(f"[red]key not usable:[/red] {guess.note}")
        return False
    if guess.provider == "unknown":
        out.print("  key format not recognized — pick the provider:")
        pick = typer.prompt("  1=OpenRouter 2=TypeSafe 3=custom URL", default="1").strip()
        if pick == "2":
            guess = detect_provider("ts-")
        elif pick == "3":
            cfg.backend, cfg.backend_label = "remote", "hosted"
            cfg.remote_url = typer.prompt("  Base URL").strip()
            cfg.model = typer.prompt("  Model (empty = server default)", "").strip() or ""
            config.store_api_key(key)
            cfg.api_key_stored = True
            return True
        else:
            guess = detect_provider("sk-or-")
    config.store_api_key(key)
    cfg.api_key_stored = True
    cfg.backend, cfg.backend_label = "remote", "hosted"
    cfg.remote_url = guess.url
    cfg.model = pick_model(guess, low_power=(cfg.profile in ("tier0", "cpu")))
    out.print(f"  [green]auto[/green]: {guess.note} · model: "
              f"[bold]{cfg.model or '(server default)'}[/bold]")
    return True


def _auto_local(cfg: config.Config) -> None:
    """Local = fully automatic: probe running servers, take the first that
    answers, model from its own /v1/models list. No typing."""
    from ..runtime.probe import probe_local_systemone

    found = probe_local_systemone()
    if not found:
        out.print("  [yellow]no local /v1/systemone server running[/yellow]")
        out.print("  start one (pick any):")
        out.print("    uv run --with 'laya[serve]' laya-serve        # smallest, CPU")
        out.print("    uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.8b")
        out.print("  then re-run [bold]" + NAME + " init[/bold] — it will be found "
                  "automatically.")
        out.print("  (Phase 2 will install+launch these for you; today: fallback "
                  "to Tier-0)")
        cfg.backend = "tier0"
        return
    f = found[0]
    cfg.backend, cfg.backend_label = "remote", "local-server"
    cfg.remote_url, cfg.model = f.url, f.model
    extra = f" · models: {', '.join(f.models[:3])}" if f.models else ""
    out.print(f"  [green]auto[/green]: found server {f.url}{extra} · "
              f"model: [bold]{f.model or '(default)'}[/bold]")


def _auto_backend(opts: dict[str, Any], api_key: str | None = None) -> config.Config:
    """The auto wizard (§9.1): ONE prompt, everything else decided."""
    prof = select_profile(hw_detect())
    cfg = config.Config(profile=prof.id)

    out.print("\n[bold]Decision backend[/bold] — paste a key for hosted, "
              "or press Enter for free & local.\n")
    key = api_key
    if key is None and not opts.get("yes"):
        key = typer.prompt("API key (Enter = free & local)", hide_input=True,
                           default="", show_default=False).strip() or None
    if key:
        if not _apply_key(cfg, key):
            # retry once, then fall back to local probe
            key2 = typer.prompt("API key (Enter = free & local)", hide_input=True,
                                default="", show_default=False).strip() or None \
                if not opts.get("yes") else None
            if not key2 or not _apply_key(cfg, key2):
                _auto_local(cfg)
    else:
        if opts.get("yes"):
            _auto_local(cfg)  # non-interactive: probe, else tier0
        else:
            _auto_local(cfg)
    return cfg


def _canary(cfg: config.Config) -> tuple[bool, str]:
    """Live validation; tries the model fallback chain automatically."""
    t0 = time.perf_counter()
    from ..backends.keydetect import provider_by_id
    from ..backends.mock import MockBackend
    from ..backends.remote_systemone import RemoteSystemOne

    if cfg.backend == "mock":
        be = MockBackend()
        try:
            be.system_one(SystemOneRequest(
                state="canary", questions={"ok": {"type": "noul",
                                                  "instructions": "ping"}}))
        except Exception as e:  # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"
        return True, "mock · ready"
    if cfg.backend != "remote":
        return True, "tier-0: no model to validate"

    key = config.get_api_key(cfg)
    candidates: list[str] = []
    if cfg.remote_url == "https://openrouter.ai/api/v1":
        candidates = list(provider_by_id("openrouter").default_models)
    elif cfg.backend_label == "hosted" and cfg.remote_url == "https://api.typesafe.ai":
        candidates = list(provider_by_id("typesafe").default_models)
    if cfg.model and cfg.model not in candidates:
        candidates = [cfg.model] + candidates
    candidates = candidates or [cfg.model]

    last_err = ""
    for model in candidates:
        be = RemoteSystemOne(cfg.remote_url, model, key)
        h = be.health()
        if h.status == "failed":
            return False, h.detail
        try:
            be.system_one(SystemOneRequest(
                state="canary", questions={"ok": {"type": "noul",
                                                  "instructions": "ping"}}))
            cfg.model = model  # winner — free variant first, paid fallback
            paid = "" if ":free" in model else " (paid)"
            ms = int((time.perf_counter() - t0) * 1000)
            return True, f"model {model}{paid} · {ms} ms"
        except Exception as e:  # noqa: BLE001 — try next candidate
            last_err = f"{model}: {type(e).__name__}"
    return False, f"no working model ({last_err})"


@app.command()
def init(
    yes: bool = typer.Option(False, "--yes", help="non-interactive (CI)"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    backend: str | None = typer.Option(None, "--backend",
                                          help="auto (default)|hosted:typesafe|"
                                               "hosted:openrouter|hosted:<url>|"
                                               "local|tier0|mock"),
    remote_url: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
    api_key_env: str | None = typer.Option(None),
    api_key: str | None = typer.Option(None, "--api-key",
                                       help="paste a key → provider+model fully auto"),
    agents: str | None = typer.Option(None, "--agents", help="comma list, or 'all'"),
) -> None:
    """First-run wizard: hardware -> backend -> agents wired -> live check."""
    out.rule(f"[bold]{NAME} init[/bold] · v{__version__}")
    _print_hardware()

    cfg = config.Config.load()
    if backend == "auto" or (backend is None and (api_key or not yes)):
        cfg = _auto_backend({"yes": yes}, api_key=api_key)
    elif backend:
        cfg.profile = select_profile(hw_detect()).id
        if backend.startswith("hosted:"):
            preset = backend.removeprefix("hosted:")
            if preset in HOSTED_PRESETS:
                cfg.remote_url, cfg.model, cfg.api_key_env = HOSTED_PRESETS[preset]
                cfg.backend, cfg.backend_label = "remote", "hosted"
            else:
                cfg.remote_url, cfg.backend, cfg.backend_label = preset, "remote", "hosted"
        elif backend == "local":
            cfg.backend, cfg.backend_label = "remote", "local-server"
            cfg.remote_url = remote_url or "http://127.0.0.1:8009"
            cfg.model = model or "kev-latest"
        else:
            cfg.backend = backend  # tier0 | mock
        if remote_url:
            cfg.remote_url = remote_url
        if model:
            cfg.model = model
        if api_key_env:
            cfg.api_key_env = api_key_env
    else:
        # non-interactive with no backend: probe local, else tier0
        cfg = _auto_backend({"yes": True})

    # ---- agents
    wanted = agents.split(",") if agents and agents != "all" else None
    detected = []
    for iid, integ in ALL_INTEGRATORS.items():
        d = integ.detect()
        if iid == "generic-skill" or d.installed:
            detected.append((iid, integ, d))
    chosen = [x for x in detected if wanted is None or x[0] in wanted]

    t = Table(title="Agents", box=None)
    t.add_column("agent")
    t.add_column("status")
    t.add_column("detail")
    results = []
    for _, integ, _d in chosen:
        if dry_run:
            acts = integ.plan("snapdec")
            t.add_row(integ.display_name, "[blue]planned[/blue]",
                      "; ".join(a.detail for a in acts))
            continue
        r = integ.apply("snapdec")
        results.append((integ, r))
        status = "[green]ok[/green]" if r.ok and not r.manual_snippet else \
            "[yellow]partial[/yellow]"
        t.add_row(integ.display_name, status, r.detail[:120])
        if r.manual_snippet:
            err.print(r.manual_snippet)
        if r.needs_restart:
            err.print(f"[dim]restart {integ.display_name} to load MCP[/dim]")
    out.print(t)
    if dry_run:
        raise typer.Exit(0)

    cfg.agents = [iid for iid, _, _ in chosen]
    cfg.save()

    # ---- daemon + live check
    if cfg.backend in ("mock", "remote"):
        stop_quiet = daemon_status()
        if stop_quiet.get("healthy"):
            stop_daemon()
        ok = start_daemon()
        ok2, detail = (True, "daemon up") if ok else (False, "daemon failed to start")
        if ok:
            try:
                ipc.call_systemone({"state": "canary", "questions": {
                    "ok": {"type": "noul", "instructions": "ping"}}})
            except ConnectionError as e:
                ok2, detail = False, str(e)
        out.print(f"[bold]Daemon:[/bold] {'[ok] ' + detail if ok2 else '[FAIL] ' + detail}")
    else:
        out.print("[bold]Daemon:[/bold] not needed (tier0)")

    ok, detail = _canary(cfg)
    out.print(f"[bold]Live check:[/bold] {'[ok]' if ok else '[FAIL]'} {detail}")
    out.rule("[bold]done[/bold] — agents carry the skill; restart them to load MCP")


# ================================================================ mcp


@app.command()
def mcp() -> None:
    """Run the stdio MCP shim (what agents launch)."""
    from ..mcp.server import main as mcp_main

    mcp_main()


# ================================================================ daemon


@daemon_app.command("start-foreground")
def daemon_fg() -> None:
    raise typer.Exit(run_daemon())


@daemon_app.command()
def start() -> None:
    if start_daemon():
        out.print("[ok] daemon running")
    else:
        err.print("[FAIL] daemon did not become healthy — check `snapdec daemon logs`")
        raise typer.Exit(1)


@daemon_app.command()
def stop() -> None:
    out.print("[ok] stopped" if stop_daemon() else "[FAIL] stop failed")


@daemon_app.command()
def status() -> None:
    st = daemon_status()
    for k, v in st.items():
        out.print(f"{k:>12}: {v}")


@daemon_app.command()
def warm() -> None:
    out.print("[ok] warm" if warm_daemon() else "[FAIL] warm failed")


@daemon_app.command()
def logs() -> None:
    p = config.logs_dir() / "daemon.log"
    if not p.exists():
        err.print("no logs yet")
        return
    text = p.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
    out.print("\n".join(text))


# ================================================================ doctor


@app.command()
def doctor(live: bool = typer.Option(False, "--live"),
           report: bool = typer.Option(False, "--report")) -> None:
    """Diagnose install, daemon, per-agent registration; redacted --report."""
    checks: list[tuple[bool, str]] = []
    cfg = config.Config.load()
    checks.append((config.config_path().exists(), f"config: {config.config_path()}"))
    rep = hw_detect()
    checks.append((True, f"hardware: {rep.oneline()}"))
    checks.append((bool(select_profile(rep).id), f"profile: {select_profile(rep).id}"))
    checks.append((bool(cfg.backend), f"backend: {cfg.backend} "
                  + (f"-> {cfg.remote_url}" if cfg.remote_url else "")))
    st = daemon_status()
    checks.append((st.get("healthy", False),
                   f"daemon: healthy={st.get('healthy')} pid={st.get('pid')}"))
    for iid in cfg.agents:
        integ = ALL_INTEGRATORS.get(iid)
        if integ:
            checks.extend(integ.verify())
    if live:
        t0 = time.perf_counter()
        try:
            ipc.call_systemone({"state": "canary", "questions": {
                "ok": {"type": "noul", "instructions": "ping"}}})
            checks.append((True, f"canary: {int((time.perf_counter()-t0)*1000)} ms"))
        except ConnectionError as e:
            checks.append((False, f"canary failed: {e}"))
    if report:
        redacted = {
            "ok": all(ok for ok, _ in checks),
            "checks": [msg for _, msg in checks],
            "backend": cfg.backend,
            "version": __version__,
            "os": rep.os, "arch": rep.arch,
        }
        out.print_json(json.dumps(redacted))
    else:
        for ok, msg in checks:
            out.print(f"{'[ok]' if ok else '[FAIL]'} {msg}")
    raise typer.Exit(0 if all(ok for ok, _ in checks) else 1)


# ================================================================ agents


@agents_app.command("list")
def agents_list() -> None:
    t = Table(box=None)
    t.add_column("id")
    t.add_column("agent")
    t.add_column("installed")
    t.add_column("evidence")
    for iid, integ in ALL_INTEGRATORS.items():
        d = integ.detect()
        t.add_row(iid, integ.display_name, "yes" if d.installed else "no", d.evidence[:60])
    out.print(t)


@agents_app.command()
def add(agent_id: str) -> None:
    integ = ALL_INTEGRATORS.get(agent_id)
    if not integ:
        err.print(f"unknown agent: {agent_id} (see `snapdec agents list`)")
        raise typer.Exit(2)
    r = integ.apply("snapdec")
    out.print(f"{'[ok]' if r.ok else '[FAIL]'} {r.detail}")
    if r.manual_snippet:
        err.print(r.manual_snippet)
    cfg = config.Config.load()
    if agent_id not in cfg.agents:
        cfg.agents.append(agent_id)
        cfg.save()


@agents_app.command()
def remove(agent_id: str) -> None:
    integ = ALL_INTEGRATORS.get(agent_id)
    if not integ:
        raise typer.Exit(2)
    r = integ.remove()
    out.print(f"{'[ok]' if r.ok else '[FAIL]'} {r.detail}")
    cfg = config.Config.load()
    cfg.agents = [a for a in cfg.agents if a != agent_id]
    cfg.save()


@agents_app.command()
def print_snippet(agent_id: str) -> None:
    """Print the copy-paste MCP snippet for manual setup."""
    integ = ALL_INTEGRATORS.get(agent_id)
    if not integ:
        raise typer.Exit(2)
    import shutil

    exe = shutil.which("snapdec") or "snapdec"
    for a in integ.plan(exe):
        out.print(f"- {a.detail}")
    entry = {"type": "stdio", "command": exe, "args": ["mcp"], "env": {}}
    out.print_json(json.dumps({integ.id: entry}))


# ================================================================ tools CLI


@app.command(name="project-facts")
def project_facts_cmd(path: str = typer.Argument(".")) -> None:
    out.print_json(json.dumps(project_facts(path)))


def _tier1_cli(payload: dict[str, Any]) -> dict[str, Any]:
    if not ipc.ping() and not warm_daemon():
        return failure_envelope("no_backend", "run `snapdec daemon start` or `snapdec init`")
    try:
        raw = ipc.call_systemone(payload)
        if raw.get("error") or raw.get("snapdec_note"):
            return failure_envelope("error", raw.get("error") or raw.get("snapdec_note", ""))
        results = []
        for name, a in (raw.get("answers") or {}).items():
            row = {"id": name}
            if a.get("type") == "noul":
                row["verdict"] = "yes" if a.get("noul") else "no"
            elif a.get("type") == "choice":
                row["label"] = a.get("choice")
            else:
                row["score"] = a.get("score")
            row["probabilities"] = a.get("probabilities") or {}
            results.append(decision_policy.apply_decision(row))
        return make_envelope(results, backend={"name": "daemon", "latency_ms": 0})
    except ConnectionError as e:
        return failure_envelope("no_backend", str(e))


def _load_input(input_path: str | None) -> dict[str, Any]:
    if input_path and input_path != "-":
        return json.loads(open(input_path, encoding="utf-8").read())
    return json.loads(sys.stdin.read())


@app.command()
def classify(input: str | None = typer.Option(None, "--input")) -> None:
    """Input: {"items":[{id,text}],"classes":{label:desc}}"""
    d = _load_input(input)
    qs = {it.get("id", f"i{n}"): {"type": "choice",
                                  "instructions": d.get("instructions", ""),
                                  "criteria": d["classes"]}
          for n, it in enumerate(d.get("items", []))}
    state = "\n".join(str(i.get("text", "")) for i in d.get("items", []))
    out.print_json(json.dumps(_tier1_cli({"state": state, "questions": qs})))


@app.command()
def check(evidence: str | None = typer.Option(None),
          input: str | None = typer.Option(None, "--input")) -> None:
    """Input: {"evidence":str,"checks":{name:question}}"""
    d = _load_input(input)
    ev = d.get("evidence") or evidence or ""
    qs = {k: {"type": "noul", "instructions": v} for k, v in d.get("checks", {}).items()}
    env = _tier1_cli({"state": ev, "questions": qs})
    for r in env.get("results", []):
        if r.get("verdict") in ("yes", "no") and r.get("decision") != "auto":
            r["verdict"] = "uncertain"
    out.print_json(json.dumps(env))


@app.command()
def score(input: str | None = typer.Option(None, "--input")) -> None:
    """Input: {"items":[{id,text}],"levels":[...]}"""
    d = _load_input(input)
    qs = {it.get("id", f"i{n}"): {"type": "score", "criteria": d["levels"]}
          for n, it in enumerate(d.get("items", []))}
    state = "\n".join(str(i.get("text", "")) for i in d.get("items", []))
    out.print_json(json.dumps(_tier1_cli({"state": state, "questions": qs})))


@app.command()
def rank(query: str | None = None, input: str | None = None,
         top_k: int = 10) -> None:
    """Input: {"query":str,"candidates":[{id,text}]}"""
    d = _load_input(input) if input else {"query": query or "", "candidates": []}
    if query and input:
        d["query"] = query
    qs = {c.get("id", f"c{n}"): {"type": "noul",
                                 "instructions": f"Relevant to: {d.get('query','')}"}
          for n, c in enumerate(d.get("candidates", []))}
    state = (d.get("query", "") + "\n" +
             "\n".join(f"[{c.get('id','')}] {c.get('text','')}"
                       for c in d.get("candidates", [])))
    env = _tier1_cli({"state": state, "questions": qs})
    res = sorted(env.get("results", []), key=lambda r: r.get("probability", 0), reverse=True)
    env["results"] = res[:top_k]
    out.print_json(json.dumps(env))


# ================================================================ misc


@app.command(name="backend")
def backend_set(backend: str | None = typer.Option(None),
                remote_url: str | None = typer.Option(None),
                model: str | None = typer.Option(None)) -> None:
    """Change backend without re-registering agents (§9.1 'changing later')."""
    cfg = config.Config.load()
    if backend:
        cfg.backend = backend
    if remote_url:
        cfg.remote_url = remote_url
        cfg.backend = cfg.backend if cfg.backend == "mock" else "remote"
    if model:
        cfg.model = model
    cfg.save()
    if daemon_status().get("healthy"):
        stop_daemon()
        start_daemon()
    out.print(f"backend -> {cfg.backend} {cfg.remote_url} {cfg.model}".strip())


@app.command()
def models() -> None:
    cfg = config.Config.load()
    out.print(f"configured backend: {cfg.backend} model: {cfg.model or '(default)'}")
    out.print("managed local model downloads arrive in Phase 2 (see SYSONE_ARCHITECTURE.md §15)")


@app.command()
def uninstall(purge: bool = typer.Option(False, "--purge-models",
                                         help="also remove SNAPDEC_HOME")) -> None:
    """Reverse every integration exactly; stop the daemon."""
    cfg = config.Config.load()
    for iid in cfg.agents:
        integ = ALL_INTEGRATORS.get(iid)
        if integ:
            r = integ.remove()
            out.print(f"{'[ok]' if r.ok else '[FAIL]'} {iid}: {r.detail}")
    stop_daemon()
    if purge:
        import shutil
        from pathlib import Path

        h = config.home()
        if h.exists():
            shutil.rmtree(h, ignore_errors=True)
        out.print(f"purged {Path(h)}")
    else:
        config.config_path().unlink(missing_ok=True)
    out.print("done")


@app.command()
def version() -> None:
    out.print(f"{NAME} {__version__}")


if __name__ == "__main__":
    app()
