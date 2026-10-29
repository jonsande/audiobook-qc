"""CLI mínima para capturar con las fuentes existentes y guardar en SQLite."""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from functools import partial

from audiobook_qc.capture import CaptureError, capture_incident
from audiobook_qc.capture_and_save import capture_and_save_incident
from audiobook_qc.captured_incident import IncidentType
from audiobook_qc.integrations import mpv, okular, selection
from audiobook_qc.sqlite_repository import SchemaError, SQLiteIncidentRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Captura y guarda una incidencia; requiere una base inicializada.",
        epilog="Inicialización: python -m audiobook_qc.incident_probe --db RUTA init",
    )
    parser.add_argument("--db", required=True, help="Ruta explícita de la base SQLite.")
    parser.add_argument("code", choices=[code.value for code in IncidentType])
    parser.add_argument("--mpv-socket", default=mpv.DEFAULT_SOCKET)
    parser.add_argument("--okular-service", help="Servicio explícito de Okular.")
    args = parser.parse_args(argv)
    capture = partial(
        capture_incident,
        read_primary=partial(selection.read_selection, "primary"),
        read_document=partial(okular.read_state, args.okular_service),
        read_audio=partial(mpv.read_state, args.mpv_socket),
    )
    try:
        with SQLiteIncidentRepository(args.db) as repository:
            incident = capture_and_save_incident(
                args.code, capture=capture, repository=repository
            )
    except CaptureError as exc:
        print(f"Error de captura: {exc}", file=sys.stderr)
        return 1
    except (sqlite3.Error, SchemaError, ValueError) as exc:
        print(f"Error al construir o guardar la incidencia: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(incident), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
