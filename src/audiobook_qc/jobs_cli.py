"""Gestión explícita de trabajos y configuración persistente, sin GUI."""

import argparse
import json
import sqlite3
import sys

from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.job_sources import (
    SourceError,
    launch_mpv,
    launch_okular,
    set_document,
    sources_data,
)
from audiobook_qc.jobs import JobError, JobStore, job_data
from audiobook_qc.sqlite_repository import SchemaError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestiona trabajos de corrección.")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("configure").add_argument("directory")
    commands.add_parser("config")
    commands.add_parser("create").add_argument("name")
    commands.add_parser("list")
    commands.add_parser("get").add_argument("id")
    commands.add_parser("migrate-types").add_argument("id")
    commands.add_parser("select").add_argument("id")
    commands.add_parser("active")
    commands.add_parser("clear")
    commands.add_parser("sources").add_argument("id")
    pdf = commands.add_parser("set-pdf")
    pdf.add_argument("id")
    pdf.add_argument("document")
    audio = commands.add_parser(
        "launch-mpv",
        help="Abre capítulos desde archivos o carpetas de audio.",
        description=(
            "Acepta archivos y carpetas mezclados. Expande cada carpeta sin "
            "subcarpetas, con orden natural (1, 2, 10), y elimina duplicados. "
            "Sin rutas, reutiliza la lista concreta guardada."
        ),
    )
    audio.add_argument("id")
    audio.add_argument(
        "files",
        nargs="*",
        metavar="RUTA",
        help="Archivos o carpetas de audio, en el orden deseado.",
    )
    commands.add_parser("launch-okular").add_argument("id")
    args = parser.parse_args(argv)
    try:
        store = JobStore()
        if args.action in ("sources", "set-pdf", "launch-mpv", "launch-okular"):
            with store.job_context(args.id) as job:
                if args.action == "set-pdf":
                    set_document(job, args.document)
                    result = sources_data(job)
                elif args.action == "launch-mpv":
                    result = launch_mpv(job, args.files)
                elif args.action == "launch-okular":
                    result = launch_okular(job)
                else:
                    result = sources_data(job)
        elif args.action == "migrate-types":
            with store.destination(args.id) as (job, repository):
                result = dict(
                    job=job.id, migrated=repository.migrate_types(), version=2
                )
        elif args.action == "configure":
            store.configure(args.directory)
            result = store.configuration()
        elif args.action == "config":
            result = store.configuration()
        elif args.action == "create":
            result = job_data(store.create(args.name))
        elif args.action == "list":
            result = [job_data(job) for job in store.list()]
        elif args.action == "get":
            result = job_data(store.get(args.id))
        elif args.action == "select":
            store.select(args.id)
            result = {"active": args.id}
        elif args.action == "clear":
            store.select(None)
            result = {"active": None}
        else:
            result = job_data(store.active())
    except (
        JobError,
        SourceError,
        ActivationBusy,
        OSError,
        sqlite3.Error,
        SchemaError,
    ) as exc:
        print(f"Error de trabajos: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
