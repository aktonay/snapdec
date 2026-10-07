"""snapdec daemon — one shared backend for all agents (§4).

Loads the configured backend ONCE and serves the System One wire
contract over the IPC transport. Batching/calibration arrive in Phase 2;
Phase 1 keeps request handling synchronous and fail-closed.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .. import config
from ..backends.base import Backend
from ..backends.mock import MockBackend
from ..backends.remote_systemone import RemoteSystemOne
from ..decisions.envelope import SystemOneRequest, SystemOneResponse
from . import ipc

log = logging.getLogger("snapdec.daemon")


def setup_logging() -> None:
    logs = config.logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(
        logs / "daemon.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)


def build_backend(cfg: config.Config) -> Backend:
    if cfg.backend == "mock":
        return MockBackend()
    if cfg.backend == "remote" and cfg.remote_url:
        return RemoteSystemOne(cfg.remote_url, model=cfg.model,
                               api_key=config.get_api_key(cfg),
                               timeout=cfg.effective_request_timeout())
    # tier0 (or anything unknown): no model. Tools that need a model
    # return fail-closed review envelopes.
    return None  # type: ignore[return-value]


def _handle_systemone(backend: Backend | None,
                      payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if backend is None:
        return 200, {
            "answers": {}, "model": None,
            "snapdec_note": "no model backend configured (tier0) — "
                           "use project_facts or run `snapdec init`",
        }
    try:
        req = SystemOneRequest.model_validate(payload)
        resp: SystemOneResponse = backend.system_one(req)
        return 200, resp.model_dump(exclude_none=True)
    except Exception as e:  # fail-closed: never a 500 toward the shim
        log.exception("system_one failed")
        return 200, {"answers": {}, "error": f"{type(e).__name__}: {e}",
                     "decision": "review", "reason": "error"}


UDS_MAX_PATH = 100  # macOS sun_path is 104 bytes; leave headroom


def _bind_uds(handler: Any) -> Any:
    """UDS server, or None when the path is too long / bind fails.

    macOS temp-dir paths (CI runners, pytest tmp) can exceed the 104-byte
    sun_path limit — in that case the caller falls back to loopback TCP,
    same transport Windows uses (ADR-0004).
    """
    if len(str(ipc._uds_path())) > UDS_MAX_PATH:
        log.info("uds path too long (> %d chars) — using loopback tcp", UDS_MAX_PATH)
        return None
    try:
        import socket

        class UDSHTTPServer(ThreadingHTTPServer):
            address_family = socket.AF_UNIX

            def server_bind(self) -> None:  # bind UDS path, skip host/port parsing
                ipc._uds_path().unlink(missing_ok=True)
                self.socket.bind(str(ipc._uds_path()))
                self.server_name = "snapdec"
                self.server_port = 0

        return UDSHTTPServer(None, handler)  # type: ignore[arg-type]
    except (OSError, AttributeError) as e:  # AttributeError: no AF_UNIX (win32)
        log.info("uds bind failed (%s) — using loopback tcp", e)
        return None


def _bind_tcp(handler: Any, port: int | None) -> tuple[Any, int | None]:
    """Loopback TCP with port fallback (concurrent dev instances).

    HTTPServer.server_bind calls socket.getfqdn(host) — reverse DNS that can
    hang for minutes on hosts with no resolver answer (macOS CI runners),
    leaving the daemon bound-but-stuck with no error. We bind the socket
    directly and skip the fqdn lookup: we serve on a literal IP.
    """
    import socketserver

    class LoopbackHTTPServer(ThreadingHTTPServer):
        def server_bind(self) -> None:
            socketserver.TCPServer.server_bind(self)
            self.server_name = "127.0.0.1"          # skip getfqdn (DNS hang)
            self.server_port = self.server_address[1]

    for cand in [port or ipc.DEFAULT_PORT] + \
            [(ipc.DEFAULT_PORT + i) for i in range(1, 11)]:
        if cand != (port or ipc.DEFAULT_PORT) and not ipc.check_port_free(cand):
            continue
        try:
            return LoopbackHTTPServer(("127.0.0.1", cand), handler), cand
        except OSError:
            continue
    return None, None


def run_daemon(port: int | None = None) -> int:
    """Run the daemon in the foreground. Returns exit code."""
    setup_logging()
    from filelock import FileLock

    config.state_dir().mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(config.state_dir() / "daemon.lock"), timeout=1)
    try:
        lock.acquire()
    except Exception:
        print("snapdec daemon already running (lock held)", file=sys.stderr)
        return 1

    cfg = config.Config.load()
    backend = build_backend(cfg)
    if backend is not None:
        backend.load()

    token = ipc.new_token()
    import os

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            st = ipc.read_state() or {}
            want = f"Bearer {st.get('token', '')}"
            got = self.headers.get("authorization", "")
            if want == "Bearer " or want == got:
                return True  # no token yet (fresh state) or match
            return False

        def do_POST(self):  # noqa: N802
            if self.path == "/shutdown":
                # unauthenticated by design: loopback-only bind is the boundary;
                # requiring the token here deadlocks stale-daemon replacement
                self._send(200, {"ok": True})
                import threading

                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if not self._authed():
                self._send(401, {"error": "bad token"})
                return
            if self.path != "/v1/systemone":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("content-length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send(400, {"error": "bad json"})
                return
            code, obj = _handle_systemone(backend, payload)
            self._send(code, obj)

        def do_GET(self):  # noqa: N802 (http.server API)
            if self.path == "/healthz":
                h = backend.health() if backend else None
                self._send(200, {"ok": True, "backend": cfg.backend,
                                 "health": h.__dict__ if h else None})
            elif self.path == "/v1/models":
                if backend and hasattr(backend, "health"):
                    self._send(200, {"models": [cfg.model or "default"]})
                else:
                    self._send(200, {"models": []})
            else:
                self._send(404, {"error": "not found"})

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet stderr
            log.info("%s", fmt % args)

    # transport: UDS when usable, else loopback TCP with port fallback
    srv = _bind_uds(Handler) if ipc.use_uds() else None
    if srv is not None:
        ipc.write_state(pid=os.getpid(), port=None, token=token, transport="uds")
        log.info("daemon up: backend=%s transport=uds", cfg.backend)
    else:
        srv, use_port = _bind_tcp(Handler, port)
        if srv is None:
            print("no usable transport for daemon (uds unavailable, no free port)",
                  file=sys.stderr)
            lock.release()
            return 1
        ipc.write_state(pid=os.getpid(), port=use_port, token=token, transport="tcp")
        log.info("daemon up: backend=%s transport=tcp:%s", cfg.backend, use_port)

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if backend is not None:
            backend.close()
        ipc.clear_state()
        lock.release()
        log.info("daemon down")
    return 0
