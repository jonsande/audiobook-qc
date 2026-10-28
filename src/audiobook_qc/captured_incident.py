"""Datos provisionales de captura, sin persistencia ni conocimiento de adaptadores."""

from dataclasses import dataclass
from enum import Enum


class IncidentType(str, Enum):
    TEXT = "TEXT"
    PRON = "PRON"
    DICC = "DICC"
    RUID = "RUID"
    RESP = "RESP"
    INTER = "INTER"
    OTRO = "OTRO"


@dataclass(frozen=True)
class CapturedIncident:
    incident_type: IncidentType
    audio_filename: str
    audio_path: str
    audio_position_seconds: float
    document: str
    page: int
    selected_text: str
