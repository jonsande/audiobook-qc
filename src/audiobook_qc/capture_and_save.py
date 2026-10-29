"""Caso de uso de captura y guardado, sin conocer CLI ni almacenamiento concreto."""

from collections.abc import Callable
from typing import Protocol

from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.incident import Incident


class IncidentWriter(Protocol):
    def add(self, incident: Incident) -> Incident:
        """Guarda una entidad nueva y devuelve la entidad con su ID asignado."""
        ...


def capture_and_save_incident(
    code: str,
    *,
    capture: Callable[[str], CapturedIncident],
    repository: IncidentWriter,
) -> Incident:
    """Captura, convierte explícitamente y guarda; propaga cualquier fallo.

    El llamador prepara las fuentes y un repositorio inicializado. No crea
    esquemas, reintenta ni comunica éxito antes de que termine add().
    """
    captured = capture(code)
    incident = Incident.from_capture(captured)
    return repository.add(incident)
