"""Coordinador probado con fuentes en memoria, sin aplicaciones externas."""

from dataclasses import replace

import pytest

from audiobook_qc import capture_probe
from audiobook_qc.capture import CaptureError, capture_incident
from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.integrations.mpv import MpvError, MpvState
from audiobook_qc.integrations.okular import OkularError, OkularState
from audiobook_qc.integrations.selection import Selection, SelectionError


class Sources:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.errors: dict[str, Exception] = {}
        self.selection = Selection("primary", "  Una palabra parti-\r\nda. e\u0301\n\n")
        self.document = OkularState("org.kde.okular-123", "file:///tmp/a.pdf", None, 3)
        self.audio = MpvState("a.wav", "/tmp/a.wav", 1.251234, None, False)

    def primary(self) -> Selection:
        self.calls.append("primary")
        if "primary" in self.errors:
            raise self.errors["primary"]
        return self.selection

    def pdf(self) -> OkularState:
        self.calls.append("okular")
        if "okular" in self.errors:
            raise self.errors["okular"]
        return self.document

    def mpv(self) -> MpvState:
        self.calls.append("mpv")
        if "mpv" in self.errors:
            raise self.errors["mpv"]
        return self.audio

    def capture(self, code: str = "INTER") -> CapturedIncident:
        return capture_incident(
            code, read_primary=self.primary, read_document=self.pdf, read_audio=self.mpv
        )


@pytest.mark.parametrize(
    "code", ["TEXT", "PRON", "DICC", "RUID", "RESP", "INTER", "OTRO"]
)
def test_capture_preserves_data_and_reads_each_source_once_in_order(code: str) -> None:
    sources = Sources()
    capture = sources.capture(code)
    assert capture == CapturedIncident(
        IncidentType(code),
        "a.wav",
        "/tmp/a.wav",
        1.251234,
        "file:///tmp/a.pdf",
        3,
        "  Una palabra parti-\r\nda. e\u0301\n\n",
    )
    assert sources.calls == ["primary", "okular", "mpv"]


@pytest.mark.parametrize(
    "code", ["text", "inter", " INTER", "INTER ", "", "TEXT\n", "NEW"]
)
def test_invalid_code_is_rejected_before_reading_any_source(code: str) -> None:
    sources = Sources()
    with pytest.raises(CaptureError, match="Código de incidencia inválido"):
        sources.capture(code)
    assert sources.calls == []


@pytest.mark.parametrize(
    ("source", "error", "label", "calls"),
    [
        ("primary", SelectionError("sin X11"), "PRIMARY", ["primary"]),
        ("okular", OkularError("varios servicios"), "Okular", ["primary", "okular"]),
        ("mpv", MpvError("socket inexistente"), "mpv", ["primary", "okular", "mpv"]),
    ],
)
def test_expected_errors_have_context_and_preserve_cause(
    source: str, error: Exception, label: str, calls: list[str]
) -> None:
    sources = Sources()
    sources.errors[source] = error
    with pytest.raises(CaptureError, match=label) as caught:
        sources.capture()
    assert caught.value.__cause__ is error
    assert str(error) in str(caught.value)
    assert sources.calls == calls


def test_unexpected_programming_error_is_not_hidden() -> None:
    sources = Sources()
    sources.errors["okular"] = RuntimeError("fallo inesperado")
    with pytest.raises(RuntimeError, match="fallo inesperado"):
        sources.capture()


@pytest.mark.parametrize(
    ("source", "field", "value", "label"),
    [
        ("selection", "text", "", "texto de PRIMARY"),
        ("document", "document", None, "documento de Okular"),
        ("document", "document", "", "documento de Okular"),
        ("document", "page", None, "página de Okular"),
        ("audio", "filename", None, "nombre del archivo"),
        ("audio", "filename", "", "nombre del archivo"),
        ("audio", "path", None, "ruta del audio"),
        ("audio", "path", "", "ruta del audio"),
        ("audio", "position", None, "posición de mpv"),
    ],
)
def test_missing_required_data_fails(
    source: str, field: str, value: object, label: str
) -> None:
    sources = Sources()
    setattr(sources, source, replace(getattr(sources, source), **{field: value}))
    with pytest.raises(CaptureError, match=label):
        sources.capture()
    if source == "selection":
        assert sources.calls == ["primary"]
    elif source == "document":
        assert sources.calls == ["primary", "okular"]


def test_clipboard_cannot_be_substituted_for_primary() -> None:
    sources = Sources()
    sources.selection = Selection("clipboard", "texto antiguo")
    with pytest.raises(CaptureError, match="debe devolver PRIMARY"):
        sources.capture()
    assert sources.calls == ["primary"]


def test_zero_and_optional_metadata_do_not_become_missing_values() -> None:
    sources = Sources()
    sources.audio = replace(sources.audio, position=0.0, duration=None, paused=None)
    sources.document = replace(sources.document, page=0)
    sources.selection = Selection("primary", " \t\n")
    capture = sources.capture()
    assert capture.audio_position_seconds == 0.0
    assert capture.page == 0
    assert capture.selected_text == " \t\n"


def test_cli_wires_existing_adapters_and_preserves_precision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sources = Sources()

    def primary(name: str) -> Selection:
        assert name == "primary"
        return sources.primary()

    def pdf(service: str | None) -> OkularState:
        assert service == "org.kde.okular-123"
        return sources.pdf()

    def audio(socket_path: str) -> MpvState:
        assert socket_path == "/tmp/test.sock"
        return sources.mpv()

    monkeypatch.setattr(capture_probe.selection, "read_selection", primary)
    monkeypatch.setattr(capture_probe.okular, "read_state", pdf)
    monkeypatch.setattr(capture_probe.mpv, "read_state", audio)
    assert (
        capture_probe.main(
            [
                "INTER",
                "--mpv-socket",
                "/tmp/test.sock",
                "--okular-service",
                "org.kde.okular-123",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Tipo: INTER" in output
    assert "Posición: 00:00:01.251" in output
    assert "Posición (segundos): 1.251234" in output
    assert "Página (D-Bus): 3" in output
    assert repr(sources.selection.text) in output
    assert sources.calls == ["primary", "okular", "mpv"]


def test_cli_invalid_code_never_starts_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args: object, **kwargs: object) -> CapturedIncident:
        pytest.fail("No debe iniciar la captura")

    monkeypatch.setattr(capture_probe, "capture_incident", unexpected)
    with pytest.raises(SystemExit) as caught:
        capture_probe.main(["inter"])
    assert caught.value.code == 2


def test_cli_capture_error_has_no_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args: object, **kwargs: object) -> CapturedIncident:
        raise CaptureError("socket inexistente")

    monkeypatch.setattr(capture_probe, "capture_incident", fail)
    assert capture_probe.main(["INTER"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error de captura: socket inexistente\n"
