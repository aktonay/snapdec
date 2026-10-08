"""Pid-reuse guard in lifecycle (Windows recycles PIDs aggressively — ADR-0011)."""

from __future__ import annotations

import sys

from snapdec.runtime import lifecycle


class _FakeProc:
    def __init__(self, pid: int, name: str, status: str, fake: _FakePsutil):
        self._pid, self._name = pid, name
        self._status, self._fake = status, fake

    def is_running(self) -> bool:
        return True

    def status(self) -> str:
        return self._status

    def name(self) -> str:
        return self._name

    def terminate(self) -> None:
        self._fake.terminated.append(self._pid)


class _FakePsutil:
    """Stands in for `import psutil` inside lifecycle via sys.modules."""

    Error = RuntimeError
    STATUS_ZOMBIE = "zombie"

    def __init__(self, names: dict[int, tuple[str, str]]):
        self._names = names
        self.terminated: list[int] = []

    def Process(self, pid: int) -> _FakeProc:
        entry = self._names.get(int(pid))
        if entry is None:
            raise self.Error("no such process")
        name, status = entry
        return _FakeProc(int(pid), name, status, self)


def _with_fake_psutil(monkeypatch, names: dict[int, tuple[str, str]]) -> _FakePsutil:
    fake = _FakePsutil(names)
    monkeypatch.setitem(sys.modules, "psutil", fake)
    return fake


def test_pid_alive_accepts_python_and_snapdec_processes(monkeypatch):
    _with_fake_psutil(monkeypatch, {
        101: ("python.exe", "running"),
        202: ("Python", "running"),
        303: ("snapdec.exe", "running"),
    })
    assert lifecycle._pid_alive(101) is True
    assert lifecycle._pid_alive(202) is True
    assert lifecycle._pid_alive(303) is True


def test_pid_alive_rejects_reused_pid(monkeypatch):
    # stale state file points at a pid Windows handed to an unrelated
    # process — that process is NOT the daemon
    _with_fake_psutil(monkeypatch, {999: ("explorer.exe", "running")})
    assert lifecycle._pid_alive(999) is False
    assert lifecycle._pid_alive(None) is False
    assert lifecycle._pid_alive("not-a-pid") is False


def test_pid_alive_rejects_zombie(monkeypatch):
    _with_fake_psutil(monkeypatch, {101: ("python.exe", "zombie")})
    assert lifecycle._pid_alive(101) is False


def test_stop_daemon_never_terminates_reused_pid(monkeypatch, tmp_path):
    # recorded pid now belongs to explorer.exe: shutdown POST fails, and the
    # terminate fallback must refuse to touch it
    fake = _with_fake_psutil(monkeypatch, {999: ("explorer.exe", "running")})
    monkeypatch.setattr(lifecycle.ipc, "read_state",
                        lambda: {"pid": 999, "token": "t"})
    monkeypatch.setattr(lifecycle.ipc, "daemon_url", lambda: "")
    monkeypatch.setattr(lifecycle.ipc, "clear_state", lambda: None)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda s: None)
    assert lifecycle.stop_daemon() is True
    assert fake.terminated == []


def test_stop_daemon_terminates_daemon_named_pid(monkeypatch, tmp_path):
    # graceful /shutdown never answered → after the wait loop the recorded
    # python-named pid is terminated
    fake = _with_fake_psutil(monkeypatch, {101: ("python.exe", "running")})
    monkeypatch.setattr(lifecycle.ipc, "read_state",
                        lambda: {"pid": 101, "token": "t"})
    monkeypatch.setattr(lifecycle.ipc, "daemon_url", lambda: "")
    monkeypatch.setattr(lifecycle.ipc, "clear_state", lambda: None)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda s: None)
    assert lifecycle.stop_daemon() is True
    assert fake.terminated == [101]
