"""Pruebas de selección sin servidor X, xclip ni Okular reales."""

import subprocess
from unittest.mock import patch

import pytest

from audiobook_qc import selection_probe
from audiobook_qc.integrations.selection import (
    Selection,
    SelectionError,
    SelectionUnavailableError,
    decode_text,
    read_selection,
)


@pytest.mark.parametrize("name", ["primary", "clipboard"])
def test_explicit_selection_uses_read_only_command(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISPLAY", ":42")
    monkeypatch.setenv("LC_ALL", "example")
    completed = subprocess.CompletedProcess([], 0, b"text\n", b"")
    with patch(
        "audiobook_qc.integrations.selection.subprocess.run", return_value=completed
    ) as run:
        result = read_selection(name)
    assert result == Selection(name, "text\n")
    assert run.call_args.args == (
        ["xclip", "-selection", name, "-out", "-target", "UTF8_STRING"],
    )
    assert run.call_count == 1
    assert run.call_args.kwargs["timeout"] == 3
    assert run.call_args.kwargs["env"]["DISPLAY"] == ":42"
    assert run.call_args.kwargs["env"]["LC_ALL"] == "C"
    assert "shell" not in run.call_args.kwargs
    assert "text" not in run.call_args.kwargs


@pytest.mark.parametrize(
    "text", ["", "  ", "a\n", "a\n\n", "a\r\nb\r", "parti-\nda", "  á  e\u0301\t!?  "]
)
def test_text_is_preserved_exactly(text: str) -> None:
    assert decode_text(text.encode("utf-8")) == text


def test_invalid_utf8_is_not_silently_replaced() -> None:
    with pytest.raises(SelectionError, match="UTF-8 válido"):
        decode_text(b"\xff")


def test_empty_selection_is_distinct_from_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISPLAY", ":42")
    completed = subprocess.CompletedProcess([], 0, b"", b"")
    with patch(
        "audiobook_qc.integrations.selection.subprocess.run", return_value=completed
    ):
        result = read_selection()
    assert result.text == ""
    assert "Estado: vacía" in selection_probe.format_selection(result)


@pytest.mark.parametrize("display", [None, ""])
def test_missing_display_does_not_run_xclip(
    display: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if display is None:
        monkeypatch.delenv("DISPLAY", raising=False)
    else:
        monkeypatch.setenv("DISPLAY", display)
    with patch("audiobook_qc.integrations.selection.subprocess.run") as run:
        with pytest.raises(SelectionError, match="DISPLAY"):
            read_selection()
    run.assert_not_called()


def test_invalid_selection_does_not_run_command() -> None:
    with patch("audiobook_qc.integrations.selection.subprocess.run") as run:
        with pytest.raises(ValueError, match="primary o clipboard"):
            read_selection("secondary")
    run.assert_not_called()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (FileNotFoundError(), "No se encuentra xclip"),
        (PermissionError("denegado"), "No se pudo ejecutar"),
        (subprocess.TimeoutExpired("xclip", 3), "Tiempo agotado"),
    ],
)
def test_execution_errors(
    error: Exception, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISPLAY", ":42")
    with (
        patch("audiobook_qc.integrations.selection.subprocess.run", side_effect=error),
        pytest.raises(SelectionError, match=message),
    ):
        read_selection()


@pytest.mark.parametrize(
    "stderr", [b"Error: Can't open display: :42", b"other xclip failure"]
)
def test_xclip_failure_is_not_empty_selection(
    stderr: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISPLAY", ":42")
    completed = subprocess.CompletedProcess([], 1, b"", stderr)
    with patch(
        "audiobook_qc.integrations.selection.subprocess.run", return_value=completed
    ):
        with pytest.raises(SelectionError, match="salida 1") as caught:
            read_selection()
    assert not isinstance(caught.value, SelectionUnavailableError)
    assert stderr.decode() in str(caught.value)


@pytest.mark.parametrize("target", ["UTF8_STRING", "STRING"])
def test_unavailable_text_does_not_fallback_to_clipboard(
    target: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISPLAY", ":42")
    completed = subprocess.CompletedProcess(
        [], 1, b"", f"Error: target {target} not available\n".encode()
    )
    with patch(
        "audiobook_qc.integrations.selection.subprocess.run", return_value=completed
    ) as run:
        with pytest.raises(SelectionUnavailableError, match="inexistente o sin texto"):
            read_selection("primary")
    assert run.call_count == 1


def test_cli_success_preserves_newlines(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(
        selection_probe, "read_selection", return_value=Selection("primary", "a\nb\n")
    ):
        assert selection_probe.main(["--selection", "primary"]) == 0
    output = capsys.readouterr().out
    assert "Caracteres: 4" in output
    assert "«a\nb\n»" in output
    assert "Representación exacta: 'a\\nb\\n'" in output


@pytest.mark.parametrize(
    ("error", "code"),
    [(SelectionError("fallo X11"), 1), (SelectionUnavailableError("sin texto"), 2)],
)
def test_cli_expected_errors_have_no_tracebacks(
    error: SelectionError, code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    with patch.object(selection_probe, "read_selection", side_effect=error):
        assert selection_probe.main([]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(error) in captured.err
    assert "Traceback" not in captured.err


def test_cli_invalid_selection_is_rejected_before_reading() -> None:
    with patch.object(selection_probe, "read_selection") as read:
        with pytest.raises(SystemExit) as caught:
            selection_probe.main(["--selection", "secondary"])
    assert caught.value.code == 2
    read.assert_not_called()
