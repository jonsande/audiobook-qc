"""Consulta/edición con campos permitidos, sin CLI, SQLite ni aplicaciones externas."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol

from audiobook_qc.descriptions import DescriptionCatalog
from audiobook_qc.incident import Incident

EDITABLE_FIELDS = frozenset(
    {
        "incident_type",
        "audio_position_seconds",
        "document",
        "page",
        "selected_text",
        "generic_description",
        "custom_comment",
    }
)


class ReviewError(ValueError):
    """Petición de revisión inválida o incidencia ausente."""


class IncidentReviewer(Protocol):
    def get(self, incident_id: int) -> Incident | None: ...
    def update(self, incident: Incident) -> Incident: ...


def get_incident(repository: IncidentReviewer, incident_id: int) -> Incident:
    if type(incident_id) is not int or incident_id <= 0:
        raise ReviewError("El ID debe ser un entero positivo.")
    incident = repository.get(incident_id)
    if incident is None:
        raise ReviewError(f"Incidencia inexistente: {incident_id}.")
    return incident


def edit_incident(
    repository: IncidentReviewer,
    incident_id: int,
    changes: Mapping[str, object],
    *,
    catalog: DescriptionCatalog | None = None,
    description_id: str | None = None,
) -> Incident:
    """El llamador mantiene el trabajo bloqueado desde get hasta el commit.

    Solo reemplaza los campos permitidos; Incident valida antes de update.
    Repetir valores ya guardados no escribe ni altera updated_at.
    """
    if not changes and description_id is None:
        raise ReviewError("Indica al menos un campo para editar.")
    forbidden = set(changes) - EDITABLE_FIELDS
    if forbidden:
        raise ReviewError(
            "Campos protegidos o desconocidos: " + ", ".join(sorted(forbidden))
        )
    stored = get_incident(repository, incident_id)
    resolved = dict(changes)
    if description_id is not None:
        if "generic_description" in resolved:
            raise ReviewError("No combines texto manual y un ID de descripción.")
        if catalog is None:
            raise ReviewError("La selección por ID requiere un catálogo validado.")
        target = replace(stored, **resolved)
        resolved["generic_description"] = catalog.resolve(
            description_id, target.incident_type
        )
    edited = replace(stored, **resolved)
    if (
        edited.incident_type != stored.incident_type
        and stored.generic_description
        and stored.generic_description.strip()
        and edited.generic_description == stored.generic_description
        and description_id is None
    ):
        raise ReviewError(
            "Cambio de tipo rechazado: la descripción existente podría ser "
            "incompatible. Elimina o reemplaza la descripción genérica "
            "explícitamente antes de cambiar el tipo (o en la misma edición)."
        )
    return stored if edited == stored else repository.update(edited)
