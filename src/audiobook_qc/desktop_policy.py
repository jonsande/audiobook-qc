"""Autorización previa a una activación de escritorio, separada del dominio."""

from collections.abc import Callable


class ActivationRejected(Exception):
    """La pulsación no está autorizada y no debe iniciar captura ni escritura."""


def require_correction_context(
    *,
    mode_active: Callable[[], bool],
    active_app: Callable[[], str],
) -> None:
    if not mode_active():
        raise ActivationRejected(
            "Modo de corrección inactivo; no se ha registrado nada."
        )
    if active_app() not in ("okular", "mpv"):
        raise ActivationRejected(
            "La ventana activa no es Okular ni mpv gráfico; no se registra."
        )
