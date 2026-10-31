"""Modo de corrección explícito por sesión de usuario/display, fuera de SQLite."""

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.integrations.gnome_shortcuts import GSettingsShortcuts, ShortcutError
from audiobook_qc.integrations.notifications import NotificationError, notify
from audiobook_qc.job_sources import SourceError, prepare_job_sources
from audiobook_qc.jobs import JobError, JobStore
from audiobook_qc.migration_state import MigrationStateFile
from audiobook_qc.shortcut_mode import BindingJournal, ShortcutMode


class ModeError(Exception):
    """El estado no se puede determinar con seguridad."""


def state_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    display = os.environ.get("DISPLAY", "")
    if not runtime or not Path(runtime).is_absolute() or not display:
        raise ModeError("Se requieren XDG_RUNTIME_DIR absoluto y DISPLAY para el modo.")
    display_id = hashlib.sha256(display.encode()).hexdigest()[:16]
    return Path(runtime) / "audiobook-qc" / f"correction-{display_id}.active"


def is_active() -> bool:
    try:
        content = state_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    except (OSError, UnicodeError) as exc:
        raise ModeError(f"No se pudo leer el modo de corrección: {exc}") from exc
    if content != "active\n":
        raise ModeError(
            "Estado de corrección inválido; desactívalo antes de continuar."
        )
    return True


def set_active(active: bool) -> None:
    path = state_path()
    if not active:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write("active\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def make_controller(journal: BindingJournal) -> ShortcutMode:
    def set_flag(active: bool) -> None:
        try:
            set_active(active)
        except (OSError, ModeError) as exc:
            raise ShortcutError(str(exc)) from exc

    return ShortcutMode(GSettingsShortcuts(), journal, set_flag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Control explícito del modo de corrección."
    )
    parser.add_argument("action", choices=("on", "off", "status"))
    parser.add_argument(
        "--notify", action="store_true", help="Muestra también un aviso."
    )
    args = parser.parse_args(argv)
    try:
        journal = BindingJournal()
        controller = make_controller(journal)
        with journal.lock():
            MigrationStateFile(journal.path).ensure_idle()
            if args.action == "on":
                # La selección no puede cambiar entre validación y modo activo.
                with JobStore().destination() as (job, _):
                    prepare_job_sources(job)
                    controller.on()
            elif args.action == "off":
                controller.off()
            message, synchronized = controller.status(is_active())
    except (
        ModeError,
        OSError,
        ShortcutError,
        JobError,
        SourceError,
        ActivationBusy,
    ) as exc:
        print(f"No se pudo controlar el modo de corrección: {exc}", file=sys.stderr)
        if args.notify:
            try:
                notify("Error de modo de corrección", str(exc), error=True)
            except NotificationError as notification_error:
                print(f"Aviso de notificación: {notification_error}", file=sys.stderr)
        return 1
    print(message)
    if args.notify:
        try:
            notify("audiobook-qc", message)
        except NotificationError as exc:
            print(f"{message}. Aviso de notificación: {exc}", file=sys.stderr)
    return 0 if synchronized else 1


if __name__ == "__main__":
    raise SystemExit(main())
