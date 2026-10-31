"""Estado duradero de migración; no contiene operaciones de escritorio."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from audiobook_qc.integrations.gnome_shortcuts import ShortcutError
from audiobook_qc.type_config import unique_object

PHASES = {"prepared", "commands", "journal", "complete", "recovering", "rolled_back"}


def fingerprint(plan: dict) -> str:
    return hashlib.sha256(
        json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def durable_text(path: Path, text: str, *, exclusive: bool = False) -> None:
    """Publica contenido completo privado y sincroniza archivo/directorio."""
    if path.is_symlink():
        raise ShortcutError(f"No se escribe un enlace: {path}")
    fd, name = tempfile.mkstemp(prefix=".migration-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            temporary.replace(path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class MigrationStateFile:
    def __init__(self, journal_path: Path) -> None:
        self.path = journal_path.with_suffix(".migration.json")
        self._expected: str | None = None

    def load(self) -> dict | None:
        try:
            if self.path.is_symlink():
                raise ValueError("estado enlazado")
            text = self.path.read_text(encoding="utf-8")
            data = json.loads(text, object_pairs_hook=unique_object)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, UnicodeError) as exc:
            raise ShortcutError(f"Estado de migración ilegible: {exc}") from exc
        try:
            if (
                set(data) != {"version", "plan", "token", "phase", "attempted"}
                or type(data["version"]) is not int
                or data["version"] != 1
                or data["phase"] not in PHASES
                or not isinstance(data["plan"], dict)
                or data["token"] != fingerprint(data["plan"])
                or not isinstance(data["attempted"], list)
                or any(type(i) is not int for i in data["attempted"])
                or data["attempted"] != list(range(len(data["attempted"])))
                or len(data["attempted"]) > 7
                or (
                    data["phase"] in ("journal", "complete")
                    and len(data["attempted"]) != 7
                )
                or (data["phase"] == "prepared" and data["attempted"])
            ):
                raise ValueError("estructura/huella/progreso inválidos")
        except (TypeError, KeyError, ValueError) as exc:
            raise ShortcutError(f"Estado de migración inválido: {exc}") from exc
        self._expected = text
        return data

    def save(self, data: dict, *, exclusive: bool = False) -> None:
        if not exclusive and (
            self.path.is_symlink()
            or self._expected is None
            or self.path.read_text(encoding="utf-8") != self._expected
        ):
            raise ShortcutError("El registro de migración cambió; no se sobrescribe.")
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        durable_text(self.path, text, exclusive=exclusive)
        self._expected = text

    def ensure_idle(self) -> None:
        data = self.load()
        if data is not None:
            # Importación local: el controlador ordinario no depende del núcleo
            # de migración hasta que existe un registro que hay que validar.
            from audiobook_qc.shortcut_migration import decode_plan

            decode_plan(data["plan"])
        if data is not None and data["phase"] not in ("complete", "rolled_back"):
            raise ShortcutError(
                "Migración pendiente; usa shortcut_migration_cli status/recover. "
                "No se cambia el modo ni el journal."
            )
