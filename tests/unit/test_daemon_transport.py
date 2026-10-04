from __future__ import annotations

from pathlib import Path

from snapdec.runtime import daemon, ipc


def test_uds_skipped_when_path_too_long(monkeypatch, tmp_path):
    """macOS sun_path is 104 B; long temp paths must fall back to TCP."""
    long_dir = tmp_path / ("x" * 90)
    monkeypatch.setattr(ipc, "_uds_path", lambda: long_dir / "snapdec.sock")
    assert daemon._bind_uds(lambda: None) is None


def test_uds_attempted_for_short_path(monkeypatch, tmp_path):
    # Windows has no AF_UNIX — _bind_uds must return None, never raise.
    monkeypatch.setattr(ipc, "_uds_path",
                        lambda: Path("C:/short/snapdec.sock"))
    assert daemon._bind_uds(lambda: None) is None


def test_bind_tcp_finds_a_port():
    srv, port = daemon._bind_tcp(lambda: None, None)
    assert srv is not None and port is not None
    srv.server_close()
