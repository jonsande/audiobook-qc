"""Representación editorial del tiempo, independiente de CLI y almacenamiento."""

import math


def format_audio_position(seconds: float) -> str:
    """HH:MM:SS truncando hacia cero; no altera los segundos nativos.

    Las horas no se reinician al superar 24 y admiten más de dos dígitos.
    """
    if not math.isfinite(seconds):
        raise ValueError("La posición de audio debe ser finita.")
    whole_seconds = math.trunc(seconds)
    sign = "-" if whole_seconds < 0 else ""
    hours, remainder = divmod(abs(whole_seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{sign}{hours:02}:{minutes:02}:{secs:02}"
