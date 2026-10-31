"""Plan, ejecución confirmada y recuperación de los siete comandos GNOME."""

import argparse
import json
import sys

from audiobook_qc.correction_mode import ModeError, is_active
from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.integrations.gnome_shortcuts import GSettingsShortcuts, ShortcutError
from audiobook_qc.jobs import JobError, JobStore
from audiobook_qc.shortcut_migration import CommandMigration
from audiobook_qc.shortcut_mode import BindingJournal
from audiobook_qc.type_config import load_types


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("plan", "apply"):
        command = actions.add_parser(name)
        command.add_argument("--interpreter", required=True)
        if name == "apply":
            command.add_argument(
                "--confirm", required=True, help="Huella del plan revisado."
            )
            command.add_argument("--execute", action="store_true")
    actions.add_parser("status")
    recovery = actions.add_parser("recover")
    recovery.add_argument("--confirm", required=True)
    recovery.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.action in ("apply", "recover") and not args.execute:
        parser.error("La escritura requiere --execute y --confirm HUELLA.")
    try:
        journal = BindingJournal()
        operation = CommandMigration(
            GSettingsShortcuts(), journal, is_active, load_types
        )
        # No se abre SQLite ni se consultan fuentes. jobs.lock excluye capturas
        # y cambios de selección de la aplicación, también durante recuperación.
        with journal.lock(), JobStore().lock():
            if args.action == "plan":
                result = operation.plan(args.interpreter)
            elif args.action == "apply":
                result = operation.apply(args.interpreter, args.confirm)
            elif args.action == "recover":
                result = operation.recover(args.confirm)
            else:
                result = operation.status()
    except (
        OSError,
        ValueError,
        ShortcutError,
        JobError,
        ModeError,
        ActivationBusy,
    ) as exc:
        print(f"Migración GNOME rechazada/incompleta: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("pending", False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
