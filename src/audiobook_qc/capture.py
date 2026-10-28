"""Coordinación provisional de las tres fuentes; no guarda ni controla aplicaciones."""

from collections.abc import Callable
from typing import TypeVar

from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.integrations.mpv import MpvError, MpvState
from audiobook_qc.integrations.okular import OkularError, OkularState
from audiobook_qc.integrations.selection import Selection, SelectionError

T = TypeVar("T")


class CaptureError(Exception):
    """Captura incompleta por código, datos o fuentes no disponibles."""


def _required(value: T | None, field: str) -> T:
    if value is None or value == "":
        raise CaptureError(f"Falta un dato imprescindible: {field}.")
    return value


def capture_incident(
    code: str,
    *,
    read_primary: Callable[[], Selection],
    read_document: Callable[[], OkularState],
    read_audio: Callable[[], MpvState],
) -> CapturedIncident:
    """Valida el código y lee PRIMARY → documento/página → audio, una sola vez.

    La selección global se lee primero para reducir el riesgo de sustitución.
    Las fuentes son secuenciales, no atómicas. Se presupone pausa manual del audio,
    pero no se impone como nueva regla de negocio. No se verifica origen del texto.
    """
    try:
        incident_type = IncidentType(code)
    except ValueError as exc:
        raise CaptureError(f"Código de incidencia inválido: {code!r}.") from exc
    try:
        selection = read_primary()
    except SelectionError as exc:
        raise CaptureError(f"No se pudo leer PRIMARY: {exc}") from exc
    if selection.name != "primary":
        raise CaptureError("La fuente de selección debe devolver PRIMARY.")
    selected_text = _required(selection.text, "texto de PRIMARY")

    try:
        document_state = read_document()
    except OkularError as exc:
        raise CaptureError(f"No se pudo consultar Okular: {exc}") from exc
    document = _required(document_state.document, "documento de Okular")
    page = _required(document_state.page, "página de Okular")

    try:
        audio_state = read_audio()
    except MpvError as exc:
        raise CaptureError(f"No se pudo consultar mpv: {exc}") from exc
    return CapturedIncident(
        incident_type=incident_type,
        audio_filename=_required(audio_state.filename, "nombre del archivo de audio"),
        audio_path=_required(audio_state.path, "ruta del audio"),
        audio_position_seconds=_required(audio_state.position, "posición de mpv"),
        document=document,
        page=page,
        selected_text=selected_text,
    )
