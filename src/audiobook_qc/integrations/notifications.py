"""Notificación pasiva mediante libnotify, sin cuadros de diálogo ni shell."""

import subprocess
from html import escape


class NotificationError(Exception):
    """La notificación no pudo enviarse; no determina el estado de persistencia."""


def notify(summary: str, body: str, *, error: bool = False) -> None:
    try:
        result = subprocess.run(
            [
                "notify-send",
                "--app-name=audiobook-qc",
                "--urgency=critical" if error else "--urgency=normal",
                "--",
                summary,
                escape(body),
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NotificationError(f"No se pudo ejecutar notify-send: {exc}") from exc
    if result.returncode:
        raise NotificationError(
            f"notify-send falló: {result.stderr.strip() or result.returncode}"
        )
