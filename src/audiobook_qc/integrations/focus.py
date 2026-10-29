"""Identificación conservadora de la ventana activa en X11 mediante xprop."""

import os
import re
import subprocess
from pathlib import Path


class FocusError(Exception):
    """No hay información suficiente o estable para autorizar el foco."""


def _query(*arguments: str) -> str:
    try:
        result = subprocess.run(
            ["xprop", *arguments],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            env=dict(os.environ, LC_ALL="C"),
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise FocusError(f"No se pudo consultar el foco X11: {exc}") from exc
    if result.returncode:
        raise FocusError(f"xprop falló: {result.stderr.strip() or result.returncode}")
    return result.stdout.strip()


def _active_window() -> str:
    value = _query("-root", "_NET_ACTIVE_WINDOW")
    match = re.fullmatch(
        r"_NET_ACTIVE_WINDOW\(WINDOW\): window id # (0x[0-9a-fA-F]+)", value
    )
    if match is None or int(match[1], 16) == 0:
        raise FocusError("No se pudo identificar una ventana activa inequívoca.")
    return match[1]


def _executable(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/exe").resolve(strict=True).name
    except OSError as exc:
        raise FocusError(
            "No se pudo verificar el proceso de la ventana activa."
        ) from exc


def active_application() -> str:
    """Verifica ventana estable y coherencia WM_CLASS/PID/binario, sin usar título.

    WM_CLASS y _NET_WM_PID los publica el cliente; esto previene errores de uso,
    no es una frontera de seguridad contra aplicaciones X11 maliciosas.
    """
    if os.environ.get("XDG_SESSION_TYPE") != "x11" or not os.environ.get("DISPLAY"):
        raise FocusError("Se requiere una sesión X11 identificada y DISPLAY.")
    window = _active_window()
    properties = _query("-id", window, "WM_CLASS", "_NET_WM_PID")
    match = re.fullmatch(
        r'WM_CLASS\(STRING\) = "([^"\\]+)", "([^"\\]+)"\n'
        r"_NET_WM_PID\(CARDINAL\) = ([1-9][0-9]*)",
        properties,
    )
    if match is None:
        raise FocusError("Clase o PID de la ventana ausente, inválido o ambiguo.")
    instance, wm_class, pid = match.groups()
    executable = _executable(int(pid))
    if _active_window() != window:
        raise FocusError(
            "El foco cambió durante la comprobación; activación rechazada."
        )
    identities = {
        ("okular", "okular", "okular"): "okular",
        ("gl", "mpv", "mpv"): "mpv",
        ("mpv", "mpv", "mpv"): "mpv",
    }
    return identities.get((instance, wm_class, executable), "other")
