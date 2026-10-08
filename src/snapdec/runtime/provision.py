"""Managed local backends: auto-download + auto-setup (the 'local' choice).

Supports four families, chosen freely by the user (stats shown in init):
- Laya (`laya[serve]` from PyPI, port 8901) — tiny encoder, fast, weak
  zero-shot (specialize-first).
- Kev (pinned git tarball — NOT on PyPI — port 8902) — best local zero-shot
  Decision Index (0.8B/4B/9B/27B since Kev 1.0); fast on CUDA and on Apple
  Silicon via MLX, seconds/question elsewhere on CPU.
- Decision 2.0 (HF org `vllm-sr`, Apache-2.0, port 8903) — single-pass
  decision models (Kai/Eos/Sol/Nox); the repos ship no HTTP server, so we
  serve them with our own shim `d2serve.py` under trust_remote_code with
  per-repo pinned revisions (ADR-0010).
- imajev (GitHub `mohit67890/imajev`, Apache-2.0, port 8904) — typed Jev
  decisions on Qwen3.5 bases (2B/4B/9B; image-capable, snapdec uses the
  text-only path). They SHIP a server, so we run their pinned playground
  server with per-repo pinned adapter revisions — no shim, no
  trust_remote_code (ADR-0011).

All are bound to 127.0.0.1 only (laya's upstream default 0.0.0.0 is
refused), weights auto-download from Hugging Face on first preload
(§5.4 consent handled by the wizard).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from .. import config

LAYA_PORT = 8901
KEV_PORT = 8902
DECISION2_PORT = 8903
IMAJEV_PORT = 8904
KEV_PIN_SHA = "fe64b1274ea7f80d4095866df90666abb03e9cf6"  # jaredpalmer/kev 1.0, 2026-10-03
KEV_TARBALL = f"https://github.com/jaredpalmer/kev/archive/{KEV_PIN_SHA}.tar.gz"

# Decision 2.0 (HF org vllm-sr, Apache-2.0): repo id → pinned revision
# (per-repo commit SHA, resolved via the HF API 2026-10-06 — ADR-0010).
D2_REPOS = {
    "vllm-sr/Decision-2.0-Kai-0.6B": "cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764",
    "vllm-sr/Decision-2.0-Eos-0.8B": "3594047d69f476f1d01cf84c593e213fc3a4dfe0",
    "vllm-sr/Decision-2.0-Sol-2B": "64235bef55dad29387dd16da7c90e038bf2f0972",
    "vllm-sr/Decision-2.0-Nox-4B": "25e8f67d1b486c647222df3aac640d2d5d736bbe",
}
# Same shared runtime venv as laya/kev (laya[serve] already pulled
# transformers/torch/safetensors) — pinned, idempotent install (§0.3).
D2_INSTALL_SPECS = ("transformers==5.18.0", "torch==2.14.1", "safetensors==0.8.0")
D2_SETUP_SIZES = {
    "vllm-sr/Decision-2.0-Kai-0.6B": "about 2 GB (weights ~1.5 GB + torch)",
    "vllm-sr/Decision-2.0-Eos-0.8B": "about 3 GB (weights ~2 GB + torch)",
    "vllm-sr/Decision-2.0-Sol-2B": "about 6 GB (weights ~4.8 GB + torch)",
    "vllm-sr/Decision-2.0-Nox-4B": "about 11 GB (weights ~9.7 GB + torch)",
}

# imajev (GitHub mohit67890/imajev, Apache-2.0 — ADR-0011): pinned repo
# tarball + adapter repo pins (resolved via the HF API 2026-10-07).
IMAJEV_PIN_SHA = "ccf586d43d2a580319b6535c893668904d909eb9"  # mohit67890/imajev, 2026-10-07
IMAJEV_TARBALL = f"https://github.com/mohit67890/imajev/archive/{IMAJEV_PIN_SHA}.tar.gz"
IMAJEV_REPOS = {
    "mohit67890/imajev-2b": "0426f7b1c73804b64fab5802e04f401420ec774c",
    "mohit67890/imajev-4b": "f8d8234cebc6c99065c07731e59716dc0a6e27ab",
    "mohit67890/imajev-9b": "9a69dd0f0d99d465638a9f872ef29ce37c21e888",
}
# size key → (base repo, pinned base revision, bundle path inside the repo) —
# mirrors their scripts/download_model.py PINNED dict at IMAJEV_PIN_SHA
# (verified 2026-10-07; bundle json is written relative to the repo root).
IMAJEV_BASE_PINS = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc", "artifacts/model.json"),
    "4b": ("Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
           "artifacts/model-qwen4b.json"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
           "artifacts/model-qwen9b.json"),
}
# Exact pins resolved via `uv pip install --dry-run` + `uv pip list` against
# the runtime venv 2026-10-07 — zero upgrades to existing pins (§0.3). Full
# server closure, not just the deltas: on a fresh venv (imajev provisioned
# before laya) peft would otherwise pull an UNPINNED torch, and their server
# imports fastapi/uvicorn/pydantic — plus PIL via `vision_decision.images`,
# which crashed the first real launch (ADR-0011 §1). mlx-vlm (Apple only)
# is appended at install time — upstream's own pin.
IMAJEV_INSTALL_SPECS = (
    "transformers==5.18.0", "torch==2.14.1", "safetensors==0.8.0",
    "peft==0.21.2", "accelerate==1.15.0", "huggingface-hub==1.33.0",
    "fastapi==0.142.2", "uvicorn==0.54.0", "python-multipart==0.0.32",
    "pydantic==2.13.5", "pillow==12.3.0",
)
IMAJEV_SETUP_SIZES = {
    "mohit67890/imajev-2b": "about 5 GB (Qwen3.5-2B base + adapter + torch)",
    "mohit67890/imajev-4b": "about 10 GB (weights + torch)",
    "mohit67890/imajev-9b": "about 19 GB (weights + torch)",
}


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
    if kind == "decision2":
        return D2_SETUP_SIZES.get(model, D2_SETUP_SIZES["vllm-sr/Decision-2.0-Eos-0.8B"])
    if kind == "imajev":
        return IMAJEV_SETUP_SIZES.get(model, IMAJEV_SETUP_SIZES["mohit67890/imajev-2b"])
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


def _run_live(cmd: list[str], *, env: dict[str, str] | None = None,
              cwd: str | None = None, timeout: int = 3600
              ) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with stderr shown LIVE in the console.

    Multi-GB downloads (uv wheel fetches, `snapshot_download` tqdm bars)
    report progress + speed on stderr; capturing it hides up to an hour of
    work on a slow link (owner request 2026-10-07). stdout is captured for
    error tails; stderr is inherited, so the user always sees it live.
    """
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=None,
                          text=True, env=env, cwd=cwd, timeout=timeout)


def _pip_install(py: Path, *specs: str) -> None:
    uv = _uv()
    cmd = [uv, "pip", "install", "--python", str(py), *specs] if uv else \
        [str(py), "-m", "pip", "install", *specs]
    r = _run_live(cmd)
    if r.returncode != 0:
        # stderr went live to the console; stdout tail is for the error path
        raise RuntimeError(f"install failed ({specs[0]}): {(r.stdout or '')[-500:]}")


def _python_ok_for_kev(py: Path) -> bool:
    """kev 1.0 requires Python 3.12/3.13 in the runtime venv."""
    q = subprocess.run([str(py), "-c", "import sys;print(sys.version_info[:2])"],
                       capture_output=True, text=True, timeout=60)
    return q.stdout.strip() in ("(3, 12)", "(3, 13)")


def _materialize_d2serve() -> Path:
    """Copy the serve shim into SNAPDEC_HOME/runtime (idempotent).

    `ensure_running` relaunches via `_launch_cmd` without reinstalling, so
    the shim must exist outside the package directory too."""
    dst = runtime_dir() / "d2serve.py"
    src = Path(__file__).with_name("d2serve.py")
    text = src.read_text(encoding="utf-8")
    if not dst.exists() or dst.read_text(encoding="utf-8") != text:
        runtime_dir().mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
    return dst


def _imajev_size(model: str) -> str:
    """`mohit67890/imajev-2b` → `2b` (their download_model.py size key)."""
    return model.rsplit("-", 1)[-1].lower()


def _imajev_dir() -> Path:
    return runtime_dir() / "imajev" / IMAJEV_PIN_SHA[:8]


def _imajev_adapter_dir(model: str) -> Path:
    return runtime_dir() / "imajev-adapter" / _imajev_size(model)


def _install_imajev(py: Path) -> str:
    """Extract the pinned repo tarball into runtime/imajev/<sha8> (idempotent).

    Untrusted-archive discipline: fresh directory per pin, tar data filter,
    `.snapdec-ok` marker only after a successful extract. The marker gates the
    extract only — deps always `_pip_install` (idempotent no-op when the venv
    satisfies them) because the spec list can grow across releases (pillow
    joined after the first launch crashed on a missing PIL, ADR-0011). Their
    server manages its own sys.path from __file__, so launches need no
    PYTHONPATH.
    """
    root = _imajev_dir()
    if not (root / ".snapdec-ok").exists():
        root.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=120.0, follow_redirects=True) as c:
            r = c.get(IMAJEV_TARBALL)
            r.raise_for_status()
        prefix = f"imajev-{IMAJEV_PIN_SHA}/"  # GitHub archive leading component
        with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name.startswith(prefix)]
            for m in members:
                m.name = m.name[len(prefix):]
            tar.extractall(root, members=members, filter="data")
        (root / ".snapdec-ok").write_text(IMAJEV_PIN_SHA, encoding="utf-8")
    specs = list(IMAJEV_INSTALL_SPECS)
    if sys.platform == "darwin":
        specs.append("mlx-vlm==0.7.1")  # upstream's own Apple pin
    _pip_install(py, *specs)
    return f"imajev-{IMAJEV_PIN_SHA[:8]}"


def _bundle_ready(bundle: Path) -> bool:
    """True when the bundle json records an existing snapshot dir.

    Their tarball SHIPS a placeholder bundle (relative
    `.cache/huggingface/...` path + a "note" key) — a plain `.exists()`
    check skips the base download entirely and the server dies on "Local
    model snapshot is missing" (found at first provision, ADR-0011 §3).
    Their script overwrites the placeholder with the real absolute
    snapshot path, which `is_dir()`-checks true.
    """
    try:
        data = json.loads(bundle.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    raw = str(data.get("path", ""))
    if not raw:
        return False
    snap = Path(raw)
    if not snap.is_absolute():
        snap = _imajev_dir() / snap  # placeholder is repo-root-relative
    return snap.is_dir()


def _ensure_imajev_model(py: Path, model: str) -> None:
    """Download the pinned base bundle + adapter repo (idempotent, per model).

    Base: their `scripts/download_model.py` (size-key argv; writes the bundle
    json relative to the repo root → cwd=root; its HF_HOME setdefault loses to
    our absolute env). Adapter: `huggingface_hub.snapshot_download` into a
    stable local_dir. Both run with `-I` so nothing is imported from the
    extracted tree or the cwd, and via `_run_live` — multi-GB tqdm progress
    (bytes + speed) stays visible on slow links.
    """
    size = _imajev_size(model)
    root = _imajev_dir()
    bundle = root / IMAJEV_BASE_PINS[size][2]
    adapter = _imajev_adapter_dir(model)
    if _bundle_ready(bundle) and adapter.exists():
        return
    hf_home = runtime_dir() / "imajev-hf"
    hf_home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HF_HOME": str(hf_home), "HF_HUB_DISABLE_TELEMETRY": "1"}
    if not _bundle_ready(bundle):
        r = _run_live(
            [str(py), "-I", str(root / "scripts" / "download_model.py"), "--model", size],
            env=env, cwd=str(root), timeout=7200)
        if r.returncode != 0 or not _bundle_ready(bundle):
            raise RuntimeError(f"imajev base download failed: {(r.stdout or '')[-500:]}")
    if not adapter.exists():
        code = ("import sys;from huggingface_hub import snapshot_download;"
                "snapshot_download(sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3])")
        r = _run_live([str(py), "-I", "-c", code, model, IMAJEV_REPOS[model], str(adapter)],
                      env=env, timeout=3600)
        if r.returncode != 0:
            raise RuntimeError(f"imajev adapter download failed: {(r.stdout or '')[-500:]}")


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
    if kind == "decision2":
        script = _materialize_d2serve()
        # idempotent: the shared venv already satisfies these pins (laya[serve])
        _pip_install(py, *D2_INSTALL_SPECS)
        q = subprocess.run([str(py), "-c", "import transformers;print(transformers.__version__)"],
                           capture_output=True, text=True, timeout=60)
        return f"transformers {q.stdout.strip() or 'unknown'} · {script.name}"
    if kind == "imajev":
        return _install_imajev(py)
    raise ValueError(f"unknown backend kind: {kind}")


def port_for(kind: str) -> int:
    """Managed-server port per kind (public — CLI wizard uses it too)."""
    ports = {"laya": LAYA_PORT, "kev": KEV_PORT, "decision2": DECISION2_PORT,
             "imajev": IMAJEV_PORT}
    if kind not in ports:
        raise ValueError(f"unknown backend kind: {kind}")
    return ports[kind]


def _default_model(kind: str) -> str:
    defaults = {
        "laya": "english",
        "kev": "jaredpalmer/kev-0.8b",
        "decision2": "vllm-sr/Decision-2.0-Eos-0.8B",
        "imajev": "mohit67890/imajev-2b",
    }
    return defaults.get(kind, "english")


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
    if kind == "imajev":
        # weights are fully local after provisioning (bundle json records an
        # absolute snapshot path); offline keeps any incidental lookups local.
        # Their server self-manages sys.path from __file__ — no PYTHONPATH.
        env["HF_HUB_OFFLINE"] = "1"
    return env


def _launch_cmd(kind: str, model: str) -> list[str]:
    py = venv_python()
    if kind == "laya":
        serve = _venv_bin("laya-serve")
        return [str(serve)] if serve.exists() else [str(py), "-m", "laya.serve"]
    if kind == "decision2":
        script = _materialize_d2serve()  # self-heal on the ensure_running path
        return [str(py), str(script), "--repo", model,
                "--revision", D2_REPOS[model], "--port", str(DECISION2_PORT)]
    if kind == "imajev":
        # their pinned playground server (ADR-0011): official benchmark flags —
        # rotations 1, eager LoRA, calibration from the adapter repo. Defaults
        # of --backend auto would look inside their repo tree, so pass explicit
        # absolute paths for everything.
        size = _imajev_size(model)
        adapter = _imajev_adapter_dir(model)
        if sys.platform == "darwin":  # real MLX fast path (mlx/ subdir)
            backend, adapter_arg = "mlx", adapter / "mlx"
        else:
            backend, adapter_arg = "torch", adapter
        return [str(py), str(_imajev_dir() / "scripts" / "playground" / "server.py"),
                "--backend", backend, "--adapter", str(adapter_arg),
                "--model-bundle", str(_imajev_dir() / IMAJEV_BASE_PINS[size][2]),
                "--calibration", str(adapter / "calibration.json"),
                "--rotations", "1", "--model-name", model,
                "--host", "127.0.0.1", "--port", str(IMAJEV_PORT)]
    hf_repo = model if "/" in model else f"jaredpalmer/{model}"
    return [str(py), "-m", "kev.serve", "--run", hf_repo, "--port", str(port_for("kev"))]


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
            base = f"http://127.0.0.1:{port_for(kind)}"
            r = c.get(f"{base}/health")
            if r.status_code == 404:
                r = c.get(f"{base}/healthz")
            if r.status_code == 404 and kind == "imajev":
                # their playground server has no /health; uvicorn binds the port
                # only after build_backend, and /v1/models says "loaded" — check
                # it anyway as belt-and-braces.
                r = c.get(f"{base}/v1/models")
                return r.status_code == 200 and r.json().get("loaded") is True
            return r.status_code == 200
    except (httpx.HTTPError, ValueError):
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
                             stdin=subprocess.DEVNULL, env=_env(kind, model),
                             cwd=str(_imajev_dir()) if kind == "imajev" else None,
                             **kwargs)
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
                r = c.get(f"http://127.0.0.1:{port_for(kind)}{path}")
            if r.status_code == 200:
                data = r.json()
                ids = [m.get("id") for m in data.get("data", data.get("models", []))]
                ids = [i for i in ids if i]
                if ids:
                    return str(ids[0])
                if data.get("model"):  # imajev: flat body, not a list
                    return str(data["model"])
        except (httpx.HTTPError, ValueError):
            continue
    return ""


def provision(kind: str, model: str, *, consent: bool = False,
              on_step: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """Full auto-setup for a 'local' choice. Returns (ok, detail)."""
    step = on_step or (lambda m: None)
    if kind == "decision2" and model not in D2_REPOS:
        return False, (f"unknown Decision 2.0 model: {model} "
                       f"(known: {', '.join(sorted(D2_REPOS))})")
    if kind == "imajev" and model not in IMAJEV_REPOS:
        return False, (f"unknown imajev model: {model} "
                       f"(known: {', '.join(sorted(IMAJEV_REPOS))})")
    try:
        step("creating runtime venv")
        py = ensure_venv()
        if not consent:
            return False, "consent required for large download"
        step(f"installing {kind} into the runtime venv")
        version = install_backend(py, kind)
        if kind == "imajev":
            step(f"downloading {model} weights (Qwen3.5 base + adapter)")
            _ensure_imajev_model(py, model)
        step(f"{kind} {version} installed — launching (weights download on first run)")
        launch(kind, model)
        step("waiting for server (first run downloads model weights)")
        if not wait_healthy(kind, on_wait=lambda s: step(f"still downloading/warming ({int(s)}s)")):
            return False, (f"{kind} server did not become healthy in 10 min — "
                           f"see {config.logs_dir() / (kind + '.log')}")
        return True, f"{kind} {version} @ 127.0.0.1:{port_for(kind)}"
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
    launch(kind, cfg.model or _default_model(kind))
    # imajev FP32 cold load (~11 GB resident) can exceed 120 s by a wide
    # margin — give it the same 10-min window `provision()` uses; laya/kev/
    # d2 keep the fast window (found at first real resurrect, ADR-0011).
    timeout = 600.0 if kind != "laya" else 120.0
    ok = wait_healthy(kind, timeout=timeout,
                      on_wait=lambda s: print(f"snapdec: {kind} warming ({int(s)}s)",
                                              file=sys.stderr, flush=True))
    if not ok:
        print(f"snapdec: {kind} did not become healthy — "
              f"see {config.logs_dir() / (kind + '.log')}",
              file=sys.stderr, flush=True)
    return ok
