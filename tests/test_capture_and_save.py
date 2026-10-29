"""Integración sin escritorio: fuentes sustituibles y SQLite temporal real."""

import json
import sqlite3
from dataclasses import asdict, replace
from datetime import timedelta
from functools import partial
from pathlib import Path

import pytest

from audiobook_qc import capture_save_probe
from audiobook_qc.capture import CaptureError, capture_incident
from audiobook_qc.capture_and_save import capture_and_save_incident
from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.incident import Incident
from audiobook_qc.integrations.mpv import MpvState
from audiobook_qc.integrations.okular import OkularState
from audiobook_qc.integrations.selection import Selection, SelectionError
from audiobook_qc.sqlite_repository import SchemaError, SQLiteIncidentRepository


@pytest.fixture
def captured() -> CapturedIncident:
    return CapturedIncident(
        IncidentType.INTER,
        "capítulo.mp3",
        "relativa/capítulo.mp3",
        1104.5171234567,
        "file:///prueba/libro.pdf",
        127,
        "  ¿Qué?\nparti-\r\nda. e\u0301\n",
    )


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "capturas.sqlite3"
    with SQLiteIncidentRepository(path) as repository:
        repository.initialize()
    return path


class Writer:
    def __init__(self) -> None:
        self.received: list[Incident] = []
        self.saved: Incident | None = None

    def add(self, incident: Incident) -> Incident:
        self.received.append(incident)
        self.saved = replace(incident, id=42)
        return self.saved


def test_use_case_converts_before_writing_and_returns_repository_result(
    captured: CapturedIncident,
) -> None:
    writer = Writer()
    codes = []

    def capture(code: str) -> CapturedIncident:
        codes.append(code)
        assert writer.received == []
        return captured

    saved = capture_and_save_incident("INTER", capture=capture, repository=writer)
    assert codes == ["INTER"]
    assert len(writer.received) == 1
    entity = writer.received[0]
    assert isinstance(entity, Incident)
    assert entity.id is None
    assert saved is writer.saved
    assert saved.id == 42


def test_real_capture_pipeline_persists_all_fields_and_sqlite_id(
    database: Path,
    captured: CapturedIncident,
) -> None:
    calls = []

    def primary() -> Selection:
        calls.append("primary")
        return Selection("primary", captured.selected_text)

    def document() -> OkularState:
        calls.append("okular")
        return OkularState(
            "org.kde.okular-test", captured.document, None, captured.page
        )

    def audio() -> MpvState:
        calls.append("mpv")
        return MpvState(
            captured.audio_filename,
            captured.audio_path,
            captured.audio_position_seconds,
            None,
            True,
        )

    capture = partial(
        capture_incident, read_primary=primary, read_document=document, read_audio=audio
    )
    with SQLiteIncidentRepository(database) as repository:
        first = capture_and_save_incident(
            "INTER", capture=capture, repository=repository
        )
        second = capture_and_save_incident(
            "INTER", capture=capture, repository=repository
        )
    assert calls == ["primary", "okular", "mpv"] * 2
    assert first.id == 1
    assert second.id == 2
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == [first, second]
        saved = repository.get(second.id)
    assert saved == second
    assert {name: getattr(saved, name) for name in asdict(captured)} == asdict(captured)
    assert saved.audio_position_seconds.hex() == captured.audio_position_seconds.hex()
    assert saved.generic_description is None
    assert saved.custom_comment is None
    assert saved.exported is False
    assert saved.created_at == saved.updated_at
    assert saved.created_at.utcoffset() == timedelta(0)


def test_capture_failure_never_calls_writer() -> None:
    writer = Writer()
    error = CaptureError("sin selección")

    def fail(code: str) -> CapturedIncident:
        raise error

    with pytest.raises(CaptureError) as caught:
        capture_and_save_incident("TEXT", capture=fail, repository=writer)
    assert caught.value is error
    assert writer.received == []


def test_conversion_failure_never_calls_writer(captured: CapturedIncident) -> None:
    writer = Writer()
    with pytest.raises(ValueError, match="page"):
        capture_and_save_incident(
            "INTER", capture=lambda code: replace(captured, page=-1), repository=writer
        )
    assert writer.received == []


def test_persistence_failure_propagates(captured: CapturedIncident) -> None:
    error = sqlite3.OperationalError("disco lleno")

    class FailingWriter:
        def add(self, incident: Incident) -> Incident:
            raise error

    with pytest.raises(sqlite3.OperationalError) as caught:
        capture_and_save_incident(
            "INTER", capture=lambda code: captured, repository=FailingWriter()
        )
    assert caught.value is error


@pytest.fixture
def cli_sources(
    monkeypatch: pytest.MonkeyPatch,
    captured: CapturedIncident,
) -> list[str]:
    calls: list[str] = []

    def primary(name: str) -> Selection:
        calls.append(name)
        return Selection(name, captured.selected_text)

    def document(service: str | None) -> OkularState:
        calls.append(f"okular:{service}")
        return OkularState(
            "org.kde.okular-test", captured.document, None, captured.page
        )

    def audio(socket: str) -> MpvState:
        calls.append(f"mpv:{socket}")
        return MpvState(
            captured.audio_filename,
            captured.audio_path,
            captured.audio_position_seconds,
            None,
            True,
        )

    monkeypatch.setattr(capture_save_probe.selection, "read_selection", primary)
    monkeypatch.setattr(capture_save_probe.okular, "read_state", document)
    monkeypatch.setattr(capture_save_probe.mpv, "read_state", audio)
    return calls


def test_cli_uses_requested_database_adapters_and_prints_saved_entity(
    database: Path,
    cli_sources: list[str],
    captured: CapturedIncident,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    other = tmp_path / "otra.sqlite3"
    with SQLiteIncidentRepository(other) as repository:
        repository.initialize()
    assert (
        capture_save_probe.main(
            [
                "--db",
                str(database),
                "INTER",
                "--mpv-socket",
                "/tmp/test.sock",
                "--okular-service",
                "org.kde.okular-test",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    assert output.err == ""
    payload = json.loads(output.out)
    assert payload["id"] == 1
    assert {name: payload[name] for name in asdict(captured)} == asdict(captured)
    assert payload["generic_description"] is None
    assert payload["custom_comment"] is None
    assert payload["exported"] is False
    assert cli_sources == [
        "primary",
        "okular:org.kde.okular-test",
        "mpv:/tmp/test.sock",
    ]
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(payload["id"]).selected_text == captured.selected_text
    with SQLiteIncidentRepository(other) as repository:
        assert repository.list() == []


def test_cli_does_not_initialize_missing_schema(
    tmp_path: Path,
    cli_sources: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "sin-inicializar.sqlite3"
    assert capture_save_probe.main(["--db", str(path), "INTER"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Inicializa explícitamente" in output.err
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_cli_capture_failure_leaves_database_empty(
    database: Path,
    cli_sources: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(name: str) -> Selection:
        raise SelectionError("sin X11")

    monkeypatch.setattr(capture_save_probe.selection, "read_selection", fail)
    assert capture_save_probe.main(["--db", str(database), "TEXT"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Error de captura" in output.err
    assert "sin X11" in output.err
    assert cli_sources == []
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []


def test_cli_sqlite_write_failure_reports_error_without_success(
    database: Path,
    cli_sources: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER reject_insert BEFORE INSERT ON incidents "
            "BEGIN SELECT RAISE(ABORT, 'fallo de escritura de prueba'); END"
        )
    assert capture_save_probe.main(["--db", str(database), "INTER"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "fallo de escritura de prueba" in output.err
    assert "Traceback" not in output.err
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []


@pytest.mark.parametrize("args", [["INTER"], ["--db", "unused.sqlite3", "inter"]])
def test_cli_requires_database_and_valid_code_before_reading_sources(
    args: list[str],
    cli_sources: list[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        capture_save_probe.main(args)
    assert caught.value.code == 2
    assert cli_sources == []


def test_use_case_does_not_initialize_schema(
    tmp_path: Path,
    captured: CapturedIncident,
) -> None:
    def capture(code: str) -> CapturedIncident:
        return captured

    with SQLiteIncidentRepository(tmp_path / "fresh.sqlite3") as repository:
        with pytest.raises(SchemaError):
            capture_and_save_incident("INTER", capture=capture, repository=repository)
