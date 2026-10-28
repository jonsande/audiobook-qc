"""Diagnóstico informativo del entorno; no realiza capturas ni integraciones."""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

SESSION_VARIABLES = (
    "XDG_SESSION_TYPE",
    "XDG_CURRENT_DESKTOP",
    "WAYLAND_DISPLAY",
    "DISPLAY",
)
TOOLS = (
    "dbus-send",
    "dbus-monitor",
    "gdbus",
    "busctl",
    "qdbus",
    "qdbus6",
    "qdbus-qt5",
    "qdbus-qt6",
    "/usr/lib/qt5/bin/qdbus",
    "/usr/lib/qt6/bin/qdbus",
    "/usr/lib64/qt5/bin/qdbus",
    "/usr/lib64/qt6/bin/qdbus",
    "xclip",
    "xsel",
    "wl-paste",
)
COMMAND_TIMEOUT = 5


@dataclass(frozen=True)
class ToolResult:
    name: str
    status: Literal["missing", "available", "failed"]
    path: str | None = None
    detail: str = ""


def inspect_tool(name: str, *, version: bool = False) -> ToolResult:
    """Localiza un ejecutable y, si se solicita, ejecuta únicamente --version."""
    path = shutil.which(name)
    if path is None:
        return ToolResult(name, "missing")
    if not version:
        return ToolResult(name, "available", path)
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(name, "failed", path, f"tiempo límite: {COMMAND_TIMEOUT} s")
    except OSError as exc:
        return ToolResult(name, "failed", path, str(exc))

    output = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part.strip()
    )
    if result.returncode != 0:
        detail = f"código de salida {result.returncode}"
        if output:
            detail += f"\n{output}"
        return ToolResult(name, "failed", path, detail)
    return ToolResult(
        name, "available", path, output or "--version sin salida; versión desconocida"
    )


def format_tool(result: ToolResult) -> str:
    """Distingue ausencia, disponibilidad y fallo sin interpretar versiones."""
    if result.status == "missing":
        return (
            f"{result.name}: no encontrada "
            "(PATH/ruta comprobada; puede no estar instalada)"
        )
    state = (
        "disponible" if result.status == "available" else "instalada, comando fallido"
    )
    lines = [f"{result.name}: {state} [{result.path}]"]
    lines.extend(f"    {line}" for line in result.detail.splitlines())
    return "\n".join(lines)


def operating_system() -> str:
    """Lee os-release cuando está disponible en Linux (Python >= 3.10)."""
    try:
        info = platform.freedesktop_os_release()
    except OSError:
        return f"{platform.system()} (versión de distribución no disponible)"
    return (
        info.get("PRETTY_NAME")
        or " ".join(
            (info.get("NAME", platform.system()), info.get("VERSION", ""))
        ).strip()
    )


def collect_report() -> str:
    """Recopila datos del proceso actual, sin acceder al bus ni a la selección."""
    lines = [
        "Diagnóstico de audiobook-qc",
        f"Sistema operativo: {operating_system()}",
        f"Kernel: {platform.system()} {platform.release()}",
        f"Arquitectura: {platform.machine()}",
        f"Python: {platform.python_version()}",
        "",
        "Variables de la sesión (entorno de este proceso):",
    ]
    for name in SESSION_VARIABLES:
        value = os.environ.get(name)
        display = "no definida" if value is None else value or "(definida, vacía)"
        lines.append(f"{name}: {display}")
    lines.extend(("", "Versiones (comandos con límite de 5 s):"))
    for name in ("mpv", "okular"):
        lines.append(format_tool(inspect_tool(name, version=True)))
    lines.extend(("", "Herramientas auxiliares (solo localización, sin ejecución):"))
    for name in TOOLS:
        lines.append(format_tool(inspect_tool(name)))
    lines.extend(
        (
            "",
            "La disponibilidad no verifica acceso a la sesión gráfica ni a D-Bus.",
            "Las búsquedas cubren PATH y las rutas Qt indicadas, no todo el sistema.",
            "No se han probado IPC de mpv, API de Okular, selección ni atajos.",
        )
    )
    return "\n".join(lines)


def main() -> None:
    print(collect_report())


if __name__ == "__main__":
    main()
