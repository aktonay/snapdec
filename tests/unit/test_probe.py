from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from snapdec.runtime.probe import _probe_one, probe_local_systemone


class _Stub(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/v1/models":
            body = json.dumps({"models": ["kev-latest", "kev-0.8b"]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):  # quiet
        pass


def _start_stub(port: int = 0) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_probe_finds_systemone_server():
    srv = _start_stub()
    try:
        port = srv.server_address[1]
        found = _probe_one(port, timeout=2.0)
        assert found is not None
        assert found.models == ["kev-latest", "kev-0.8b"]
        assert found.model == "kev-latest"
        assert found.url == f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()


def test_probe_list_uses_extra_ports():
    srv = _start_stub()
    try:
        port = srv.server_address[1]
        found = probe_local_systemone(extra_ports=[port])
        assert any(f.port == port for f in found)
    finally:
        srv.shutdown()


def test_probe_empty_port_returns_none():
    # bind then close → port almost surely closed
    srv = _start_stub()
    port = srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    assert _probe_one(port, timeout=0.3) is None
