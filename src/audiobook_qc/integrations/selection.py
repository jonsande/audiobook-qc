"""Lectura puntual de selecciones globales X11; independiente de Okular."""

import os
import subprocess
from dataclasses import dataclass
from typing import Literal

SelectionName = Literal["primary", "clipboard"]


class SelectionError(Exception):
    """Fallo esperado al ejecutar xclip o consultar X11."""


class SelectionUnavailableError(SelectionError):
    """La selección no existe o no ofrece el formato de texto solicitado."""


@dataclass(frozen=True)
class Selection:
    name: SelectionName
    text: str


def decode_text(data: bytes) -> str:
    """Decodifica UTF-8 estrictamente, sin normalizar ni retirar terminadores."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SelectionError("La selección no contiene texto UTF-8 válido.") from exc


def read_selection(name: SelectionName = "primary") -> Selection:
    """Lee una selección explícita; nunca copia ni recurre a la otra selección."""
    if name not in ("primary", "clipboard"):
        raise ValueError("La selección debe ser primary o clipboard.")
    if not os.environ.get("DISPLAY"):
        raise SelectionError("DISPLAY no está definida o está vacía; se requiere X11.")
    command = ["xclip", "-selection", name, "-out", "-target", "UTF8_STRING"]
    # Estabiliza únicamente los mensajes de diagnóstico de este subproceso.
    environment = dict(os.environ, LC_ALL="C")
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=3, check=False, env=environment
        )
    except FileNotFoundError as exc:
        raise SelectionError(
            "No se encuentra xclip en PATH; puede no estar instalado."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SelectionError(
            "Tiempo agotado al consultar la selección X11 (3 s)."
        ) from exc
    except OSError as exc:
        raise SelectionError(f"No se pudo ejecutar xclip: {exc}.") from exc
    if result.returncode != 0:
        detail = (
            result.stderr.decode("utf-8", errors="replace").strip() or "sin detalle"
        )
        # xclip 0.13 puede probar STRING tras fallar UTF8_STRING, en la misma
        # selección. Ambos diagnósticos significan ausencia de texto compatible.
        if any(
            f"target {target} not available" in detail
            for target in ("UTF8_STRING", "STRING")
        ):
            raise SelectionUnavailableError(
                f"Selección {name.upper()} inexistente o sin texto compatible: {detail}"
            )
        raise SelectionError(
            f"Fallo al consultar X11/{name.upper()} con xclip "
            f"(salida {result.returncode}): {detail}"
        )
    return Selection(name, decode_text(result.stdout))
