"""Managed local backends: auto-download + auto-setup (the 'local' choice).

Supports two families, chosen freely by the user (stats shown in init):
- Laya (`laya[serve]` from PyPI, port 8901) — tiny encoder, fast, weak
  zero-shot (specialize-first).
- Kev (pinned git tarball — NOT on PyPI — port 8902) — best local zero-shot
  Decision Index (0.8B/4B/9B/27B since Kev 1.0); fast on CUDA and on Apple
  Silicon via MLX, seconds/question elsewhere on CPU.

Both are bound to 127.0.0.1 only (laya's upstream default 0.0.0.0 is
refused), weights auto-download from Hugging Face on first preload
(§5.4 consent handled by the wizard).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from .. import config

LAYA_PORT = 8901
KEV_PORT = 8902
KEV_PIN_SHA = "fe64b1274ea7f80d4095866df90666abb03e9cf6"  # jaredpalmer/kev 1.0, 2026-10-03
KEV_TARBALL = f"https://github.com/jaredpalmer/kev/archive/{KEV_PIN_SHA}.tar.gz"


def runtime_dir() -> Path:
    return config.home() / "runtime"


def _venv_bin(name: str) -> Path:
    sub = "Scripts" if sys.platform == "win32" else "bin"
    ext = ".exe" if sys.platform == "win32" else ""
    return runtime_dir() / "venv" / sub / f"{name}{ext}"


def venv_python() -> Path:
    return _venv_bin("python")


def _uv() -> str | None:
    return shutil.which("uv")


KEV_SETUP_SIZES = {
    "jaredpalmer/kev-0.8b": "about 5 GB (torch + transformers + Kev-0.8B weights)",
    "jaredpalmer/kev-4b": "about 12 GB (weights + torch)",
    "jaredpalmer/kev-9b": "about 22 GB (weights + torch)",
    "jaredpalmer/kev-27b": "about 60 GB+ (weights dominate)",
}


def setup_size_note(kind: str, model: str = "") -> str:
    if kind == "laya":
        return "about 2 GB (torch + transformers + Laya weights)"
    return KEV_SETUP_SIZES.get(model, KEV_SETUP_SIZES["jaredpalmer/kev-0.8b"])


def ensure_venv() -> Path:
    py = venv_python()
    if py.exists():
        return py
    runtime_dir().mkdir(parents=True, exist_ok=True)
    uv = _uv()
    cmd = [uv, "venv", "--python", "3.12", str(runtime_dir() / "venv")] if uv else \
        [sys.executable, "-m", "venv", str(runtime_dir() / "venv")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"venv creation failed: {r.stderr[:300]}")
    return py


def _pip_install(py: Path, *specs: str) -> None:
    uv = _uv()
    cmd = [uv, "pip", "install", "--python", str(py), *specs] if uv else \
        [str(py), "-m", "pip", "install", *specs]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f"install failed ({specs[0]}): {(r.stderr or r.stdout)[-500:]}")


def _python_ok_for_kev(py: Path) -> bool:
    """kev 1.0 requires Python 3.12/3.13 in the runtime venv."""
    q = subprocess.run([str(py), "-c", "import sys;print(sys.version_info[:2])"],
                       capture_output=True, text=True, timeout=60)
    return q.stdout.strip() in ("(3, 12)", "(3, 13)")


def install_backend(py: Path, kind: str) -> str:
    if kind == "laya":
        _pip_install(py, "laya[serve]")
        q = subprocess.run([str(py), "-c", "import laya;print(laya.__version__)"],
                           capture_output=True, text=True, timeout=60)
        return q.stdout.strip() or "unknown"
    if kind == "kev":
        if not _python_ok_for_kev(py):
            raise RuntimeError(
                "kev 1.0 needs Python 3.12/3.13 in the runtime venv — install "
                "uv (https://astral.sh/uv) and re-run `snapdec init` so the "
                "venv can be created with 3.12")
        # [serve] brings fastapi/uvicorn/typesafe-sdk (+ mlx-lm on Apple Silicon)
        _pip_install(py, f"kev[serve] @ {KEV_TARBALL}")
        q = subprocess.run([str(py), "-c", "import kev;print(getattr(kev,'__version__','git'))"],
                           capture_output=True, text=True, timeout=60)
        return f"{q.stdout.strip() or 'git'}@{KEV_PIN_SHA[:8]}"
    raise ValueError(f"unknown backend kind: {kind}")


def _port(kind: str) -> int:
    return LAYA_PORT if kind == "laya" else KEV_PORT


def _env(kind: str, model: str) -> dict[str, str]:
    env = dict(os.environ)
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    if kind == "laya":
        env.update({
            "LAYA_HOST": "127.0.0.1",      # upstream default 0.0.0.0 — never
            "LAYA_PORT": str(LAYA_PORT),
            "LAYA_PRELOAD": "1",           # download + build checkpoints now
            "LAYA_MODELS": model,          # english | multilingual
            "LAYA_DEFAULT_MODEL": model,
            "LAYA_THREADS": str(max(2, (os.cpu_count() or 4) // 2)),
        })
    return env


def _launch_cmd(kind: str, model: str) -> list[str]:
    py = venv_python()
    if kind == "laya":
        serve = _venv_bin("laya-serve")
        return [str(serve)] if serve.exists() else [str(py), "-m", "laya.serve"]
    hf_repo = model if "/" in model else f"jaredpalmer/{model}"
    return [str(py), "-m", "kev.serve", "--run", hf_repo, "--port", str(KEV_PORT)]


def _pid_file(kind: str) -> Path:
    return config.state_dir() / f"{kind}.pid"


def _pid(kind: str) -> int | None:
    f = _pid_file(kind)
    if f.exists():
        try:
            return int(f.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return None


def _healthy(kind: str, timeout: float = 1.5) -> bool:
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"http://127.0.0.1:{_port(kind)}/health")
            if r.status_code == 404:
                r = c.get(f"http://127.0.0.1:{_port(kind)}/healthz")
            return r.status_code == 200
    except httpx.HTTPError:
        return False


def launch(kind: str, model: str) -> int:
    """Start the managed server detached; return PID."""
    if _healthy(kind):
        return _pid(kind) or 0
    logs = config.logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    logf = open(logs / f"{kind}.log", "ab")
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True
    try:
        p = subprocess.Popen(_launch_cmd(kind, model), stdout=logf, stderr=logf,
                             stdin=subprocess.DEVNULL, env=_env(kind, model), **kwargs)
    finally:
        logf.close()
    config.state_dir().mkdir(parents=True, exist_ok=True)
    _pid_file(kind).write_text(str(p.pid), encoding="utf-8")
    return p.pid


def stop(kind: str) -> bool:
    pid = _pid(kind)
    if pid:
        try:
            import psutil

            psutil.Process(pid).terminate()
        except psutil.Error:
            pass
    _pid_file(kind).unlink(missing_ok=True)
    return True


def wait_healthy(kind: str, timeout: float = 600.0,
                 on_wait: Callable[[float], None] | None = None) -> bool:
    """Poll until healthy; first run includes the HF weights download."""
    deadline = time.monotonic() + timeout
    waited = 0.0
    while time.monotonic() < deadline:
        if _healthy(kind):
            return True
        time.sleep(2.0)
        waited += 2.0
        if on_wait and waited % 10 == 0:
            on_wait(waited)
    return False


def advertised_model(kind: str) -> str:
    """First model id the managed server advertises ('' if unreachable).

    kev.serve may advertise a wire id like `kev-latest` rather than the HF
    repo id we passed to --run; adopting the advertised id avoids guessing
    what the /v1/systemone `model` field should be (§4.5).
    """
    for path in ("/v1/models", "/models"):
        try:
            with httpx.Client(timeout=2.0) as c:
                r = c.get(f"http://127.0.0.1:{_port(kind)}{path}")
            if r.status_code == 200:
                data = r.json()
                ids = [m.get("id") for m in data.get("data", data.get("models", []))]
                ids = [i for i in ids if i]
                if ids:
                    return str(ids[0])
        except (httpx.HTTPError, ValueError):
            continue
    return ""


def provision(kind: str, model: str, *, consent: bool = False,
              on_step: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """Full auto-setup for a 'local' choice. Returns (ok, detail)."""
    step = on_step or (lambda m: None)
    try:
        step("creating runtime venv")
        py = ensure_venv()
        if not consent:
            return False, "consent required for large download"
        step(f"installing {kind} into the runtime venv")
        version = install_backend(py, kind)
        step(f"{kind} {version} installed — launching (weights download on first run)")
        launch(kind, model)
        step("waiting for server (first run downloads model weights)")
        if not wait_healthy(kind, on_wait=lambda s: step(f"still downloading/warming ({int(s)}s)")):
            return False, (f"{kind} server did not become healthy in 10 min — "
                           f"see {config.logs_dir() / (kind + '.log')}")
        return True, f"{kind} {version} @ 127.0.0.1:{_port(kind)}"
    except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as e:
        return False, str(e)


def ensure_running(cfg: config.Config) -> bool:
    """Called by daemon start: resurrect the managed backend if it died."""
    if cfg.backend_label != "local-managed":
        return True
    kind = cfg.managed or "laya"
    if _healthy(kind):
        return True
    if not venv_python().exists():
        return False
    launch(kind, cfg.model or "english")
    return wait_healthy(kind, timeout=120.0)
