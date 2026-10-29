"""Repositorio SQLite explícito, sin ORM ni dependencia de aplicaciones externas."""

import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from audiobook_qc.captured_incident import IncidentType
from audiobook_qc.incident import Incident, utc_now

SCHEMA_VERSION = 1
_CODES = ", ".join(f"'{code.value}'" for code in IncidentType)
_FIELDS = (
    "incident_type",
    "audio_filename",
    "audio_path",
    "audio_position_seconds",
    "document",
    "page",
    "selected_text",
    "generic_description",
    "custom_comment",
    "exported",
)


class SchemaError(Exception):
    """Base no inicializada o versión no compatible con este repositorio."""


class IncidentNotFoundError(LookupError):
    """La actualización o eliminación exige una incidencia existente."""


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Inicializa una base vacía o verifica la versión; no migra ni reemplaza tablas."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version != 0:
        raise SchemaError(f"Versión SQLite no compatible: {version}.")
    existing = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()
    if existing:
        raise SchemaError("La base contiene tablas sin una versión reconocida.")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(f"""
            CREATE TABLE incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT CHECK (id>0),
                created_at TEXT NOT NULL CHECK (
                    length(created_at)=32 AND substr(created_at,27)='+00:00'
                    AND julianday(created_at) IS NOT NULL),
                updated_at TEXT NOT NULL CHECK (
                    length(updated_at)=32 AND substr(updated_at,27)='+00:00'
                    AND julianday(updated_at) IS NOT NULL),
                incident_type TEXT NOT NULL CHECK (incident_type IN ({_CODES})),
                audio_filename TEXT NOT NULL CHECK (
                    typeof(audio_filename)='text' AND audio_filename <> ''),
                audio_path TEXT NOT NULL CHECK (
                    typeof(audio_path)='text' AND audio_path <> ''),
                audio_position_seconds REAL NOT NULL CHECK (
                    typeof(audio_position_seconds) IN ('real','integer') AND
                    audio_position_seconds BETWEEN -1.7976931348623157e308
                    AND 1.7976931348623157e308),
                document TEXT NOT NULL CHECK (
                    typeof(document)='text' AND document <> ''),
                page INTEGER NOT NULL CHECK (typeof(page)='integer' AND page>=0),
                selected_text TEXT NOT NULL CHECK (
                    typeof(selected_text)='text' AND selected_text <> ''),
                generic_description TEXT CHECK (
                    generic_description IS NULL OR typeof(generic_description)='text'),
                custom_comment TEXT CHECK (
                    custom_comment IS NULL OR typeof(custom_comment)='text'),
                exported INTEGER NOT NULL DEFAULT 0 CHECK (
                    typeof(exported)='integer' AND exported IN (0,1))
            )
        """)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _values(incident: Incident) -> tuple[object, ...]:
    return (
        incident.incident_type.value,
        incident.audio_filename,
        incident.audio_path,
        incident.audio_position_seconds,
        incident.document,
        incident.page,
        incident.selected_text,
        incident.generic_description,
        incident.custom_comment,
        int(incident.exported),
    )


def _from_row(row: sqlite3.Row) -> Incident:
    return Incident(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        incident_type=IncidentType(row["incident_type"]),
        audio_filename=row["audio_filename"],
        audio_path=row["audio_path"],
        audio_position_seconds=row["audio_position_seconds"],
        document=row["document"],
        page=row["page"],
        selected_text=row["selected_text"],
        generic_description=row["generic_description"],
        custom_comment=row["custom_comment"],
        exported=bool(row["exported"]),
    )


class SQLiteIncidentRepository:
    """Cada escritura confirma una transacción; las lecturas consultan siempre SQLite.

    Usar como context manager o llamar close(). Abrir no inicializa el esquema.
    """

    def __init__(self, database: str | Path, *, existing: bool = False) -> None:
        if existing:
            uri = Path(database).resolve().as_uri() + "?mode=rw"
            self._connection = sqlite3.connect(uri, uri=True)
        else:
            self._connection = sqlite3.connect(database)
        self._connection.row_factory = sqlite3.Row

    def __enter__(self) -> "SQLiteIncidentRepository":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def initialize(self) -> None:
        initialize_schema(self._connection)

    def validate_schema(self) -> None:
        """Valida versión y columnas antes de leer fuentes; no inicializa nada."""
        self._ensure_schema()
        fields = ", ".join(("id", "created_at", "updated_at", *_FIELDS))
        self._connection.execute(f"SELECT {fields} FROM incidents LIMIT 0")

    def _ensure_schema(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            raise SchemaError(
                "Inicializa explícitamente una base compatible (versión 1)."
            )

    def add(self, incident: Incident) -> Incident:
        self._ensure_schema()
        if incident.id is not None:
            raise ValueError("add requiere una incidencia nueva sin id.")
        # Una entidad nueva empieza con ambas fechas iguales.
        incident = replace(incident, updated_at=incident.created_at)
        columns = ", ".join(_FIELDS)
        placeholders = ", ".join("?" for _ in _FIELDS)
        with self._connection:
            cursor = self._connection.execute(
                f"INSERT INTO incidents ({columns}, created_at, updated_at) "
                f"VALUES ({placeholders}, ?, ?)",
                _values(incident)
                + (
                    incident.created_at.isoformat(timespec="microseconds"),
                    incident.updated_at.isoformat(timespec="microseconds"),
                ),
            )
        return replace(incident, id=cursor.lastrowid)

    def get(self, incident_id: int) -> Incident | None:
        self._ensure_schema()
        row = self._connection.execute(
            "SELECT * FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        return _from_row(row) if row is not None else None

    def list(self) -> list[Incident]:
        self._ensure_schema()
        rows = self._connection.execute(
            "SELECT * FROM incidents ORDER BY created_at, id"
        ).fetchall()
        return [_from_row(row) for row in rows]

    def update(self, incident: Incident) -> Incident:
        self._ensure_schema()
        if incident.id is None:
            raise ValueError("update requiere una incidencia con id.")
        with self._connection:
            stored = self.get(incident.id)
            if stored is None:
                raise IncidentNotFoundError(f"Incidencia inexistente: {incident.id}.")
            if incident.created_at != stored.created_at:
                raise ValueError("created_at no se puede modificar.")
            updated = replace(incident, updated_at=utc_now())
            assignments = ", ".join(f"{name}=?" for name in _FIELDS)
            cursor = self._connection.execute(
                f"UPDATE incidents SET {assignments}, updated_at=? WHERE id=?",
                _values(updated)
                + (
                    updated.updated_at.isoformat(timespec="microseconds"),
                    incident.id,
                ),
            )
            if cursor.rowcount != 1:
                raise IncidentNotFoundError(f"Incidencia inexistente: {incident.id}.")
        return updated

    def delete(self, incident_id: int) -> None:
        self._ensure_schema()
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM incidents WHERE id=?", (incident_id,)
            )
            if cursor.rowcount != 1:
                raise IncidentNotFoundError(f"Incidencia inexistente: {incident_id}.")
