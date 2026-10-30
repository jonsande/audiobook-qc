"""Revisión humana o JSON de incidencias, siempre dentro de un trabajo explícito."""

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict

from audiobook_qc.audio_position import format_audio_position
from audiobook_qc.captured_incident import IncidentType
from audiobook_qc.description_config import load_catalog
from audiobook_qc.incident import Incident
from audiobook_qc.incident_review import EDITABLE_FIELDS, edit_incident, get_incident
from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.jobs import JobError, JobStore
from audiobook_qc.sqlite_repository import IncidentNotFoundError, SchemaError


def _positive_id(value: str) -> int:
    try:
        number = int(value)
        if number <= 0:
            raise ValueError
        return number
    except ValueError as exc:
        raise argparse.ArgumentTypeError("El ID debe ser un entero positivo.") from exc


def incident_data(incident: Incident) -> dict:
    data = asdict(incident)
    data["incident_type"] = incident.incident_type.value
    for name in ("created_at", "updated_at"):
        data[name] = getattr(incident, name).isoformat(timespec="microseconds")
    return dict(
        data,
        audio_position_formatted=format_audio_position(incident.audio_position_seconds),
        editorially_complete=incident.editorially_complete,
        editorial_description_preview=incident.compose_editorial_description(
            separator="\n"
        ),
    )


def _summary(value: str | None, limit: int = 64) -> str:
    text = "NULL" if value is None else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _human(result: dict) -> str:
    header = f"Trabajo: {result['job']['name']} ({result['job']['id']})"
    if "incidents" in result:
        rows = [
            header,
            "ID | Tipo | Audio | Posición | Página | Texto | "
            "generic_description | custom_comment | exported | Completa",
        ]
        for item in result["incidents"]:
            rows.append(
                " | ".join(
                    (
                        str(item["id"]),
                        item["incident_type"],
                        _summary(item["audio_filename"]),
                        item["audio_position_formatted"],
                        str(item["page"]),
                        _summary(item["selected_text"]),
                        _summary(item["generic_description"]),
                        _summary(item["custom_comment"]),
                        "sí" if item["exported"] else "no",
                        "sí" if item["editorially_complete"] else "no",
                    )
                )
            )
        if not result["incidents"]:
            rows.append("Sin incidencias.")
        return "\n".join(rows)
    rows = [header]
    for name, value in result["incident"].items():
        if value is None:
            text = "NULL"
        elif isinstance(value, str):
            # JSON literal permite ver espacios, CR/LF y cadenas vacías.
            text = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            text = "sí" if value else "no"
        else:
            text = str(value)
        rows.append(f"{name}: {text}")
    return "\n".join(rows)


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--job",
        default=argparse.SUPPRESS,
        help="UUID del trabajo; por defecto utiliza el seleccionado.",
    )
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Salida estructurada completa, sin resumir textos.",
    )
    parser = argparse.ArgumentParser(
        description="Consulta y edita incidencias por trabajo.", parents=[common]
    )
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("list", parents=[common], help="Lista por creación e ID.")
    get = commands.add_parser(
        "get", parents=[common], help="Consulta todos los campos."
    )
    get.add_argument("id", type=_positive_id)
    edit = commands.add_parser(
        "edit", parents=[common], help="Edita solo los campos indicados."
    )
    edit.add_argument("id", type=_positive_id)
    edit.add_argument(
        "--type",
        dest="incident_type",
        choices=[c.value for c in IncidentType],
        default=argparse.SUPPRESS,
    )
    edit.add_argument(
        "--position",
        dest="audio_position_seconds",
        type=float,
        default=argparse.SUPPRESS,
        help="Segundos nativos, sin redondear.",
    )
    edit.add_argument("--document", default=argparse.SUPPRESS)
    edit.add_argument("--page", type=int, default=argparse.SUPPRESS)
    edit.add_argument("--selected-text", default=argparse.SUPPRESS)
    for field, options, clear in (
        (
            "generic_description",
            ("--generic-description",),
            ("--clear-generic-description",),
        ),
        (
            "custom_comment",
            ("--comment", "--custom-comment"),
            ("--clear-comment", "--clear-custom-comment"),
        ),
    ):
        group = edit.add_mutually_exclusive_group()
        if field == "generic_description":
            group.add_argument("--generic-description-id", default=argparse.SUPPRESS)
        group.add_argument(
            *options,
            dest=field,
            default=argparse.SUPPRESS,
            help="Texto exacto; permite cadena vacía.",
        )
        group.add_argument(
            *clear,
            dest=field,
            action="store_const",
            const=None,
            default=argparse.SUPPRESS,
            help="Establece NULL explícitamente.",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    changes = {
        key: value for key, value in vars(args).items() if key in EDITABLE_FIELDS
    }
    description_id = getattr(args, "generic_description_id", None)
    if args.action == "edit" and not changes and description_id is None:
        parser.error("Indica al menos un campo editable.")
    try:
        with JobStore().destination(getattr(args, "job", None)) as (job, repository):
            result = {"job": {"id": job.id, "name": job.name}}
            if args.action == "list":
                result["incidents"] = [
                    incident_data(item) for item in repository.list()
                ]
            else:
                incident = (
                    edit_incident(
                        repository,
                        args.id,
                        changes,
                        catalog=load_catalog() if description_id is not None else None,
                        description_id=description_id,
                    )
                    if args.action == "edit"
                    else get_incident(repository, args.id)
                )
                result["incident"] = incident_data(incident)
    except (
        JobError,
        ActivationBusy,
        ValueError,
        OSError,
        sqlite3.Error,
        SchemaError,
        IncidentNotFoundError,
    ) as exc:
        print(f"Error de revisión: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(result, ensure_ascii=False, allow_nan=False)
        if getattr(args, "json", False)
        else _human(result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
