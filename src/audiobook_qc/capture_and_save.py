"""Caso de uso de captura y guardado, sin conocer CLI ni almacenamiento concreto."""

from collections.abc import Callable
from typing import Protocol

from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.incident import Incident
from audiobook_qc.type_catalog import TypeCatalog


class IncidentWriter(Protocol):
    def add(self, incident: Incident) -> Incident:
        """Guarda una entidad nueva y devuelve la entidad con su ID asignado."""
        ...


def capture_and_save_incident(
    code: str,
    *,
    types: TypeCatalog,
    capture: Callable[[str], CapturedIncident],
    repository: IncidentWriter,
) -> Incident:
    """Captura, convierte explícitamente y guarda; propaga cualquier fallo.

    El llamador prepara las fuentes y un repositorio inicializado. No crea
    esquemas, reintenta ni comunica éxito antes de que termine add().
    """
    types.require_enabled(code)
    captured = capture(code)
    if captured.incident_type != code:
        raise ValueError("La captura devolvió otro tipo distinto del solicitado.")
    incident = Incident.from_capture(captured)
    return repository.add(incident)
