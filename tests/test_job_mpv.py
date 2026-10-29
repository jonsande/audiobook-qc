"""Runtime y lanzamiento de mpv: sin procesos gráficos ni reproductores reales."""

import socket
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from audiobook_qc.integrations import job_mpv
from audiobook_qc.integrations.mpv import MpvError


@pytest.fixture
def runtime(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="aqc-") as directory:
        monkeypatch.setenv("XDG_RUNTIME_DIR", directory)
        yield Path(directory)


def test_socket_identity_is_deterministic_unique_and_under_runtime(runtime):
    a, b = str(uuid4()), str(uuid4())
    assert job_mpv.socket_path(a) == job_mpv.socket_path(a)
    assert job_mpv.socket_path(a) != job_mpv.socket_path(b)
    assert job_mpv.socket_path(a) == runtime / "audiobook-qc" / (a + ".sock")
    assert not (runtime / "audiobook-qc").exists()


@pytest.mark.parametrize("value", [None, "", "relative", "/" + "x" * 110])
def test_missing_or_oversized_runtime_has_no_fallback(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    else:
        monkeypatch.setenv("XDG_RUNTIME_DIR", value)
    with pytest.raises(MpvError):
        job_mpv.socket_path(str(uuid4()))


class FakeProcess:
    pid = 123

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        return 0


@pytest.fixture
def launcher(runtime, monkeypatch):
    commands = []
    process = FakeProcess()

    def popen(command, **kwargs):
        commands.append((command, kwargs))
        return process

    monkeypatch.setattr(job_mpv.subprocess, "Popen", popen)
    return commands, process


def test_launch_uses_absolute_files_job_socket_and_no_shell(
    runtime, launcher, monkeypatch
):
    checks = iter([False, True])
    monkeypatch.setattr(job_mpv, "_live", lambda *a, **kw: next(checks))
    files = (runtime / "capítulo 1.mp3", runtime / "capítulo 2.mp3")
    identifier = str(uuid4())
    result = job_mpv.launch(identifier, files, runtime / "mpv.log")
    command, kwargs = launcher[0][0]
    assert command == [
        "mpv",
        "--idle=yes",
        "--pause",
        "--force-window=yes",
        f"--input-ipc-server={job_mpv.socket_path(identifier)}",
        "--",
        *map(str, files),
    ]
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert "shell" not in kwargs
    assert result["status"] == "started"
    assert (runtime / "audiobook-qc").stat().st_mode & 0o777 == 0o700


def test_running_instance_is_reused_without_relaunch(runtime, launcher, monkeypatch):
    monkeypatch.setattr(job_mpv, "_live", lambda *a, **kw: True)
    monkeypatch.setattr(job_mpv, "read_state", lambda path: None)
    assert job_mpv.launch(str(uuid4()), (), runtime / "mpv.log")["status"] == "running"
    assert launcher[0] == []


def test_first_launch_needs_declared_audio(runtime, launcher):
    with pytest.raises(MpvError, match="primera vez"):
        job_mpv.launch(str(uuid4()), (), runtime / "mpv.log")
    assert launcher[0] == []


def test_failed_process_does_not_report_success(runtime, launcher, monkeypatch):
    monkeypatch.setattr(job_mpv, "_live", lambda *a, **kw: False)
    monkeypatch.setattr(launcher[1], "poll", lambda: 1)
    with pytest.raises(MpvError, match="terminó"):
        job_mpv.launch(str(uuid4()), (runtime / "a.mp3",), runtime / "mpv.log")


def test_timeout_cleans_up_only_the_process_it_started(runtime, launcher, monkeypatch):
    monkeypatch.setattr(job_mpv, "_live", lambda *a, **kw: False)
    times = iter([0, 6])
    monkeypatch.setattr(job_mpv.time, "monotonic", lambda: next(times))
    with pytest.raises(MpvError, match="se cerró el proceso"):
        job_mpv.launch(str(uuid4()), (runtime / "a.mp3",), runtime / "mpv.log")
    assert launcher[1].terminated


def test_existing_regular_file_and_symlink_never_overwritten(runtime, launcher):
    identifier = str(uuid4())
    path = job_mpv.socket_path(identifier)
    path.parent.mkdir(mode=0o700)
    path.write_text("conservar")
    with pytest.raises(MpvError, match="ocupada"):
        job_mpv.launch(identifier, (), runtime / "mpv.log")
    assert path.read_text() == "conservar"
    target = runtime / "target"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(MpvError, match="enlace"):
        job_mpv.launch(identifier, (), runtime / "mpv.log")
    assert target.read_text() == "conservar"
    assert launcher[0] == []


def test_stale_socket_removed_only_by_explicit_launch_check(runtime):
    path = runtime / "stale.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
    assert not job_mpv._live(path)
    assert path.exists()
    assert not job_mpv._live(path, clean_stale=True)
    assert not path.exists()


def test_nonprivate_runtime_namespace_is_rejected(runtime, launcher):
    parent = runtime / "audiobook-qc"
    parent.mkdir(mode=0o755)
    with pytest.raises(MpvError, match="privado"):
        job_mpv.launch(str(uuid4()), (), runtime / "mpv.log")
    assert launcher[0] == []


def test_missing_socket_read_fails_without_creating_anything(runtime):
    path = runtime / "missing.sock"
    with pytest.raises(MpvError, match="no disponible"):
        job_mpv.read_state(str(path))
    assert not path.exists()


@pytest.mark.parametrize("switch", [False, True])
def test_consistent_audio_snapshot_or_rejection_on_file_switch(
    runtime, monkeypatch, switch
):
    path = str(runtime / "job.sock")
    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, timeout):
            pass

        def connect(self, destination):
            assert destination == path

    class IPC:
        def __init__(self, connection):
            self.paths = iter(["/a.mp3", "/a.mp3", "/b.mp3" if switch else "/a.mp3"])

        def get_property(self, name):
            calls.append(name)
            if name == "path":
                return next(self.paths)
            return {
                "filename": "a.mp3",
                "time-pos": 19.300243,
                "duration": 100,
                "pause": True,
            }[name]

    monkeypatch.setattr(job_mpv.socket, "socket", lambda *a: Connection())
    monkeypatch.setattr(job_mpv, "MpvIPC", IPC)
    if switch:
        with pytest.raises(MpvError, match="cambió de archivo"):
            job_mpv.read_state(path)
    else:
        result = job_mpv.read_state(path)
        assert result.position.hex() == (19.300243).hex()
        assert result.path == "/a.mp3"
    assert calls == [
        "path",
        "filename",
        "path",
        "time-pos",
        "duration",
        "pause",
        "path",
    ]
