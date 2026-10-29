"""CLI mínima para capturar con las fuentes existentes y guardar en SQLite."""

import argparse
import json
import sqlite3
import sys
from contextlib import nullcontext
from dataclasses import asdict
from functools import partial
from pathlib import Path

from audiobook_qc.capture import CaptureError, capture_incident
from audiobook_qc.capture_and_save import capture_and_save_incident
from audiobook_qc.captured_incident import IncidentType
from audiobook_qc.correction_mode import ModeError, is_active
from audiobook_qc.desktop_policy import ActivationRejected, require_correction_context
from audiobook_qc.integrations import mpv, okular, selection
from audiobook_qc.integrations.activation import ActivationBusy, activation_guard
from audiobook_qc.integrations.focus import FocusError, active_application
from audiobook_qc.integrations.notifications import NotificationError, notify
from audiobook_qc.sqlite_repository import SchemaError, SQLiteIncidentRepository


def _notify(summary: str, body: str, *, error: bool = False) -> None:
    """Un fallo de presentación no cambia el resultado de captura/persistencia."""
    try:
        notify(summary, body, error=error)
    except NotificationError as exc:
        print(f"{summary}: {body}. Aviso de notificación: {exc}", file=sys.stderr)


def check_desktop_activation() -> None:
    require_correction_context(mode_active=is_active, active_app=active_application)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Captura y guarda una incidencia; requiere una base inicializada.",
        epilog="Inicialización: python -m audiobook_qc.incident_probe --db RUTA init",
    )
    parser.add_argument("--db", required=True, help="Ruta explícita de la base SQLite.")
    parser.add_argument("code", choices=[code.value for code in IncidentType])
    parser.add_argument("--mpv-socket", default=mpv.DEFAULT_SOCKET)
    parser.add_argument("--okular-service", help="Servicio explícito de Okular.")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Exige modo activo y foco autorizado; notifica y evita solapamientos.",
    )
    args = parser.parse_args(argv)
    capture = partial(
        capture_incident,
        read_primary=partial(selection.read_selection, "primary"),
        read_document=partial(okular.read_state, args.okular_service),
        read_audio=partial(mpv.read_state, args.mpv_socket),
    )
    try:
        if args.desktop and (
            not Path(args.db).is_absolute() or not Path(args.mpv_socket).is_absolute()
        ):
            raise ValueError(
                "El modo --desktop requiere rutas absolutas para --db y --mpv-socket."
            )
        if args.desktop:
            check_desktop_activation()
        guard = activation_guard(args.db) if args.desktop else nullcontext()
        with guard, SQLiteIncidentRepository(args.db) as repository:
            incident = capture_and_save_incident(
                args.code, capture=capture, repository=repository
            )
    except (ActivationRejected, ModeError, FocusError) as exc:
        print(f"Activación rechazada: {exc}", file=sys.stderr)
        _notify("Activación rechazada", str(exc))
        return 1
    except ActivationBusy as exc:
        print(str(exc), file=sys.stderr)
        if args.desktop:
            _notify("Activación omitida", str(exc), error=True)
        return 1
    except CaptureError as exc:
        print(f"Error de captura: {exc}", file=sys.stderr)
        if args.desktop:
            _notify("Incidencia no guardada", f"{args.code}: {exc}", error=True)
        return 1
    except (sqlite3.Error, SchemaError, ValueError, OSError) as exc:
        print(f"Error al construir o guardar la incidencia: {exc}", file=sys.stderr)
        if args.desktop:
            _notify("Incidencia no guardada", f"{args.code}: {exc}", error=True)
        return 1
    print(json.dumps(asdict(incident), ensure_ascii=False, default=str))
    if args.desktop:
        _notify(
            "Incidencia guardada", f"{incident.incident_type.value} · ID {incident.id}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
