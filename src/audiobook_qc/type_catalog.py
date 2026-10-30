"""Identidad histórica y disponibilidad editorial; sin archivos, SQL ni UI."""

import re
from dataclasses import dataclass


class TypeConfigError(ValueError):
    """Configuración o selección de tipo no válida."""


def validate_type_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
        raise TypeConfigError("El ID de tipo debe seguir [A-Z][A-Z0-9_]*.")
    return value


@dataclass(frozen=True)
class IncidentTypeDefinition:
    id: str
    label: str
    enabled: bool
    default_generic_description: str | None

    def __post_init__(self) -> None:
        validate_type_id(self.id)
        if not isinstance(self.label, str) or not self.label.strip():
            raise TypeConfigError(f"Label ausente o vacío en {self.id}.")
        if type(self.enabled) is not bool:
            raise TypeConfigError(f"enabled debe ser booleano en {self.id}.")
        if self.default_generic_description is not None and not isinstance(
            self.default_generic_description, str
        ):
            raise TypeConfigError(f"Fórmula de {self.id}: debe ser texto o null.")


@dataclass(frozen=True)
class TypeCatalog:
    types: tuple[IncidentTypeDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.types, tuple) or any(
            not isinstance(item, IncidentTypeDefinition) for item in self.types
        ):
            raise TypeConfigError("types debe contener tipos válidos.")
        ids = [item.id for item in self.types]
        if len(set(ids)) != len(ids):
            raise TypeConfigError("IDs de tipo duplicados.")

    def get(self, identifier: str) -> IncidentTypeDefinition:
        validate_type_id(identifier)
        for item in self.types:
            if item.id == identifier:
                return item
        raise TypeConfigError(f"Tipo inexistente: {identifier}.")

    def require_enabled(self, identifier: str) -> IncidentTypeDefinition:
        item = self.get(identifier)
        if not item.enabled:
            raise TypeConfigError(f"Tipo deshabilitado: {identifier}.")
        return item

    def historical_info(self, identifier: str) -> dict:
        """Un ID válido ya persistido es histórico aunque se retire del catálogo."""
        validate_type_id(identifier)
        item = next((item for item in self.types if item.id == identifier), None)
        return dict(
            id=identifier,
            label=item.label if item else identifier,
            enabled=item.enabled if item else None,
            status=("enabled" if item.enabled else "disabled")
            if item
            else "historical",
        )
