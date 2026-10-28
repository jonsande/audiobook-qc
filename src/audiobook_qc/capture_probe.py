"""Composición de adaptadores y CLI para una captura provisional en memoria."""

import argparse
import sys
from functools import partial

from audiobook_qc.capture import CaptureError, capture_incident
from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.integrations import mpv, okular, selection
from audiobook_qc.mpv_probe import format_time


def format_capture(capture: CapturedIncident) -> str:
    return "\n".join(
        (
            "Captura provisional",
            f"Tipo: {capture.incident_type.value}",
            f"Audio: {capture.audio_filename}",
            f"Ruta audio: {capture.audio_path}",
            f"Posición: {format_time(capture.audio_position_seconds)}",
            f"Posición (segundos): {capture.audio_position_seconds}",
            f"PDF: {capture.document}",
            f"Página (D-Bus): {capture.page}",
            "Texto:",
            f"«{capture.selected_text}»",
            f"Texto exacto: {capture.selected_text!r}",
            "Captura en memoria; lectura secuencial. Origen de PRIMARY no verificado.",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Captura conjunta provisional sin guardar."
    )
    parser.add_argument("code", choices=[code.value for code in IncidentType])
    parser.add_argument("--mpv-socket", default=mpv.DEFAULT_SOCKET)
    parser.add_argument("--okular-service", help="Servicio explícito de Okular.")
    args = parser.parse_args(argv)
    try:
        capture = capture_incident(
            args.code,
            read_primary=partial(selection.read_selection, "primary"),
            read_document=partial(okular.read_state, args.okular_service),
            read_audio=partial(mpv.read_state, args.mpv_socket),
        )
    except CaptureError as exc:
        print(f"Error de captura: {exc}", file=sys.stderr)
        return 1
    print(format_capture(capture))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
