"""Identidad de un audiolibro, independiente de captura y almacenamiento."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CorrectionJob:
    id: str
    name: str
    directory: Path
    created_at: datetime
