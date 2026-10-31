"""Conversión acotada y recuperable de siete órdenes; backend sustituible.

El llamador mantiene locks journal → trabajos. No se activan teclas ni fuentes.
El registro conserva intención y escrituras intentadas; la observación del backend
resuelve incluso una interrupción después del set y antes del siguiente fsync.
"""

import json
import re
import shlex
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Protocol

from audiobook_qc.integrations.gnome_shortcuts import (
    PATH_PATTERN,
    Shortcut,
    ShortcutError,
)
from audiobook_qc.migration_state import MigrationStateFile, durable_text, fingerprint
from audiobook_qc.shortcut_mode import BindingJournal, SavedBinding
from audiobook_qc.type_config import (
    EditorialConfiguration,
    parse_types,
    types_data,
    unique_object,
)

INITIAL_IDS = ("TEXT", "PRON", "DICC", "RUID", "RESP", "INTER", "OTRO")


class CommandBackend(Protocol):
    def paths(self) -> list[str]: ...
    def read(self, path: str) -> Shortcut: ...
    def write_command(self, expected: Shortcut, command: str) -> None: ...


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ShortcutError(message)


def commands(interpreter: str) -> tuple[tuple[str, str], ...]:
    require(
        isinstance(interpreter, str)
        and Path(interpreter).is_absolute()
        and re.fullmatch(r"python[0-9.]*", Path(interpreter).name) is not None,
        "Indica la ruta absoluta del intérprete Python original.",
    )
    base = [interpreter, "-m", "audiobook_qc.capture_save_probe", "--desktop"]
    return tuple(
        (shlex.join([*base, code]), shlex.join([*base, "--hotkey", f"F{i}"]))
        for i, code in enumerate(INITIAL_IDS, 1)
    )


def decode_plan(plan: dict) -> tuple[list[Shortcut], dict[str, SavedBinding]]:
    """Valida también el registro persistido antes de autorizar recuperación."""
    try:
        require(
            set(plan) == {"interpreter", "entries", "journal_before", "catalog"},
            "Campos de plan desconocidos.",
        )
        pairs = commands(plan["interpreter"])
        require(isinstance(plan["entries"], list), "Entradas inválidas.")
        entries = [Shortcut(**row) for row in plan["entries"]]
        require(
            all(
                isinstance(e.path, str)
                and PATH_PATTERN.fullmatch(e.path)
                and all(isinstance(v, str) for v in (e.name, e.command, e.binding))
                for e in entries
            )
            and len({e.path for e in entries}) == len(entries),
            "Rutas/propiedades ambiguas.",
        )
        own = [e for e in entries if e.owned]
        require(
            len(own) == 7 and all(not e.binding for e in own),
            "Siete bindings vacíos requeridos.",
        )
        require(
            {e.command for e in own} == {old for old, _ in pairs},
            "Comandos originales inesperados.",
        )
        raw = json.loads(plan["journal_before"], object_pairs_hook=unique_object)
        require(
            set(raw) == {"version", "entries"}
            and type(raw["version"]) is int
            and raw["version"] == 1,
            "Journal incompatible.",
        )
        records = {p: SavedBinding(**row) for p, row in raw["entries"].items()}
        require(
            set(records) == {e.path for e in own},
            "Journal incompleto o con entradas adicionales.",
        )
        for i, (old, _) in enumerate(pairs, 1):
            e = next(e for e in own if e.command == old)
            require(
                records[e.path] == SavedBinding(old, f"F{i}", True)
                and type(records[e.path].suspended) is bool,
                "Comando/binding suspendido incompatible.",
            )
        catalog = parse_types(json.dumps(plan["catalog"]))
        require(
            all(
                catalog.resolve_hotkey(f"F{i}") == code
                for i, code in enumerate(INITIAL_IDS, 1)
            ),
            "Mapa inicial F1–F7 requerido.",
        )
        return entries, records
    except (ValueError, TypeError, KeyError, StopIteration, AttributeError) as exc:
        raise ShortcutError(f"Plan/journal inválido: {exc}") from exc


class CommandMigration:
    def __init__(
        self,
        backend: CommandBackend,
        journal: BindingJournal,
        read_active: Callable[[], bool],
        read_catalog: Callable[[], EditorialConfiguration],
        state: MigrationStateFile | None = None,
    ) -> None:
        self.backend, self.journal = backend, journal
        self.read_active, self.read_catalog = read_active, read_catalog
        self.state = state or MigrationStateFile(journal.path)

    def _snapshot(self) -> list[Shortcut]:
        paths = self.backend.paths()
        require(len(paths) == len(set(paths)), "Rutas duplicadas.")
        return [self.backend.read(p) for p in paths]

    def plan(self, interpreter: str) -> dict:
        require(
            self.state.load() is None,
            "Ya hay un registro de migración; consulta status/recover.",
        )
        require(not self.read_active(), "Modo activo; no se migra.")
        require(not self.journal.path.is_symlink(), "Journal enlazado.")
        # load valida el adaptador ordinario; decode_plan añade duplicados y alcance.
        self.journal.load()
        plan = dict(
            interpreter=interpreter,
            entries=[asdict(e) for e in self._snapshot()],
            journal_before=self.journal.path.read_text(encoding="utf-8"),
            catalog=types_data(self.read_catalog()),
        )
        decode_plan(plan)
        self._observe(plan, set())
        return dict(token=fingerprint(plan), plan=plan)

    def _targets(self, plan: dict) -> list[tuple[Shortcut, Shortcut]]:
        entries, _ = decode_plan(plan)
        return [
            (e, replace(e, command=new))
            for old, new in commands(plan["interpreter"])
            for e in entries
            if e.command == old
        ]

    def _journal_after(self, plan: dict) -> str:
        _, records = decode_plan(plan)
        for old, new in self._targets(plan):
            records[old.path] = replace(records[old.path], command=new.command)
        return json.dumps(
            dict(version=1, entries={p: asdict(v) for p, v in records.items()}),
            ensure_ascii=False,
            indent=2,
        )

    def _observe(
        self, plan: dict, allowed_new: set[int], *, recovery: bool = False
    ) -> list[Shortcut]:
        require(
            not self.read_active(), "Modo activado durante la operación; detenerse."
        )
        # Recovery does not depend on a catalog that might now be broken.
        if not recovery:
            require(
                types_data(self.read_catalog()) == plan["catalog"],
                "El catálogo cambió.",
            )
        entries, _ = decode_plan(plan)
        current = self._snapshot()
        require(
            [e.path for e in current] == [e.path for e in entries],
            "Lista de atajos cambiada.",
        )
        targets = {
            old.path: (i, old, new) for i, (old, new) in enumerate(self._targets(plan))
        }
        for e, original in zip(current, entries):
            choices = [original]
            if e.path in targets and targets[e.path][0] in allowed_new:
                choices.append(targets[e.path][2])
            require(
                e in choices,
                f"Cambio concurrente/inesperado en {e.path}; no se sobrescribe.",
            )
        require(not self.journal.path.is_symlink(), "Journal enlazado.")
        text = self.journal.path.read_text(encoding="utf-8")
        journal_options = [plan["journal_before"]]
        if allowed_new == set(range(7)):
            journal_options.append(self._journal_after(plan))
        require(
            text in journal_options,
            "Journal cambió fuera de la migración; no se sobrescribe.",
        )
        return current

    def apply(self, interpreter: str, token: str) -> dict:
        proposed = self.plan(interpreter)
        require(
            token == proposed["token"], "Huella del plan distinta; vuelve a validar."
        )
        plan = proposed["plan"]
        data = dict(version=1, plan=plan, token=token, phase="prepared", attempted=[])
        self.state.save(data, exclusive=True)  # fsync antes del primer set
        try:
            for i, (old, new) in enumerate(self._targets(plan)):
                observed = self._observe(plan, set(data["attempted"]))
                require(old in observed, "Entrada ya cambiada antes de su intento.")
                data["phase"] = "commands"
                data["attempted"].append(i)
                self.state.save(data)  # intención por entrada ANTES del set
                self.backend.write_command(old, new.command)
                self._observe(plan, set(data["attempted"]))
            require(
                self._snapshot() == self._expected_new(plan),
                "Comandos nuevos no confirmados.",
            )
            data["phase"] = "journal"
            self.state.save(data)
            self._observe(plan, set(range(7)))
            durable_text(self.journal.path, self._journal_after(plan))
            self._observe(plan, set(range(7)))
            require(
                self._snapshot() == self._expected_new(plan),
                "Escritorio cambió antes de confirmar.",
            )
            require(
                self.journal.path.read_text(encoding="utf-8")
                == self._journal_after(plan),
                "Journal nuevo no confirmado.",
            )
            data["phase"] = "complete"
            self.state.save(data)
        except (OSError, ShortcutError) as exc:
            raise ShortcutError(
                "Migración incompleta; conserva el registro y usa status/recover: "
                f"{exc}"
            ) from exc
        return self.status()

    def _expected_new(self, plan: dict) -> list[Shortcut]:
        replacements = {old.path: new for old, new in self._targets(plan)}
        entries, _ = decode_plan(plan)
        return [replacements.get(e.path, e) for e in entries]

    def recover(self, token: str) -> dict:
        data = self.state.load()
        require(data is not None, "No hay intención que recuperar.")
        require(token == data["token"], "Huella de recuperación incorrecta.")
        plan = data["plan"]
        decode_plan(plan)
        require(data["phase"] != "rolled_back", "Recuperación ya completada.")
        # No se escribe nada externo si una entrada/journal/lista no es reconocible.
        self._observe(plan, set(data["attempted"]), recovery=True)
        data["phase"] = "recovering"
        self.state.save(data)
        try:
            for old, new in reversed(self._targets(plan)):
                observed = self._observe(plan, set(data["attempted"]), recovery=True)
                if new in observed:
                    self.backend.write_command(new, old.command)
            self._observe(plan, set(data["attempted"]), recovery=True)
            if self.journal.path.read_text(encoding="utf-8") != plan["journal_before"]:
                durable_text(self.journal.path, plan["journal_before"])
            require(
                self._snapshot() == decode_plan(plan)[0], "Recuperación no confirmada."
            )
            self._observe(plan, set(), recovery=True)
            require(
                self.journal.path.read_text(encoding="utf-8") == plan["journal_before"],
                "Journal anterior no confirmado.",
            )
            data["phase"] = "rolled_back"
            self.state.save(data)
        except (OSError, ShortcutError) as exc:
            raise ShortcutError(
                "Recuperación parcial; registro conservado, vuelve a diagnosticar: "
                f"{exc}"
            ) from exc
        return self.status()

    def status(self) -> dict:
        data = self.state.load()
        if data is None:
            return dict(phase="absent", pending=False)
        plan = data["plan"]
        decode_plan(plan)
        try:
            observed = self._observe(plan, set(data["attempted"]), recovery=True)
        except (OSError, ShortcutError) as exc:
            return dict(
                phase=data["phase"],
                pending=True,
                coherent=False,
                token=data["token"],
                attempted=data["attempted"],
                error=str(exc),
            )
        new = self._expected_new(plan)
        if data["phase"] == "complete":
            require(
                observed == new
                and self.journal.path.read_text(encoding="utf-8")
                == self._journal_after(plan),
                "Estado complete no coincide con escritorio/journal.",
            )
        if data["phase"] == "rolled_back":
            require(
                observed == decode_plan(plan)[0]
                and self.journal.path.read_text(encoding="utf-8")
                == plan["journal_before"],
                "Estado rolled_back no coincide.",
            )
        return dict(
            phase=data["phase"],
            pending=data["phase"] not in ("complete", "rolled_back"),
            coherent=True,
            token=data["token"],
            attempted=data["attempted"],
            changed=[
                e.path for e in observed if e in [n for _, n in self._targets(plan)]
            ],
        )
