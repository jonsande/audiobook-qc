"""Sincronización recuperable del modo y los bindings propios, sin daemon."""

import fcntl
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Protocol

from audiobook_qc.integrations.gnome_shortcuts import (
    PATH_PATTERN,
    Shortcut,
    ShortcutError,
)


class Bindings(Protocol):
    def paths(self) -> list[str]: ...
    def read(self, path: str) -> Shortcut: ...
    def write_binding(self, expected: Shortcut, binding: str) -> None: ...


@dataclass(frozen=True)
class SavedBinding:
    command: str
    binding: str
    suspended: bool


class BindingJournal:
    def __init__(self, path: Path | None = None) -> None:
        root = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
        if not root.is_absolute():
            raise ShortcutError("XDG_STATE_HOME debe ser absoluto.")
        self.path = path or root / "audiobook-qc/gnome-bindings.json"

    def load(self) -> dict[str, SavedBinding]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, UnicodeError, ValueError) as exc:
            raise ShortcutError(
                f"No se pudo leer la copia de combinaciones: {exc}"
            ) from exc
        try:
            if (
                set(data) != {"version", "entries"}
                or type(data["version"]) is not int
                or data["version"] != 1
            ):
                raise ValueError("versión desconocida")
            records = {}
            for path, record in data["entries"].items():
                if not PATH_PATTERN.fullmatch(path) or set(record) != {
                    "command",
                    "binding",
                    "suspended",
                }:
                    raise ValueError("registro inválido")
                if (
                    not isinstance(record["command"], str)
                    or not isinstance(record["binding"], str)
                    or type(record["suspended"]) is not bool
                ):
                    raise ValueError("tipos inválidos")
                records[path] = SavedBinding(**record)
            return records
        except (TypeError, AttributeError, ValueError) as exc:
            raise ShortcutError(
                "Copia de combinaciones inválida; no se sobrescribe."
            ) from exc

    def save(self, records: dict[str, SavedBinding]) -> None:
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(
                    dict(
                        version=1,
                        entries={
                            path: asdict(record) for path, record in records.items()
                        },
                    ),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
            descriptor = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as exc:
            raise ShortcutError(
                f"No se pudo guardar la copia de combinaciones: {exc}"
            ) from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.path.with_suffix(".lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ShortcutError(
                    "Hay otro cambio de modo en curso; vuelve a intentarlo."
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


class ShortcutMode:
    def __init__(
        self,
        backend: Bindings,
        journal: BindingJournal,
        set_mode: Callable[[bool], None],
    ) -> None:
        self.backend, self.journal, self.set_mode = backend, journal, set_mode

    def _entries(
        self, errors: list[str], *, include_foreign: bool = False
    ) -> list[Shortcut]:
        try:
            paths = self.backend.paths()
        except ShortcutError as exc:
            errors.append(str(exc))
            return []
        entries = []
        for path in paths:
            try:
                entry = self.backend.read(path)
                if entry.owned or include_foreign:
                    entries.append(entry)
            except ShortcutError as exc:
                errors.append(f"{path}: {exc}")
        return entries

    @staticmethod
    def _desired(entry: Shortcut, previous: SavedBinding | None) -> str:
        if entry.binding:
            return entry.binding  # Una combinación manual nueva tiene prioridad.
        if previous and previous.suspended:
            if previous.command != entry.command:
                raise ShortcutError(
                    f"{entry.path}: comando cambiado; asigna la combinación en GNOME."
                )
            return previous.binding
        return ""  # Desactivado manualmente, o entrada nueva vacía.

    def off(self) -> None:
        errors: list[str] = []
        try:
            self.set_mode(False)  # Nunca seguir capturando mientras se liberan teclas.
        except (ShortcutError, OSError) as exc:
            errors.append(f"No se pudo desactivar el indicador de modo: {exc}")
        try:
            records = self.journal.load()
        except ShortcutError as exc:
            errors.append(str(exc))
            records = None  # Conservar la copia dañada; liberar aun así las teclas.
        for entry in self._entries(errors):
            try:
                if records is not None:
                    try:
                        desired = self._desired(entry, records.get(entry.path))
                    except ShortcutError as exc:
                        errors.append(str(exc))
                        desired = ""
                    records[entry.path] = SavedBinding(entry.command, desired, True)
                    self.journal.save(records)  # Antes de cambiar GSettings.
                elif entry.binding:
                    errors.append(
                        f"Restauración manual: {entry.path} = {entry.binding!r}"
                    )
            except ShortcutError as exc:
                errors.append(f"{exc}; copia manual: {entry.path} = {entry.binding!r}")
            if entry.binding:
                try:
                    self.backend.write_binding(entry, "")
                except ShortcutError as exc:
                    errors.append(f"{entry.path}: {exc}")
        if errors:
            raise ShortcutError(
                "Desactivación/liberación con incidencias; consulta status: "
                + " | ".join(errors)
            )

    def on(self) -> None:
        self.set_mode(False)
        try:
            records = self.journal.load()
            errors: list[str] = []
            all_entries = self._entries(errors, include_foreign=True)
            entries = [entry for entry in all_entries if entry.owned]
            if errors:
                raise ShortcutError(" | ".join(errors))
            desired = {
                entry.path: self._desired(entry, records.get(entry.path))
                for entry in entries
            }
            if not any(desired.values()):
                raise ShortcutError(
                    "No hay combinaciones propias configuradas para activar."
                )
            nonempty = [value for value in desired.values() if value]
            foreign = {
                entry.binding
                for entry in all_entries
                if not entry.owned and entry.binding
            }
            if foreign.intersection(nonempty):
                raise ShortcutError(
                    "Combinación asignada a otro atajo personal; no se restaura."
                )
            if len(set(nonempty)) != len(nonempty):
                raise ShortcutError(
                    "Hay combinaciones propias duplicadas; corrígelas en GNOME."
                )
            # Registrar antes de habilitar; conservar suspended hasta confirmar el set.
            for entry in entries:
                records[entry.path] = SavedBinding(
                    entry.command, desired[entry.path], not bool(entry.binding)
                )
            self.journal.save(records)
            for entry in entries:
                target = desired[entry.path]
                if entry.binding != target:
                    self.backend.write_binding(entry, target)
                elif self.backend.read(entry.path) != entry:
                    raise ShortcutError(
                        "La configuración cambió durante la activación."
                    )
                records[entry.path] = SavedBinding(entry.command, target, False)
                self.journal.save(records)
            confirmed = self._entries(errors, include_foreign=True)
            expected = {
                entry.path: replace(entry, binding=desired[entry.path])
                for entry in entries
            }
            actual = {entry.path: entry for entry in confirmed if entry.owned}
            conflicts = {
                entry.binding
                for entry in confirmed
                if not entry.owned and entry.binding
            }
            if errors or actual != expected or conflicts.intersection(nonempty):
                raise ShortcutError(
                    "No se han podido confirmar todas las combinaciones."
                )
            # Solo después de restauración y verificación completas.
            self.set_mode(True)
        except (ShortcutError, OSError):
            try:
                self.off()
            except (ShortcutError, OSError) as cleanup:
                raise ShortcutError(
                    f"Activación fallida; recuperación parcial: {cleanup}"
                )
            raise

    def status(self, active: bool) -> tuple[str, bool]:
        records = self.journal.load()
        errors: list[str] = []
        entries = self._entries(errors)
        if errors:
            raise ShortcutError(" | ".join(errors))
        if active:
            enabled = [entry for entry in entries if entry.binding]
            synced = bool(enabled) and all(
                entry.path in records
                and records[entry.path]
                == SavedBinding(entry.command, entry.binding, False)
                for entry in entries
            )
        else:
            synced = not any(entry.binding for entry in entries)
        detail = (
            "sincronizados"
            if synced
            else "DESINCRONIZADOS; ejecuta off para liberar o revisa GNOME"
        )
        return (
            f"Modo de corrección {'activo' if active else 'inactivo'}; atajos {detail}",
            synced,
        )
