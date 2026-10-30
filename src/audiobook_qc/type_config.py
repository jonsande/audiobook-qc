"""Configuración XDG de tipos y atajos; instalación explícita sin sobrescritura."""

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path

from audiobook_qc.type_catalog import (
    IncidentTypeDefinition,
    TypeCatalog,
    TypeConfigError,
)


@dataclass(frozen=True)
class EditorialConfiguration(TypeCatalog):
    """Instantánea del adaptador: añade atajos al catálogo puro de tipos."""

    hotkeys: tuple[tuple[str, str | None], ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.hotkeys, tuple):
            raise TypeConfigError("hotkeys debe ser inmutable.")
        keys = []
        for binding in self.hotkeys:
            if not isinstance(binding, tuple) or len(binding) != 2:
                raise TypeConfigError("Asociación de atajo inválida.")
            key, identifier = binding
            if not isinstance(key, str) or not re.fullmatch(r"F[1-7]", key):
                raise TypeConfigError(f"Atajo lógico inválido: {key!r}; usa F1–F7.")
            keys.append(key)
            if identifier is not None:
                self.require_enabled(identifier)
        if len(set(keys)) != len(keys):
            raise TypeConfigError("Atajos duplicados.")

    def resolve_hotkey(self, hotkey: str) -> str:
        identifier = dict(self.hotkeys).get(hotkey)
        if identifier is None:
            raise TypeConfigError(f"Atajo {hotkey} sin asignación.")
        return self.require_enabled(identifier).id


def types_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    if not root.is_absolute():
        raise TypeConfigError("XDG_CONFIG_HOME debe ser absoluto.")
    return root / "audiobook-qc/incident_types.json"


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clave JSON duplicada: {key}.")
        result[key] = value
    return result


def parse_types(raw: str) -> EditorialConfiguration:
    data = json.loads(raw, object_pairs_hook=unique_object)
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "types", "hotkeys"}
        or type(data["version"]) is not int
        or data["version"] != 1
        or not isinstance(data["types"], list)
        or not isinstance(data["hotkeys"], dict)
    ):
        raise TypeConfigError("Se requiere version: 1, types: lista y hotkeys: objeto.")
    entries = []
    for item in data["types"]:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "label",
            "enabled",
            "default_generic_description",
        }:
            raise TypeConfigError("Cada tipo requiere id, label, enabled y fórmula.")
        entries.append(IncidentTypeDefinition(**item))
    return EditorialConfiguration(tuple(entries), tuple(data["hotkeys"].items()))


def load_types(path: Path | None = None) -> EditorialConfiguration:
    target = path if path is not None else types_path()
    try:
        return parse_types(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise TypeConfigError(
            f"Configuración de tipos {target}: {exc}. "
            "Consulta types_cli validate; "
            "para instalar por primera vez: types_cli init."
        ) from exc


def types_data(catalog: EditorialConfiguration) -> dict:
    return dict(
        version=1,
        types=[asdict(item) for item in catalog.types],
        hotkeys=dict(catalog.hotkeys),
    )


def install_initial_types() -> Path:
    """Publica un archivo completo usando link exclusivo, incluso entre procesos."""
    target = types_path()
    raw = files("audiobook_qc").joinpath("data/incident_types.json").read_bytes()
    parse_types(raw.decode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".incident_types-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(name, target)  # falla si existe; nunca sigue/sobrescribe un symlink
    finally:
        os.unlink(name)
    return target
