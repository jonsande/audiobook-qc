"""Pruebas sin depender de aplicaciones o de una sesión gráfica real."""

import subprocess
from unittest.mock import patch

import pytest

from audiobook_qc import diagnostics


def test_missing_tool_does_not_run_a_command() -> None:
    with (
        patch.object(diagnostics.shutil, "which", return_value=None),
        patch.object(diagnostics.subprocess, "run") as run,
    ):
        result = diagnostics.inspect_tool("mpv", version=True)
    assert result.status == "missing"
    run.assert_not_called()
    assert "no encontrada" in diagnostics.format_tool(result)


def test_availability_only_does_not_run_a_command() -> None:
    with (
        patch.object(diagnostics.shutil, "which", return_value="/usr/bin/qdbus"),
        patch.object(diagnostics.subprocess, "run") as run,
    ):
        result = diagnostics.inspect_tool("qdbus")
    assert result.status == "available"
    assert result.path == "/usr/bin/qdbus"
    run.assert_not_called()


@pytest.mark.parametrize(
    ("stdout", "stderr"), [("mpv example\n", ""), ("", "mpv example\n")]
)
def test_version_can_be_reported_on_either_stream(stdout: str, stderr: str) -> None:
    completed = subprocess.CompletedProcess([], 0, stdout, stderr)
    with (
        patch.object(diagnostics.shutil, "which", return_value="/bin/mpv"),
        patch.object(diagnostics.subprocess, "run", return_value=completed) as run,
    ):
        result = diagnostics.inspect_tool("mpv", version=True)
    assert result.status == "available"
    assert result.detail == "mpv example"
    run.assert_called_once_with(
        ["/bin/mpv", "--version"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=5,
        check=False,
    )


def test_failed_command_keeps_output_and_exit_code() -> None:
    completed = subprocess.CompletedProcess([], 2, "partial output", "error message")
    with (
        patch.object(diagnostics.shutil, "which", return_value="/bin/okular"),
        patch.object(diagnostics.subprocess, "run", return_value=completed),
    ):
        result = diagnostics.inspect_tool("okular", version=True)
    assert result.status == "failed"
    formatted = diagnostics.format_tool(result)
    for text in ("instalada, comando fallido", "2", "partial output", "error message"):
        assert text in formatted


@pytest.mark.parametrize(
    "error", [subprocess.TimeoutExpired("mpv", 5), PermissionError("denegado")]
)
def test_execution_errors_are_reported(error: Exception) -> None:
    with (
        patch.object(diagnostics.shutil, "which", return_value="/bin/mpv"),
        patch.object(diagnostics.subprocess, "run", side_effect=error),
    ):
        result = diagnostics.inspect_tool("mpv", version=True)
    assert result.status == "failed"
    assert result.detail


def test_success_without_output_does_not_invent_a_version() -> None:
    with (
        patch.object(diagnostics.shutil, "which", return_value="/bin/mpv"),
        patch.object(
            diagnostics.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
    ):
        result = diagnostics.inspect_tool("mpv", version=True)
    assert "versión desconocida" in result.detail


def test_os_release_and_fallback() -> None:
    with patch.object(
        diagnostics.platform,
        "freedesktop_os_release",
        return_value={"PRETTY_NAME": "OS X"},
    ):
        assert diagnostics.operating_system() == "OS X"
    with (
        patch.object(
            diagnostics.platform, "freedesktop_os_release", side_effect=OSError
        ),
        patch.object(diagnostics.platform, "system", return_value="Linux"),
    ):
        assert diagnostics.operating_system() == (
            "Linux (versión de distribución no disponible)"
        )


def test_report_continues_with_missing_tools_and_distinguishes_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":42")
    with patch.object(diagnostics.shutil, "which", return_value=None):
        report = diagnostics.collect_report()
    for text in (
        "XDG_SESSION_TYPE: wayland",
        "XDG_CURRENT_DESKTOP: (definida, vacía)",
        "WAYLAND_DISPLAY: no definida",
        "DISPLAY: :42",
        "mpv: no encontrada",
        "okular: no encontrada",
        "dbus-send: no encontrada",
        "Python:",
        "Kernel:",
        "Arquitectura:",
    ):
        assert text in report


def test_report_continues_after_a_version_command_fails() -> None:
    def inspect(name: str, *, version: bool = False) -> diagnostics.ToolResult:
        if name == "mpv":
            return diagnostics.ToolResult(name, "failed", "/bin/mpv", "fallo simulado")
        return diagnostics.ToolResult(name, "available", f"/bin/{name}")

    with patch.object(diagnostics, "inspect_tool", side_effect=inspect):
        report = diagnostics.collect_report()
    assert "mpv: instalada, comando fallido" in report
    assert "fallo simulado" in report
    assert "okular: disponible" in report
    assert "dbus-send: disponible" in report
