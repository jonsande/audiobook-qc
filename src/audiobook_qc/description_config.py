"""Lectura estricta de configuración global JSON; nunca escribe ni usa fallback."""

import json
import os
from pathlib import Path

from audiobook_qc.descriptions import (
    CatalogError,
    DescriptionCatalog,
    GenericDescription,
)
from audiobook_qc.type_catalog import TypeCatalog
from audiobook_qc.type_config import load_types


def catalog_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    if not root.is_absolute():
        raise CatalogError("XDG_CONFIG_HOME debe ser absoluto.")
    return root / "audiobook-qc/descriptions.json"


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"Clave JSON duplicada: {key}.")
        result[key] = value
    return result


def load_catalog(
    path: Path | None = None, *, types: TypeCatalog | None = None
) -> DescriptionCatalog:
    target = path if path is not None else catalog_path()
    try:
        data = json.loads(
            target.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
        if (
            not isinstance(data, dict)
            or set(data) != {"version", "descriptions"}
            or type(data["version"]) is not int
            or data["version"] != 1
            or not isinstance(data["descriptions"], list)
        ):
            raise CatalogError("Se requiere version: 1 y descriptions: lista.")
        type_catalog = types if types is not None else load_types()
        entries = []
        for item in data["descriptions"]:
            if (
                not isinstance(item, dict)
                or set(item) != {"id", "text", "incident_types"}
                or not isinstance(item["incident_types"], list)
                or any(not isinstance(t, str) for t in item["incident_types"])
            ):
                raise CatalogError(
                    "Entrada inválida: requiere id, text e incident_types."
                )
            for identifier in item["incident_types"]:
                type_catalog.get(identifier)
            entries.append(
                GenericDescription(
                    item["id"],
                    item["text"],
                    tuple(item["incident_types"]),
                )
            )
        return DescriptionCatalog(tuple(entries))
    except (OSError, ValueError, UnicodeError) as exc:
        raise CatalogError(f"Catálogo {target}: {exc}") from exc
