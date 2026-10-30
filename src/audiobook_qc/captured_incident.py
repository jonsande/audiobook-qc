"""Datos provisionales de captura, sin persistencia ni conocimiento de adaptadores."""

from dataclasses import dataclass

from audiobook_qc.type_catalog import validate_type_id


@dataclass(frozen=True)
class CapturedIncident:
    incident_type: str
    audio_filename: str
    audio_path: str
    audio_position_seconds: float
    document: str
    page: int
    selected_text: str

    def __post_init__(self) -> None:
        validate_type_id(self.incident_type)
