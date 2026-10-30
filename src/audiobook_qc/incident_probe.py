"""CLI mínima de persistencia con datos explícitos, sin consultar el entorno."""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict

from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.incident import Incident
from audiobook_qc.sqlite_repository import (
    IncidentNotFoundError,
    SchemaError,
    SQLiteIncidentRepository,
)
from audiobook_qc.type_config import load_types


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prueba explícita de persistencia SQLite."
    )
    parser.add_argument("--db", required=True, help="Ruta explícita de la base SQLite.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Inicializa el esquema de una base vacía.")
    add = commands.add_parser(
        "add", help="Lee por stdin los siete campos JSON de captura."
    )
    add.add_argument("--generic-description")
    add.add_argument("--custom-comment")
    get = commands.add_parser(
        "get", help="Recupera una incidencia en una nueva conexión."
    )
    get.add_argument("id", type=int)
    args = parser.parse_args(argv)
    try:
        with SQLiteIncidentRepository(args.db) as repository:
            if args.command == "init":
                repository.initialize()
                print("Esquema SQLite verificado (versiones 1/2; nuevas bases v2).")
                return 0
            if args.command == "add":
                payload = json.load(sys.stdin)
                required = {
                    "incident_type",
                    "audio_filename",
                    "audio_path",
                    "audio_position_seconds",
                    "document",
                    "page",
                    "selected_text",
                }
                if not isinstance(payload, dict) or set(payload) != required:
                    raise ValueError(
                        "Se requieren exactamente los siete campos de captura."
                    )
                incident = Incident.from_capture(
                    CapturedIncident(**payload),
                    generic_description=args.generic_description,
                    custom_comment=args.custom_comment,
                )
                load_types().require_enabled(incident.incident_type)
                incident = repository.add(incident)
            else:
                incident = repository.get(args.id)
                if incident is None:
                    raise IncidentNotFoundError(f"Incidencia inexistente: {args.id}.")
            print(json.dumps(asdict(incident), ensure_ascii=False, default=str))
    except (sqlite3.Error, SchemaError, IncidentNotFoundError, ValueError) as exc:
        print(f"Error de persistencia: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
