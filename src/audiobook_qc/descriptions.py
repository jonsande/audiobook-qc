"""Catálogo inmutable y reglas de selección, independientes de almacenamiento/UI."""

import re
from dataclasses import dataclass

from audiobook_qc.type_catalog import validate_type_id


class CatalogError(ValueError):
    """Catálogo o selección inválidos."""


@dataclass(frozen=True)
class GenericDescription:
    id: str
    text: str
    incident_types: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not re.fullmatch(
            r"[a-z][a-z0-9_-]*", self.id
        ):
            raise CatalogError("ID inválido: usa [a-z][a-z0-9_-]*.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise CatalogError(f"La descripción {self.id} necesita texto efectivo.")
        if (
            not isinstance(self.incident_types, tuple)
            or not self.incident_types
            or any(not isinstance(t, str) for t in self.incident_types)
            or len(set(self.incident_types)) != len(self.incident_types)
        ):
            raise CatalogError(f"Tipos inválidos o duplicados en {self.id}.")
        for identifier in self.incident_types:
            validate_type_id(identifier)


@dataclass(frozen=True)
class DescriptionCatalog:
    descriptions: tuple[GenericDescription, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.descriptions, tuple) or any(
            not isinstance(item, GenericDescription) for item in self.descriptions
        ):
            raise CatalogError("El catálogo debe contener descripciones válidas.")
        ids = [item.id for item in self.descriptions]
        if len(set(ids)) != len(ids):
            raise CatalogError("IDs duplicados en el catálogo.")

    def list(self, incident_type: str | None = None) -> tuple[GenericDescription, ...]:
        return tuple(
            item
            for item in self.descriptions
            if incident_type is None or incident_type in item.incident_types
        )

    def resolve(self, identifier: str, incident_type: str) -> str:
        for item in self.descriptions:
            if item.id == identifier:
                if incident_type not in item.incident_types:
                    raise CatalogError(
                        f"Descripción {identifier} incompatible con {incident_type}."
                    )
                return item.text
        raise CatalogError(f"Descripción inexistente: {identifier}.")
