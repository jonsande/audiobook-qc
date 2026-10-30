"""Modo y foco probados sin escritorio; los rechazos no abren SQLite ni capturan."""

import subprocess
import sys
from pathlib import Path

import pytest

from audiobook_qc import capture_save_probe, correction_mode
from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.desktop_policy import ActivationRejected, require_correction_context
from audiobook_qc.integrations import focus
from audiobook_qc.jobs import JobStore, job_database
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository


@pytest.fixture
def session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_desktop_sources
) -> Path:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    store = JobStore()
    store.configure(str(tmp_path / "trabajos"))
    job = store.create("Prueba")
    store.select(job.id)

    # Esta suite aísla el indicador runtime; GNOME se prueba con un backend falso.
    class FlagController:
        def on(self):
            correction_mode.set_active(True)

        def off(self):
            correction_mode.set_active(False)

        def status(self, active):
            return (f"Modo de corrección {'activo' if active else 'inactivo'}", True)

    monkeypatch.setattr(
        correction_mode, "make_controller", lambda journal: FlagController()
    )
    return tmp_path


def test_mode_starts_inactive_without_creating_state(session: Path) -> None:
    assert correction_mode.is_active() is False
    assert not (session / "runtime").exists()


def test_mode_on_off_status_and_application_independence(
    session: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert correction_mode.main(["status"]) == 0
    assert "inactivo" in capsys.readouterr().out
    assert correction_mode.main(["on"]) == 0
    assert correction_mode.is_active()
    assert correction_mode.main(["status"]) == 0
    assert "activo" in capsys.readouterr().out
    assert correction_mode.main(["off"]) == 0
    assert correction_mode.main(["off"]) == 0
    assert not correction_mode.is_active()


def test_mode_shared_between_processes_and_separate_displays(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from audiobook_qc.correction_mode import set_active; set_active(True)",
        ],
        check=True,
    )
    assert correction_mode.is_active()
    monkeypatch.setenv("DISPLAY", ":1")
    assert not correction_mode.is_active()
    monkeypatch.setenv("DISPLAY", ":0")
    assert correction_mode.is_active()
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from audiobook_qc.correction_mode import set_active; set_active(False)",
        ],
        check=True,
    )
    assert not correction_mode.is_active()


@pytest.mark.parametrize(
    "content", ["", "true", "active", "inactive\n", "active\nextra"]
)
def test_corrupt_state_cannot_enable_mode(session: Path, content: str) -> None:
    path = correction_mode.state_path()
    path.parent.mkdir(parents=True)
    path.write_text(content)
    with pytest.raises(correction_mode.ModeError):
        correction_mode.is_active()
    correction_mode.set_active(False)
    assert not correction_mode.is_active()


@pytest.mark.parametrize("variable", ["DISPLAY", "XDG_RUNTIME_DIR"])
def test_missing_session_configuration_cannot_enable_mode(
    session: Path,
    variable: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(variable)
    with pytest.raises(correction_mode.ModeError):
        correction_mode.is_active()


def test_mode_read_and_write_errors_are_explicit(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def denied(*args: object, **kwargs: object):
        raise PermissionError("sin permiso")

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(correction_mode.ModeError, match="sin permiso"):
        correction_mode.is_active()
    assert correction_mode.main(["status"]) == 1
    assert "sin permiso" in capsys.readouterr().err
    monkeypatch.setattr(Path, "unlink", denied)
    assert correction_mode.main(["off"]) == 1


def test_mode_notification_cannot_revert_successful_state_change(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from audiobook_qc.integrations.notifications import NotificationError

    def fail(*args: object, **kwargs: object):
        raise NotificationError("sin aviso")

    monkeypatch.setattr(correction_mode, "notify", fail)
    assert correction_mode.main(["on", "--notify"]) == 0
    assert correction_mode.is_active()
    assert "Aviso de notificación" in capsys.readouterr().err


def test_mode_change_error_is_notified_when_requested(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = []

    def denied(*args: object):
        raise PermissionError("sin permiso")

    monkeypatch.setattr(correction_mode, "set_active", denied)
    monkeypatch.setattr(
        correction_mode,
        "notify",
        lambda *args, **kwargs: messages.append((args, kwargs)),
    )
    assert correction_mode.main(["on", "--notify"]) == 1
    assert not correction_mode.is_active()
    assert messages == [
        (("Error de modo de corrección", "sin permiso"), {"error": True})
    ]


def test_unverifiable_process_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: object, **kwargs: object):
        raise PermissionError("proceso no accesible")

    monkeypatch.setattr(Path, "resolve", denied)
    with pytest.raises(focus.FocusError, match="proceso"):
        focus._executable(123)


def test_focus_is_reidentified_after_application_restart(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for window, pid in [("0x123", 123), ("0x456", 456)]:
        setup_focus(
            monkeypatch,
            f'WM_CLASS(STRING) = "okular", "okular"\n_NET_WM_PID(CARDINAL) = {pid}',
            "okular",
            (window, window),
        )
        seen = []
        monkeypatch.setattr(
            focus, "_executable", lambda value: seen.append(value) or "okular"
        )
        assert focus.active_application() == "okular"
        assert seen == [pid]


def test_inactive_policy_does_not_even_consult_focus() -> None:
    def unexpected():
        pytest.fail("No debe consultar foco en modo inactivo")

    with pytest.raises(ActivationRejected, match="inactivo"):
        require_correction_context(mode_active=lambda: False, active_app=unexpected)


@pytest.mark.parametrize("application", ["okular", "mpv"])
def test_policy_permits_only_allowed_active_apps(application: str) -> None:
    require_correction_context(mode_active=lambda: True, active_app=lambda: application)


@pytest.mark.parametrize(
    "application", ["firefox", "libreoffice", "terminal", "other", ""]
)
def test_policy_rejects_other_apps(application: str) -> None:
    with pytest.raises(ActivationRejected):
        require_correction_context(
            mode_active=lambda: True, active_app=lambda: application
        )


def setup_focus(
    monkeypatch: pytest.MonkeyPatch,
    properties: str,
    executable: str,
    windows: tuple[str, str] = ("0x123", "0x123"),
) -> list[tuple[str, ...]]:
    calls = []
    root_windows = iter(windows)

    def query(*args: str) -> str:
        calls.append(args)
        if args == ("-root", "_NET_ACTIVE_WINDOW"):
            return f"_NET_ACTIVE_WINDOW(WINDOW): window id # {next(root_windows)}"
        assert args == ("-id", windows[0], "WM_CLASS", "_NET_WM_PID")
        return properties

    monkeypatch.setattr(focus, "_query", query)
    monkeypatch.setattr(focus, "_executable", lambda pid: executable)
    return calls


@pytest.mark.parametrize(
    "instance,wm_class,executable,expected",
    [
        ("okular", "okular", "okular", "okular"),
        ("gl", "mpv", "mpv", "mpv"),
        ("mpv", "mpv", "mpv", "mpv"),
        ("gnome-terminal-server", "Gnome-terminal", "gnome-terminal-server", "other"),
        ("Navigator", "firefox", "firefox", "other"),
        ("libreoffice", "libreoffice-calc", "soffice.bin", "other"),
        ("okular", "okular", "gnome-terminal-server", "other"),
        ("other", "mpv", "mpv", "other"),
    ],
)
def test_focus_identifies_window_class_and_process_not_title_or_open_applications(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    instance: str,
    wm_class: str,
    executable: str,
    expected: str,
) -> None:
    calls = setup_focus(
        monkeypatch,
        f'WM_CLASS(STRING) = "{instance}", "{wm_class}"\n_NET_WM_PID(CARDINAL) = 123',
        executable,
    )
    assert focus.active_application() == expected
    assert len(calls) == 3


@pytest.mark.parametrize("window", ["0x0", "0x123, 0x456", "none", "0xxyz"])
def test_missing_or_ambiguous_active_window_is_rejected(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    window: str,
) -> None:
    setup_focus(monkeypatch, "", "okular", (window, window))
    with pytest.raises(focus.FocusError):
        focus.active_application()


@pytest.mark.parametrize(
    "properties",
    [
        "WM_CLASS: not found.",
        'WM_CLASS(STRING) = "okular", "okular"',
        'WM_CLASS(STRING) = "okular", "okular"\n_NET_WM_PID(CARDINAL) = 0',
        'WM_CLASS(STRING) = "okular", "okular"\n_NET_WM_PID(CARDINAL) = 1, 2',
    ],
)
def test_missing_or_ambiguous_identity_is_rejected(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    properties: str,
) -> None:
    setup_focus(monkeypatch, properties, "okular")
    with pytest.raises(focus.FocusError):
        focus.active_application()


def test_focus_change_during_identification_is_rejected(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_focus(
        monkeypatch,
        'WM_CLASS(STRING) = "okular", "okular"\n_NET_WM_PID(CARDINAL) = 1',
        "okular",
        ("0x123", "0x456"),
    )
    with pytest.raises(focus.FocusError, match="cambió"):
        focus.active_application()


@pytest.mark.parametrize("session_type", ["wayland", "", "unknown"])
def test_non_x11_session_is_rejected(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    session_type: str,
) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", session_type)
    with pytest.raises(focus.FocusError):
        focus.active_application()


@pytest.mark.parametrize(
    "failure", [FileNotFoundError(), subprocess.TimeoutExpired("xprop", 3)]
)
def test_xprop_execution_failure_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    def fail(*args: object, **kwargs: object):
        raise failure

    monkeypatch.setattr(focus.subprocess, "run", fail)
    with pytest.raises(focus.FocusError):
        focus._query("-root", "_NET_ACTIVE_WINDOW")


def test_xprop_uses_no_shell_timeout_and_stable_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command, **kwargs):
        assert command == ["xprop", "-root", "_NET_ACTIVE_WINDOW"]
        assert kwargs["timeout"] == 3 and kwargs["env"]["LC_ALL"] == "C"
        assert "shell" not in kwargs
        return subprocess.CompletedProcess(command, 1, "", "sin X11")

    monkeypatch.setattr(focus.subprocess, "run", run)
    with pytest.raises(focus.FocusError, match="sin X11"):
        focus._query("-root", "_NET_ACTIVE_WINDOW")


@pytest.mark.parametrize(
    "active,application",
    [
        (False, "okular"),
        (True, "firefox"),
        (True, "terminal"),
        (True, "libreoffice"),
        (True, None),
    ],
)
def test_rejected_desktop_activation_never_captures_opens_database_or_creates_lock(
    session: Path,
    active: bool,
    application: str | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if active:
        correction_mode.set_active(True)

    def read_focus():
        if application is None:
            raise focus.FocusError("identificación imposible")
        return application

    def unexpected(*args: object, **kwargs: object):
        pytest.fail("No debe capturar ni abrir SQLite ni adquirir bloqueo")

    messages = []
    monkeypatch.setattr(capture_save_probe, "active_application", read_focus)
    monkeypatch.setattr(capture_save_probe, "capture_incident", unexpected)
    monkeypatch.setattr(capture_save_probe, "SQLiteIncidentRepository", unexpected)
    monkeypatch.setattr(capture_save_probe, "activation_guard", unexpected)
    monkeypatch.setattr(
        capture_save_probe, "notify", lambda *args, **kwargs: messages.append(args)
    )
    database = session / "must-not-exist.sqlite3"
    assert capture_save_probe.main(["--desktop", "--db", str(database), "INTER"]) == 1
    assert not database.exists()
    assert len(messages) == 1 and messages[0][0] == "Activación rechazada"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("application", ["okular", "mpv"])
def test_active_mode_and_allowed_focus_preserve_integrated_capture_and_save(
    session: Path,
    monkeypatch: pytest.MonkeyPatch,
    application: str,
) -> None:
    database = job_database(JobStore().active())
    correction_mode.set_active(True)
    monkeypatch.setattr(capture_save_probe, "active_application", lambda: application)
    captured = CapturedIncident(
        "INTER",
        "a.wav",
        "./a.wav",
        19.300243,
        "libro.pdf",
        33,
        "parti-\r\ndo. ",
    )
    monkeypatch.setattr(
        capture_save_probe, "capture_incident", lambda *args, **kwargs: captured
    )
    monkeypatch.setattr(capture_save_probe, "notify", lambda *args, **kwargs: None)
    assert capture_save_probe.main(["--desktop", "--db", str(database), "INTER"]) == 0
    with SQLiteIncidentRepository(database) as repository:
        saved = repository.get(1)
        assert saved.selected_text == captured.selected_text
        assert (
            saved.audio_position_seconds.hex() == captured.audio_position_seconds.hex()
        )
