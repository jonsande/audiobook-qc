"""Activación sin teclado real: caso de uso, SQLite, exclusión y notificaciones."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from audiobook_qc import capture_save_probe
from audiobook_qc.capture import CaptureError
from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.integrations import notifications
from audiobook_qc.integrations.activation import ActivationBusy, activation_guard
from audiobook_qc.integrations.notifications import NotificationError
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository


@pytest.fixture(autouse=True)
def authorized_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Esta suite prueba captura/avisos; el filtro se prueba por separado."""
    monkeypatch.setattr(capture_save_probe, "check_desktop_activation", lambda: None)


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "desktop.sqlite3"
    with SQLiteIncidentRepository(path) as repository:
        repository.initialize()
    return path


@pytest.fixture
def capture(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    codes: list[str] = []

    def read(code: str, **sources: object) -> CapturedIncident:
        codes.append(code)
        return CapturedIncident(
            IncidentType(code),
            "á.wav",
            "./á.wav",
            19.300243,
            "file:///libro.pdf",
            33,
            "  Texto parti-\r\ndo. e\u0301\n",
        )

    monkeypatch.setattr(capture_save_probe, "capture_incident", read)
    return codes


@pytest.mark.parametrize("code", [code.value for code in IncidentType])
def test_desktop_command_maps_code_to_existing_use_case_and_notifies_after_commit(
    database: Path,
    capture: list[str],
    code: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events = []
    use_case = capture_save_probe.capture_and_save_incident

    def execute(selected_code: str, **dependencies: object):
        events.append("use_case")
        return use_case(selected_code, **dependencies)

    def notify(summary: str, body: str, *, error: bool) -> None:
        with SQLiteIncidentRepository(database) as repository:
            stored = repository.get(1)
        assert stored is not None and stored.incident_type.value == code
        assert stored.selected_text == "  Texto parti-\r\ndo. e\u0301\n"
        assert stored.audio_position_seconds.hex() == (19.300243).hex()
        assert summary == "Incidencia guardada"
        assert body == f"{code} · ID 1" and error is False
        events.append("notification")

    monkeypatch.setattr(capture_save_probe, "capture_and_save_incident", execute)
    monkeypatch.setattr(capture_save_probe, "notify", notify)
    assert capture_save_probe.main(["--desktop", "--db", str(database), code]) == 0
    assert capture == [code]
    assert events == ["use_case", "notification"]
    assert json.loads(capsys.readouterr().out)["id"] == 1


@pytest.mark.parametrize(
    "error", [CaptureError("fuente ausente"), sqlite3.OperationalError("sin disco")]
)
def test_failure_notifies_without_success_or_partial_record(
    database: Path,
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    messages = []

    def fail(*args: object, **kwargs: object):
        raise error

    monkeypatch.setattr(capture_save_probe, "capture_incident", fail)
    monkeypatch.setattr(
        capture_save_probe,
        "notify",
        lambda summary, body, **kwargs: messages.append((summary, body, kwargs)),
    )
    assert capture_save_probe.main(["--desktop", "--db", str(database), "TEXT"]) == 1
    output = capsys.readouterr()
    assert output.out == "" and str(error) in output.err
    assert messages == [("Incidencia no guardada", f"TEXT: {error}", {"error": True})]
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []


def test_sqlite_insert_failure_is_reported_without_success(
    database: Path,
    capture: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER fail BEFORE INSERT ON incidents "
            "BEGIN SELECT RAISE(ABORT, 'escritura rechazada'); END"
        )
    messages = []
    monkeypatch.setattr(
        capture_save_probe,
        "notify",
        lambda summary, body, **kwargs: messages.append((summary, body)),
    )
    assert capture_save_probe.main(["--desktop", "--db", str(database), "PRON"]) == 1
    assert messages[0][0] == "Incidencia no guardada"
    assert "escritura rechazada" in messages[0][1]
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []


def test_overlapping_activation_is_rejected_before_capture(
    database: Path,
    capture: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = []
    monkeypatch.setattr(
        capture_save_probe,
        "notify",
        lambda summary, body, **kwargs: messages.append(summary),
    )
    with activation_guard(str(database)):
        assert (
            capture_save_probe.main(
                [
                    "--desktop",
                    "--db",
                    str(database),
                    "DICC",
                ]
            )
            == 1
        )
    assert capture == []
    assert messages == ["Activación omitida"]
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []


def test_completed_consecutive_activations_are_independent_and_guard_is_released(
    database: Path,
    capture: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = []
    monkeypatch.setattr(
        capture_save_probe,
        "notify",
        lambda summary, body, **kwargs: messages.append(body),
    )
    for _ in range(2):
        assert (
            capture_save_probe.main(
                [
                    "--desktop",
                    "--db",
                    str(database),
                    "RUID",
                ]
            )
            == 0
        )
    assert capture == ["RUID", "RUID"]
    assert messages == ["RUID · ID 1", "RUID · ID 2"]
    with SQLiteIncidentRepository(database) as repository:
        assert len(repository.list()) == 2


def test_notification_failure_after_save_does_not_report_failed_persistence(
    database: Path,
    capture: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise NotificationError("sin bus de notificaciones")

    monkeypatch.setattr(capture_save_probe, "notify", fail)
    assert capture_save_probe.main(["--desktop", "--db", str(database), "RESP"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["id"] == 1
    assert "Incidencia guardada: RESP · ID 1" in output.err
    assert "no guardada" not in output.err
    with SQLiteIncidentRepository(database) as repository:
        assert len(repository.list()) == 1


def test_uninitialized_database_is_not_initialized_by_desktop_mode(
    tmp_path: Path,
    capture: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "fresh.sqlite3"
    messages = []
    monkeypatch.setattr(
        capture_save_probe,
        "notify",
        lambda summary, body, **kwargs: messages.append(summary),
    )
    assert capture_save_probe.main(["--desktop", "--db", str(path), "OTRO"]) == 1
    assert messages == ["Incidencia no guardada"]
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_guard_releases_after_exception_and_resolves_symlinks(database: Path) -> None:
    alias = database.with_name("alias.sqlite3")
    alias.symlink_to(database)
    with pytest.raises(RuntimeError):
        with activation_guard(str(database)):
            with pytest.raises(ActivationBusy):
                with activation_guard(str(alias)):
                    pytest.fail("No debe adquirir otro bloqueo para el mismo destino")
            raise RuntimeError("fallo durante la captura")
    with activation_guard(str(alias)):
        pass


@pytest.mark.parametrize(
    "options", [["--db", "relative.sqlite3"], ["--mpv-socket", "relative.sock"]]
)
def test_desktop_rejects_paths_dependent_on_working_directory(
    database: Path,
    options: list[str],
    capture: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = []
    monkeypatch.setattr(
        capture_save_probe,
        "notify",
        lambda summary, body, **kwargs: messages.append((summary, body)),
    )
    assert (
        capture_save_probe.main(
            [
                "--desktop",
                "--db",
                str(database),
                "TEXT",
                *options,
            ]
        )
        == 1
    )
    assert capture == []
    assert messages[0][0] == "Incidencia no guardada"
    assert "rutas absolutas" in messages[0][1]
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []


def test_guard_excludes_another_process_and_remains_as_a_sidecar(
    database: Path,
) -> None:
    code = (
        "import sys\n"
        "from audiobook_qc.integrations.activation import activation_guard\n"
        "from audiobook_qc.integrations.activation import ActivationBusy\n"
        "try:\n"
        "    with activation_guard(sys.argv[1]): pass\n"
        "except ActivationBusy:\n"
        "    raise SystemExit(7)\n"
    )
    with activation_guard(str(database)):
        result = subprocess.run(
            [sys.executable, "-c", code, str(database)], check=False
        )
        assert result.returncode == 7
    assert database.with_name(database.name + ".capture.lock").exists()


def test_desktop_cli_wires_explicit_adapters_and_database(
    database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from audiobook_qc.integrations.mpv import MpvState
    from audiobook_qc.integrations.okular import OkularState
    from audiobook_qc.integrations.selection import Selection

    calls = []

    def primary(name: str) -> Selection:
        calls.append(name)
        return Selection(name, "Frase")

    def pdf(service: str) -> OkularState:
        calls.append(service)
        return OkularState(service, "documento.pdf", None, 33)

    def audio(socket: str) -> MpvState:
        calls.append(socket)
        return MpvState("a.wav", "./a.wav", 19.300243, None, True)

    monkeypatch.setattr(capture_save_probe.selection, "read_selection", primary)
    monkeypatch.setattr(capture_save_probe.okular, "read_state", pdf)
    monkeypatch.setattr(capture_save_probe.mpv, "read_state", audio)
    monkeypatch.setattr(capture_save_probe, "notify", lambda *args, **kwargs: None)
    assert (
        capture_save_probe.main(
            [
                "--desktop",
                "--db",
                str(database),
                "INTER",
                "--mpv-socket",
                "/explicit/mpv.sock",
                "--okular-service",
                "org.kde.okular-test",
            ]
        )
        == 0
    )
    assert calls == ["primary", "org.kde.okular-test", "/explicit/mpv.sock"]
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(1).selected_text == "Frase"


def test_notification_uses_argument_vector_and_escapes_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command: list[str], **kwargs: object):
        assert command == [
            "notify-send",
            "--app-name=audiobook-qc",
            "--urgency=critical",
            "--",
            "Incidencia no guardada",
            "&lt;ruta&gt; &amp; datos",
        ]
        assert kwargs == dict(capture_output=True, text=True, timeout=3, check=False)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(notifications.subprocess, "run", run)
    notifications.notify("Incidencia no guardada", "<ruta> & datos", error=True)


@pytest.mark.parametrize(
    "error",
    [FileNotFoundError("no instalado"), subprocess.TimeoutExpired("notify-send", 3)],
)
def test_notification_execution_failure_is_explicit(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object):
        raise error

    monkeypatch.setattr(notifications.subprocess, "run", fail)
    with pytest.raises(NotificationError):
        notifications.notify("Resultado", "texto")


def test_notification_nonzero_exit_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        notifications.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "", "sin servicio"),
    )
    with pytest.raises(NotificationError, match="sin servicio"):
        notifications.notify("Resultado", "texto")
