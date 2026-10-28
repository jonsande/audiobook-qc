"""SQLite real sobre archivos temporales: dominio, CRUD, transacciones y esquema."""

import io
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from audiobook_qc import incident_probe
from audiobook_qc.captured_incident import IncidentType
from audiobook_qc.incident import Incident
from audiobook_qc.sqlite_repository import (
    IncidentNotFoundError,
    SchemaError,
    SQLiteIncidentRepository,
)


@pytest.fixture
def incident() -> Incident:
    return Incident(
        IncidentType.TEXT,
        "capítulo.mp3",
        "/no/existe/audio.mp3",
        1104.5171234567,
        "file:///no/existe/libro.pdf",
        1,
        "¿Qué?\nparti-\r\nda. e\u0301\n",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "incidents.sqlite3"
    with SQLiteIncidentRepository(path) as repository:
        repository.initialize()
    return path


def test_explicit_initialization_required(tmp_path: Path, incident: Incident) -> None:
    path = tmp_path / "fresh.sqlite3"
    with SQLiteIncidentRepository(path) as repository:
        for action in (
            lambda: repository.add(incident),
            repository.list,
            lambda: repository.get(1),
        ):
            with pytest.raises(SchemaError, match="explícitamente"):
                action()
        repository.initialize()
        assert repository.list() == []
        stored = repository.add(incident)
        repository.initialize()
        assert repository.get(stored.id) == stored
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_add_close_reopen_and_read(database: Path, incident: Incident) -> None:
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(incident)
        assert incident.id is None
        assert stored.id == 1
        assert repository.get(1) == stored
    with SQLiteIncidentRepository(database) as reopened:
        recovered = reopened.get(1)
        assert recovered == stored
        assert (
            recovered.audio_position_seconds.hex()
            == incident.audio_position_seconds.hex()
        )
        assert recovered.selected_text == incident.selected_text
        assert recovered.created_at.tzinfo is timezone.utc
        assert recovered.updated_at == recovered.created_at


@pytest.mark.parametrize(
    "position", [0.0, -0.311595, 1.0000000000000002, 1e-12, 1104.5171234567]
)
def test_binary64_roundtrip(
    database: Path, incident: Incident, position: float
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(replace(incident, audio_position_seconds=position))
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(stored.id).audio_position_seconds.hex() == position.hex()


@pytest.mark.parametrize("description", [None, "", "Descripción genérica\ná"])
@pytest.mark.parametrize("comment", [None, "", "Comentario propio\r\nñ"])
def test_description_comment_separate_and_nullable(
    database: Path, incident: Incident, description: str | None, comment: str | None
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(
            replace(incident, generic_description=description, custom_comment=comment)
        )
        recovered = repository.get(stored.id)
    assert recovered.generic_description == description
    assert recovered.custom_comment == comment


def test_list_deterministic_by_creation_time_then_id(
    database: Path, incident: Incident
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        newer = repository.add(
            replace(incident, created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
        )
        older = repository.add(incident)
        same_time = repository.add(incident)
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == [older, same_time, newer]


def test_edit_and_reopen_source_of_truth(
    database: Path, incident: Incident, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 1, 2, 12, 34, 56, 123456, tzinfo=timezone.utc)
    monkeypatch.setattr("audiobook_qc.sqlite_repository.utc_now", lambda: now)
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(incident)
        edited = replace(
            stored,
            incident_type=IncidentType.PRON,
            audio_filename="otro.mp3",
            audio_path="ruta/relativa.mp3",
            audio_position_seconds=0.125123,
            document="https://example.org/new.pdf",
            page=0,
            selected_text="Nuevo\ntexto",
            generic_description="genérica",
            custom_comment="personal",
            exported=True,
        )
        updated = repository.update(edited)
        assert updated.created_at == stored.created_at
        assert updated.updated_at == now
        assert (
            stored.custom_comment is None
        )  # La copia anterior no es la fuente de verdad.
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(stored.id) == updated
        assert repository.get(stored.id).exported is True
        reset = repository.update(replace(updated, exported=False, custom_comment=None))
        assert reset.exported is False
        assert repository.get(stored.id).custom_comment is None


def test_delete_committed_and_ids_not_reused(
    database: Path, incident: Incident
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        first = repository.add(incident)
        repository.delete(first.id)
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(first.id) is None
        assert repository.list() == []
        assert repository.add(incident).id > first.id


def test_missing_identity_and_preserved_creation_date(
    database: Path, incident: Incident
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(999) is None
        with pytest.raises(IncidentNotFoundError):
            repository.delete(999)
        with pytest.raises(IncidentNotFoundError):
            repository.update(replace(incident, id=999))
        with pytest.raises(ValueError, match="con id"):
            repository.update(incident)
        stored = repository.add(incident)
        with pytest.raises(ValueError, match="sin id"):
            repository.add(stored)
        with pytest.raises(ValueError, match="created_at"):
            repository.update(
                replace(stored, created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
            )
        assert repository.get(stored.id) == stored


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("incident_type", "NEW"),
        ("incident_type", "text"),
        ("incident_type", None),
        ("audio_filename", None),
        ("audio_filename", ""),
        ("audio_path", None),
        ("audio_path", ""),
        ("document", None),
        ("document", ""),
        ("selected_text", ""),
        ("selected_text", None),
        ("selected_text", b"blob"),
        ("audio_position_seconds", None),
        ("audio_position_seconds", "invalid"),
        ("audio_position_seconds", float("nan")),
        ("audio_position_seconds", float("inf")),
        ("page", None),
        ("page", -1),
        ("page", 1.5),
        ("exported", 2),
        ("exported", None),
        ("created_at", "2026-01-01T00:00:00"),
        ("updated_at", None),
        ("generic_description", b"blob"),
        ("custom_comment", b"blob"),
        ("id", -1),
    ],
)
def test_sql_constraints_without_python_validation(
    database: Path, incident: Incident, field: str, value: object
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(incident)
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"UPDATE incidents SET {field}=? WHERE id=?", (value, stored.id)
            )
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(stored.id) == stored


def test_failed_transaction_rolls_back_all_changes(
    database: Path, incident: Incident
) -> None:
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(incident)
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError), connection:
            connection.execute("UPDATE incidents SET custom_comment='discarded'")
            connection.execute("UPDATE incidents SET incident_type='INVALID'")
    with SQLiteIncidentRepository(database) as repository:
        assert repository.get(stored.id) == stored


def test_parameterized_sql_preserves_quotes(database: Path, incident: Incident) -> None:
    text = "'); DROP TABLE incidents; --\n¿Texto?"
    with SQLiteIncidentRepository(database) as repository:
        stored = repository.add(
            replace(incident, selected_text=text, custom_comment=text)
        )
        assert repository.get(stored.id).selected_text == text
        assert repository.get(stored.id).custom_comment == text
        assert len(repository.list()) == 1


@pytest.mark.parametrize("version", [2, 999])
def test_unknown_schema_is_not_changed(tmp_path: Path, version: int) -> None:
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version={version}")
    with SQLiteIncidentRepository(path) as repository:
        with pytest.raises(SchemaError, match="no compatible"):
            repository.initialize()
        with pytest.raises(SchemaError):
            repository.list()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == version


def test_unversioned_tables_not_adopted(tmp_path: Path) -> None:
    path = tmp_path / "other.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE other (id INTEGER)")
    with SQLiteIncidentRepository(path) as repository:
        with pytest.raises(SchemaError, match="tablas"):
            repository.initialize()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall() == [("other",)]


def test_context_manager_closes_connection(database: Path) -> None:
    with SQLiteIncidentRepository(database) as repository:
        assert repository.list() == []
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        repository.list()


def test_cli_init_insert_reopen_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = str(tmp_path / "probe.sqlite3")
    assert incident_probe.main(["--db", path, "init"]) == 0
    capsys.readouterr()
    payload = {
        "incident_type": "INTER",
        "audio_filename": "á.mp3",
        "audio_path": "/missing/á.mp3",
        "audio_position_seconds": 6.249938,
        "document": "file:///missing/doc.pdf",
        "page": 2,
        "selected_text": "Línea\nparti-\nda.",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert (
        incident_probe.main(["--db", path, "add", "--custom-comment", "Comentario"])
        == 0
    )
    added = json.loads(capsys.readouterr().out)
    assert incident_probe.main(["--db", path, "get", str(added["id"])]) == 0
    recovered = json.loads(capsys.readouterr().out)
    assert recovered == added
    assert recovered["custom_comment"] == "Comentario"
    assert recovered["generic_description"] is None
    assert incident_probe.main(["--db", path, "get", "999"]) == 1
    assert "inexistente" in capsys.readouterr().err


@pytest.mark.parametrize("payload", ["not JSON", "[]", "{}", '{"incident_type":"NEW"}'])
def test_cli_invalid_input_is_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: str,
) -> None:
    path = str(tmp_path / "probe.sqlite3")
    assert incident_probe.main(["--db", path, "init"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert incident_probe.main(["--db", path, "add"]) == 1
    assert "Error de persistencia" in capsys.readouterr().err
