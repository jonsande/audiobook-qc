"""Entidad de dominio editable mediante dataclasses.replace, sin SQL ni adaptadores."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from audiobook_qc.captured_incident import CapturedIncident, IncidentType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Incident:
    incident_type: IncidentType
    audio_filename: str
    audio_path: str
    audio_position_seconds: float
    document: str
    page: int
    selected_text: str
    generic_description: str | None = None
    custom_comment: str | None = None
    exported: bool = False
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "incident_type", IncidentType(self.incident_type))
        for name in ("audio_filename", "audio_path", "document", "selected_text"):
            value = getattr(self, name)
            if not isinstance(value, str) or value == "":
                raise ValueError(f"{name} debe ser texto no vacío.")
        for name in ("generic_description", "custom_comment"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} debe ser texto o None.")
        if type(self.audio_position_seconds) not in (int, float):
            raise ValueError("audio_position_seconds debe ser un número finito.")
        try:
            position = float(self.audio_position_seconds)
        except OverflowError as exc:
            raise ValueError("audio_position_seconds fuera de rango.") from exc
        if not math.isfinite(position):
            raise ValueError("audio_position_seconds debe ser finito.")
        object.__setattr__(self, "audio_position_seconds", position)
        if type(self.page) is not int or self.page < 0:
            raise ValueError(
                "page debe ser un entero no negativo, sin convertir su base."
            )
        if type(self.exported) is not bool:
            raise ValueError("exported debe ser booleano.")
        if self.id is not None and (type(self.id) is not int or self.id <= 0):
            raise ValueError("id debe ser un entero positivo o None.")
        if self.updated_at is None:
            object.__setattr__(self, "updated_at", self.created_at)
        for name in ("created_at", "updated_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ValueError(f"{name} debe tener zona horaria.")
            object.__setattr__(self, name, value.astimezone(timezone.utc))

    @classmethod
    def from_capture(
        cls,
        capture: CapturedIncident,
        *,
        generic_description: str | None = None,
        custom_comment: str | None = None,
    ) -> "Incident":
        """Convierte una captura sin guardarla ni componer sus descripciones."""
        return cls(
            incident_type=capture.incident_type,
            audio_filename=capture.audio_filename,
            audio_path=capture.audio_path,
            audio_position_seconds=capture.audio_position_seconds,
            document=capture.document,
            page=capture.page,
            selected_text=capture.selected_text,
            generic_description=generic_description,
            custom_comment=custom_comment,
        )
