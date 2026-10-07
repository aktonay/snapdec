"""Decision 2.0 serve shim — HTTP wrapper around `model.system_one` (ADR-0010).

The `vllm-sr` model repos ship a modeling file (trust_remote_code) but no
HTTP server; this shim is the snapdec-authored server for the family. It
speaks the §4.5 System One wire contract 1:1 — answers pass through
verbatim, so the daemon and RemoteSystemOne need no changes.

Security-critical load order (deviation from §5.4/§10, ADR-0010):
  1. `snapshot_download()` the repo at the pinned revision — the ONLY
     network phase (their loader also verifies MODEL_MANIFEST SHA-256);
  2. set `HF_HUB_OFFLINE=1` BEFORE importing transformers;
  3. `AutoModel.from_pretrained(..., revision=pin, trust_remote_code=True)`
     runs with the hub disabled: pinned cache only, no post-snapshot fetch.

127.0.0.1-only bind, inference-only (system_one, never generates). Run by
provision.launch() with the runtime-venv python; stdout/stderr go to
logs/decision2.log (log_message → stderr, nothing on stdout).

Windows fingerprint compat (ADR-0010 §8): the vendored fingerprint helpers
build `files_sha256` keys with `str(Path.relative_to())`, which emits `\\`
separators on Windows while the published MODEL_MANIFEST.json was hashed on
POSIX. Every per-file digest is still verified by the original function — we
only normalize the key spelling and recompute the composite before the
vendored loader compares it. The patch is active only around
`AutoModel.from_pretrained` and removed afterwards.
"""

from __future__ import annotations

import argparse
import builtins
import contextlib
import functools
import hashlib
import json
import os
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_FINGERPRINT_MODULES = (
    "_vendor.dev2model.infer",
    "_vendor.dev2model.label_token",
    "_vendor.dev2model.dec_model",
)
_FINGERPRINT_ATTRS = ("checkpoint_fingerprint", "label_fingerprint", "dec_fingerprint")


def _canonical(value: Any) -> str:
    """The vendored data.canonical() contract, reimplemented (ADR-0010 §8)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _posix_fingerprint(fn: Any) -> Any:
    """Wrap a vendored fingerprint: verify files, then normalize key spelling.

    The original still reads and hashes every file (tamper detection is
    untouched); only the dict-key separators and the composite over them are
    normalized to the POSIX spelling the published manifest was hashed with.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        identity = fn(*args, **kwargs)
        files = {key.replace("\\", "/"): value
                 for key, value in identity.get("files_sha256", {}).items()}
        composite = hashlib.sha256(_canonical(files).encode("utf-8")).hexdigest()
        return {**identity, "files_sha256": files, "model_sha256": composite}

    wrapper._snapdec_posix = True  # idempotence marker
    return wrapper


def _patch_fingerprint_modules() -> int:
    """Patch fingerprint attrs on any loaded vendored module; return count."""
    patched = 0
    for name, module in list(sys.modules.items()):
        if not name.endswith(_FINGERPRINT_MODULES):
            continue
        for attr in _FINGERPRINT_ATTRS:
            fn = getattr(module, attr, None)
            if callable(fn) and not getattr(fn, "_snapdec_posix", False):
                setattr(module, attr, _posix_fingerprint(fn))
                patched += 1
    return patched


@contextlib.contextmanager
def _fingerprint_compat() -> Iterator[None]:
    """Patch vendored fingerprints to POSIX keys while active (ADR-0010 §8).

    Wraps `builtins.__import__` and rescans `sys.modules` after every import:
    the vendored loader imports its fingerprint helpers at call time inside
    `QwenDecision.load`, so the patch lands between that import and the
    `from ... import checkpoint_fingerprint` attribute fetch. Removed in
    `finally`; inference afterwards runs unpatched.
    """
    original = builtins.__import__

    def auditing_import(name: str, *args: Any, **kwargs: Any) -> Any:
        module = original(name, *args, **kwargs)
        patched = _patch_fingerprint_modules()
        if patched:
            print(f"d2serve: fingerprint compat patched {patched} function(s) "
                  "(Windows path-key fix, ADR-0010 §8)", file=sys.stderr, flush=True)
        return module

    builtins.__import__ = auditing_import
    try:
        yield
    finally:
        builtins.__import__ = original


def _load(repo: str, revision: str) -> Any:
    """Two-phase load: download pinned snapshot, then go offline."""
    import torch

    torch.set_num_threads(min(8, os.cpu_count() or 4))
    from huggingface_hub import snapshot_download

    print(f"d2serve: downloading {repo} @ {revision[:8]} (cached if present)",
          file=sys.stderr, flush=True)
    snapshot_download(repo_id=repo, revision=revision)
    os.environ["HF_HUB_OFFLINE"] = "1"  # BEFORE transformers import (ADR-0010)
    from transformers import AutoModel

    with _fingerprint_compat():  # Windows path-key fix (ADR-0010 §8)
        model = AutoModel.from_pretrained(repo, revision=revision,
                                          trust_remote_code=True)
    return model.eval()


def _coerce_state(payload: dict[str, Any]) -> str:
    state = payload.get("state", "")
    return state if isinstance(state, str) else json.dumps(state)


def make_handler(model: Any, repo: str, lanes: int) -> type[BaseHTTPRequestHandler]:
    gate = threading.Semaphore(lanes)  # torch CPU ops release the GIL

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/systemone":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("content-length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, {"error": "bad json"})
                return
            payload.pop("model", None)  # server-side model, not caller's
            questions = payload.get("questions") or {}
            try:
                with gate:
                    # Decision2Model.system_one is keyword-only (modeling file)
                    out = model.system_one(state=_coerce_state(payload),
                                           questions=questions)
                if not isinstance(out, dict):
                    out = getattr(out, "__dict__", {}) or {}
                self._send(200, {"model": repo, "answers": out.get("answers", {}),
                                 "usage": out.get("usage")})
            except Exception as e:  # noqa: BLE001 — fail closed (NFR-4)
                print(f"d2serve inference error: {type(e).__name__}: {e}",
                      file=sys.stderr, flush=True)
                self._send(200, {"answers": {}, "error": f"{type(e).__name__}: {e}"})

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/health", "/healthz"):
                self._send(200, {"ok": True, "model": repo})
            elif self.path in ("/v1/models", "/models"):
                self._send(200, {"data": [{"id": repo}]})
            else:
                self._send(404, {"error": "not found"})

        def log_message(self, fmt: str, *args: Any) -> None:  # stderr only
            print(fmt % args, file=sys.stderr)

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(prog="d2serve")
    ap.add_argument("--repo", required=True, help="HF repo id, e.g. vllm-sr/Decision-2.0-Eos-0.8B")
    ap.add_argument("--revision", required=True, help="pinned commit SHA (ADR-0010)")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--lanes", type=int, default=2,
                    help="concurrent system_one calls (CPU threads)")
    args = ap.parse_args()

    print(f"d2serve: loading {args.repo} @ {args.revision[:8]} "
          "(first run downloads weights)", file=sys.stderr, flush=True)
    model = _load(args.repo, args.revision)
    # bind AFTER load: health endpoint implies weights resident in RAM
    srv = ThreadingHTTPServer(("127.0.0.1", args.port),
                               make_handler(model, args.repo, args.lanes))
    print(f"d2serve: ready on 127.0.0.1:{args.port}", file=sys.stderr, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
