"""snapdec CLI — Typer + Rich (§9).

Commands: init | mcp | daemon | doctor | agents | project-facts |
classify/check/score/rank | bench | models | backend | uninstall | version
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
        out.print("    python -m kev.serve --run jaredpalmer/kev-0.8b --port 8902")
        out.print("  or pick a managed local option in the menu — snapdec downloads")
        out.print("  and launches it for you. Re-run [bold]" + NAME + " init[/bold].")
        cfg.backend = "tier0"
        return
    f = found[0]
    cfg.backend, cfg.backend_label = "remote", "local-server"
    cfg.remote_url, cfg.model = f.url, f.model
    extra = f" · models: {', '.join(f.models[:3])}" if f.models else ""
    out.print(f"  [green]auto[/green]: found server {f.url}{extra} · "
              f"model: [bold]{f.model or '(default)'}[/bold]")


def _select_backend(opts: dict[str, Any], api_key: str | None = None) -> config.Config:
    """The wizard (§9.1): PC spec → catalog with honest stats, hardware-gated
    (only what this machine can run) → user chooses freely → local = auto
    download + auto-setup; hosted = paste key, rest automatic."""
    from ..hardware.catalog import HOSTED_STATS, catalog_for
    from ..runtime.provision import setup_size_note

    rep = hw_detect()
    prof = select_profile(rep)
    cfg = config.Config(profile=prof.id)

    models = catalog_for(rep)
    mapping = {
        "laya-en": ("laya", "english"),
        "laya-multilingual": ("laya", "multilingual"),
        "kev-0.8b": ("kev", "jaredpalmer/kev-0.8b"),
        "kev-4b": ("kev", "jaredpalmer/kev-4b"),
        "kev-9b": ("kev", "jaredpalmer/kev-9b"),
        "kev-27b": ("kev", "jaredpalmer/kev-27b"),
    }

    out.print("\n[bold]Recommended for this machine[/bold] "
              f"({rep.oneline()})\n")
    out.print("  LOCAL — free · private · offline")
    n = 1
    numbers: dict[int, tuple[str, str]] = {}
    for m in models:
        star = "   [bold](recommended)[/bold]" if prof.id in m.recommended_for else ""
        # slow_on_cpu never applies on Apple Silicon — MLX is the fast path there
        slow = "   [yellow]slow on CPU[/yellow]" if m.slow_on_cpu and \
            not rep.apple_silicon and \
            not any(g.vendor == "nvidia" for g in rep.gpus) else ""
        out.print(f"    [{n}] {m.label} ({m.params})  —  {m.di}")
        out.print(f"        {m.latency} · setup: {m.setup}{star}{slow}")
        numbers[n] = (m.key, m.label)
        n += 1
    out.print("  HOSTED — API key · best accuracy")
    for label, stats in HOSTED_STATS:
        out.print(f"    [{n}] {label}  —  {stats}")
        numbers[n] = (f"hosted:{label}", label)
        n += 1
    out.print(f"    [{n}] Other /v1/systemone URL")
    numbers[n] = ("hosted:custom", "custom")
    out.print()

    rec_keys = {mm.key for mm in models if prof.id in mm.recommended_for}
    default = next((str(i) for i, (k, _) in numbers.items() if k in rec_keys), "1")
    choice = typer.prompt("Choice", default=default).strip()
    try:
        key_sel, label = numbers[int(choice)]
    except (KeyError, ValueError):
        cfg.backend = "tier0"
        return cfg

    if key_sel in mapping:
        kind, model = mapping[key_sel]
        ok = True if opts.get("yes") else typer.confirm(
            f"    Local setup downloads {setup_size_note(kind, model)} once. Continue?",
            default=True)
        if not ok:
            cfg.backend = "tier0"
            out.print("  skipped — Tier-0 configured")
            return cfg
        if not opts.get("dry_run"):
            from ..runtime import provision

            ok, detail = provision.provision(
                kind, model, consent=True,
                on_step=lambda m: out.print(f"  [blue]…[/blue] {m}"))
            if not ok:
                out.print(f"  [red]local setup failed:[/red] {detail}")
                out.print("  falling back to Tier-0; fix the issue and re-run init")
                cfg.backend = "tier0"
                return cfg
            if kind == "kev":
                # adopt the wire id the server advertises (may be `kev-latest`)
                am = provision.advertised_model("kev")
                if am:
                    model = am
            out.print(f"  [green]local ready[/green]: {detail}")
        from ..runtime.provision import KEV_PORT, LAYA_PORT

        port = LAYA_PORT if kind == "laya" else KEV_PORT
        cfg.backend, cfg.backend_label = "remote", "local-managed"
        cfg.remote_url = f"http://127.0.0.1:{port}"
        cfg.model, cfg.managed = model, kind
    elif key_sel.startswith("hosted:"):
        if key_sel == "hosted:custom":
            cfg.backend, cfg.backend_label = "remote", "hosted"
            cfg.remote_url = typer.prompt("  Base URL").strip()
            k = api_key or (typer.prompt("  API key (optional)", hide_input=True,
                                         default="", show_default=False).strip()
                            if not opts.get("yes") else "")
            if k:
                config.store_api_key(k)
                cfg.api_key_stored = True
            return cfg
        fake = "sk-or-x" if "OpenRouter" in label else "ts-x"
        from ..backends.keydetect import detect_provider as _dp
        from ..backends.keydetect import pick_model

        guess = _dp(fake)
        key = api_key
        if key is None and not opts.get("yes"):
            key = typer.prompt("  Paste API key", hide_input=True,
                               default="", show_default=False).strip() or None
        if not key:
            out.print("  [red]no key given[/red] — Tier-0 configured; re-run init "
                      "with a key")
            cfg.backend = "tier0"
            return cfg
        config.store_api_key(key)
        cfg.api_key_stored = True
        cfg.backend, cfg.backend_label = "remote", "hosted"
        cfg.remote_url = guess.url
        cfg.model = pick_model(guess)
        out.print(f"  [green]auto[/green]: {guess.note}")
    else:
        cfg.backend = "tier0"
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
    from ..runtime.uvx_guard import guard as _uvx_guard

    _uvx_guard()  # ephemeral-run guard (§5.3): persist + re-exec if uvx-cached
    out.rule(f"[bold]{NAME} init[/bold] · v{__version__}")
    _print_hardware()

    cfg = config.Config.load()
    if backend == "auto" or (backend is None and (api_key or not yes)):
        cfg = _select_backend({"yes": yes}, api_key=api_key)
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
            # non-interactive managed local setup (explicit flag = consent)
            from ..runtime import provision
            from ..runtime.provision import KEV_PORT, LAYA_PORT

            kind = "kev" if model and "kev" in model else "laya"
            m = model or ("jaredpalmer/kev-0.8b" if kind == "kev" else "english")
            if kind == "kev" and "/" not in m:
                m = f"jaredpalmer/{m}"
            port = LAYA_PORT if kind == "laya" else KEV_PORT
            if not dry_run:
                ok, detail = provision.provision(
                    kind, m, consent=True,
                    on_step=lambda msg: out.print(f"  [blue]…[/blue] {msg}"))
                if not ok:
                    err.print(f"[red]local setup failed:[/red] {detail}")
                    raise typer.Exit(1)
                if kind == "kev":
                    am = provision.advertised_model("kev")
                    if am:
                        m = am
                out.print(f"  [green]local ready[/green]: {detail}")
            cfg.backend, cfg.backend_label = "remote", "local-managed"
            cfg.remote_url = f"http://127.0.0.1:{port}"
            cfg.model, cfg.managed, cfg.laya_model = m, kind, m
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
        cfg = _select_backend({"yes": True})

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
    from ..integrations.base import snapdec_cmd

    cmd = snapdec_cmd()
    for _, integ, _d in chosen:
        if dry_run:
            acts = integ.plan(cmd)
            t.add_row(integ.display_name, "[blue]planned[/blue]",
                      "; ".join(a.detail for a in acts))
            continue
        r = integ.apply(cmd)
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
    from ..integrations.base import snapdec_cmd

    r = integ.apply(snapdec_cmd())
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

    from ..integrations.base import mcp_entry, snapdec_cmd

    cmd = snapdec_cmd()
    for a in integ.plan(cmd):
        out.print(f"- {a.detail}")
    entry = mcp_entry(cmd)
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
                p = a.get("noul")
                p_yes = (1.0 if p else 0.0) if isinstance(p, bool) else float(p or 0.0)
                row["verdict"] = "yes" if p_yes > 0.5 else "no"
                row["p_yes"] = round(p_yes, 4)
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


def _tier1_cli_many(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Fan-out (§4.6): per-item states, parallel; mirrors the MCP shim."""
    import concurrent.futures as cf

    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=min(8, len(payloads) or 1)) as ex:
        envs = list(ex.map(_tier1_cli, payloads))
    results = [r for env in envs for r in env.get("results", [])]
    if not results and envs:
        return envs[0]
    return make_envelope(results, backend={"name": "daemon",
                                           "latency_ms": round(
                                               (time.perf_counter()-t0)*1000, 1)})


@app.command()
def classify(input: str | None = typer.Option(None, "--input")) -> None:
    """Input: {"items":[{id,text}],"classes":{label:desc}}"""
    d = _load_input(input)
    instr = d.get("instructions", "") or \
        "Pick the single best-fitting class for the text."
    payloads = [{"state": str(it.get("text", "")),
                 "questions": {"item": {"type": "choice", "instructions": instr,
                                        "criteria": d["classes"]}}}
                for it in d.get("items", [])]
    env = _tier1_cli_many(payloads)
    for it, r in zip(d.get("items", []), env.get("results", []), strict=False):
        r["id"] = it.get("id", r.get("id"))
    out.print_json(json.dumps(env))


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
    payloads = [{"state": str(it.get("text", "")),
                 "questions": {"item": {"type": "score",
                                        "instructions":
                                            "Rate the item on the given scale.",
                                        "criteria": d["levels"]}}}
                for it in d.get("items", [])]
    env = _tier1_cli_many(payloads)
    for it, r in zip(d.get("items", []), env.get("results", []), strict=False):
        r["id"] = it.get("id", r.get("id"))
    out.print_json(json.dumps(env))


@app.command()
def rank(query: str | None = None, input: str | None = None,
         top_k: int = 10) -> None:
    """Input: {"query":str,"candidates":[{id,text}]}"""
    d = _load_input(input) if input else {"query": query or "", "candidates": []}
    if query and input:
        d["query"] = query
    payloads = [{"state": str(c.get("text", "")),
                 "questions": {"item": {"type": "noul",
                                        "instructions":
                                            f"Is this relevant to: "
                                            f"{d.get('query', '')}? Answer yes or no."}}}
                for c in d.get("candidates", [])]
    env = _tier1_cli_many(payloads)
    for c, r in zip(d.get("candidates", []), env.get("results", []), strict=False):
        r["id"] = c.get("id", r.get("id"))
    res = sorted(env.get("results", []), key=lambda r: r.get("probability", 0),
                 reverse=True)
    env["results"] = res[:top_k]
    out.print_json(json.dumps(env))


# ================================================================ bench


@app.command()
def bench(
    json_out: bool = typer.Option(False, "--json"),
    backend: str = typer.Option("active", "--backend", help="active | mock"),
) -> None:
    """Fixed mini-suite (accuracy/Brier/latency) — commits belong in docs/benchmarks/."""
    from ..backends.mock import MockBackend
    from ..bench import run_bench
    from ..runtime.daemon import build_backend

    if backend == "mock":
        be = MockBackend()
    else:
        be = build_backend(config.Config.load())
        if be is None:
            err.print("no model backend configured — run `snapdec init` "
                      "(or use --backend mock)")
            raise typer.Exit(2)
    res = run_bench(be)
    if json_out:
        out.print_json(json.dumps(res))
        return
    out.print(f"suite {res['suite']} · backend {res['backend']['name']} "
              f"({res['backend']['model']}) · {res['items']} items · "
              f"{res['latency_note']}")
    t = Table(box=None)
    t.add_column("metric")
    t.add_column("value")
    for k in ("classify_accuracy", "check_accuracy", "check_brier", "score_exact"):
        t.add_row(k, str(res[k]))
    t.add_row("decision auto/review",
              f"{res['decision_mix']['auto']}/{res['decision_mix']['review']}")
    t.add_row("latency p50/p95 ms",
              f"{res['latency_p50_ms']} / {res['latency_p95_ms']}")
    out.print(t)


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
def models(all: bool = typer.Option(False, "--all",
                                     help="also show models this machine can't run")) -> None:
    """Hardware-gated catalog with honest stats; only what fits is runnable."""
    from ..hardware.catalog import CATALOG, HOSTED_STATS, fits

    rep = hw_detect()
    prof = select_profile(rep)
    t = Table(title=f"Models for this machine ({prof.id} · {prof.label})", box=None)
    t.add_column("")
    t.add_column("model")
    t.add_column("params")
    t.add_column("stats")
    t.add_column("runs here")
    for m in CATALOG:
        ok = fits(m, rep)
        if not ok and not all:
            continue
        star = "(*)" if prof.id in m.recommended_for else ""
        t.add_row(star, m.label, m.params, f"{m.di} · {m.latency}",
                  "yes" if ok else "[dim]no[/dim]")
    out.print(t)
    for label, stats in HOSTED_STATS:
        out.print(f"  hosted · {label}  —  {stats}")
    cfg = config.Config.load()
    out.print(f"\nactive: {cfg.backend_label or cfg.backend} · "
              f"{cfg.model or '(default)'} — run [bold]{NAME} init[/bold] to change")


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
