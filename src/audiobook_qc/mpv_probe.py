"""CLI de la prueba aislada de consulta a mpv (sin control de reproducción)."""

import argparse
import math
import sys

from audiobook_qc.integrations.mpv import DEFAULT_SOCKET, MpvError, MpvState, read_state


def format_time(seconds: float) -> str:
    """Redondea a milisegundos para mostrar; no modifica el dato de la consulta."""
    if not math.isfinite(seconds):
        raise ValueError("El tiempo debe ser finito.")
    milliseconds = round(seconds * 1000)
    sign = "-" if milliseconds < 0 else ""
    total_seconds, fraction = divmod(abs(milliseconds), 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{sign}{hours:02}:{minutes:02}:{secs:02}.{fraction:03}"


def format_state(state: MpvState) -> str:
    missing = "no disponible temporalmente"
    position = format_time(state.position) if state.position is not None else missing
    duration = format_time(state.duration) if state.duration is not None else missing
    paused = missing if state.paused is None else "sí" if state.paused else "no"
    raw = str(state.position) if state.position is not None else missing
    return "\n".join(
        (
            "Estado de mpv",
            f"Archivo: {state.filename if state.filename is not None else missing}",
            f"Ruta: {state.path if state.path is not None else missing}",
            f"Posición: {position}",
            f"Posición (segundos): {raw}",
            f"Duración: {duration}",
            f"Pausado: {paused}",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consulta puntual de mpv por JSON IPC."
    )
    parser.add_argument(
        "--socket", default=DEFAULT_SOCKET, help="Ruta del socket Unix."
    )
    args = parser.parse_args(argv)
    try:
        state = read_state(args.socket)
    except MpvError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(format_state(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
