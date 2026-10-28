"""Pruebas sin D-Bus accesible, PDFs personales ni Okular en ejecución."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from audiobook_qc import okular_probe
from audiobook_qc.integrations.okular import (
    OkularError,
    OkularState,
    SessionBus,
    local_path,
    parse_reply,
    read_state,
    select_service,
    verify_interface,
)

XML = """<node><interface name="org.kde.okular">
<method name="currentDocument"><arg type="s" direction="out"/></method>
<method name="currentPage"><arg type="u" direction="out"/></method>
</interface></node>"""
SERVICE = "org.kde.okular-123"


@pytest.mark.parametrize(
    ("signature", "data"),
    [("s", "/tmp/a b.pdf"), ("u", 1), ("u", 0), ("as", [SERVICE])],
)
def test_busctl_reply(signature: str, data: object) -> None:
    assert (
        parse_reply(json.dumps({"type": signature, "data": [data]}), signature) == data
    )


@pytest.mark.parametrize(
    ("output", "signature"),
    [
        ("invalid", "s"),
        ("[]", "s"),
        ('{"type":"s","data":[]}', "s"),
        ('{"type":"s","data":["a","b"]}', "s"),
        ('{"type":"u","data":["1"]}', "u"),
        ('{"type":"u","data":[true]}', "u"),
        ('{"type":"u","data":[-1]}', "u"),
        ('{"type":"u","data":[4294967296]}', "u"),
        ('{"type":"i","data":[1]}', "u"),
        ('{"type":"as","data":[[1]]}', "as"),
    ],
)
def test_invalid_reply(output: str, signature: str) -> None:
    with pytest.raises(OkularError, match="Respuesta D-Bus inválida"):
        parse_reply(output, signature)


def test_service_selection_requires_unambiguous_choice() -> None:
    assert select_service([SERVICE]) == SERVICE
    assert select_service([SERVICE, "org.kde.okular-456"], SERVICE) == SERVICE
    with pytest.raises(OkularError, match="No hay servicios"):
        select_service([])
    with pytest.raises(OkularError, match="varios servicios.*--service"):
        select_service([SERVICE, "org.kde.okular-456"])
    with pytest.raises(OkularError, match="no está registrado"):
        select_service([SERVICE], "org.kde.okular-999")


def test_discovery_filters_names_without_choosing_an_active_window() -> None:
    names = [
        ":1.4",
        "org.kde.other",
        SERVICE,
        SERVICE,
        "org.kde.okular",
        "org.kde.okular-other",
    ]
    with patch.object(SessionBus, "call", return_value=names):
        assert SessionBus().list_services() == ["org.kde.okular", SERVICE]


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("/tmp/a b%20.pdf", Path("/tmp/a b%20.pdf")),
        ("file:///tmp/a%20b.pdf", Path("/tmp/a b.pdf")),
        ("file://localhost/tmp/á.pdf", Path("/tmp/á.pdf")),
        ("https://example.org/a.pdf", None),
        ("file://remote/tmp/a.pdf", None),
        ("file:relative.pdf", None),
        ("file:///tmp/a.pdf?query", None),
        ("file:///tmp/a.pdf#page=1", None),
        ("a.pdf", None),
        ("//remote/share/a.pdf", None),
        ("", None),
    ],
)
def test_only_unambiguous_local_documents_become_paths(
    document: str, expected: Path | None
) -> None:
    assert local_path(document) == expected


def test_interface_signatures_checked_before_calls() -> None:
    verify_interface(XML)
    for invalid in (
        "not xml",
        "<node/>",
        XML.replace('type="u"', 'type="i"'),
        XML.replace('direction="out"', 'direction="in"'),
    ):
        with pytest.raises(OkularError):
            verify_interface(invalid)


@pytest.mark.parametrize("page", [1, 3])
def test_page_value_is_preserved_without_plus_one(page: int) -> None:
    bus = SessionBus()
    with (
        patch.object(bus, "list_services", return_value=[SERVICE]),
        patch.object(bus, "call", side_effect=[XML, "/tmp/a.pdf", page]) as call,
    ):
        state = read_state(bus=bus)
    assert state == OkularState(SERVICE, "/tmp/a.pdf", Path("/tmp/a.pdf"), page)
    assert [args.args[3] for args in call.call_args_list] == [
        "Introspect",
        "currentDocument",
        "currentPage",
    ]


def test_missing_document_does_not_report_a_meaningless_page() -> None:
    bus = SessionBus()
    with (
        patch.object(bus, "list_services", return_value=[SERVICE]),
        patch.object(bus, "call", side_effect=[XML, "", 0]),
    ):
        state = read_state(bus=bus)
    assert state == OkularState(SERVICE, None, None, None)
    assert "Página (D-Bus): no disponible" in okular_probe.format_state(state)


def test_remote_document_identifier_is_preserved() -> None:
    bus = SessionBus()
    with (
        patch.object(bus, "list_services", return_value=[SERVICE]),
        patch.object(bus, "call", side_effect=[XML, "https://example.org/a.pdf", 1]),
    ):
        state = read_state(bus=bus)
    assert state.path is None
    assert state.document == "https://example.org/a.pdf"


@pytest.mark.parametrize(
    "error",
    [FileNotFoundError(), PermissionError(), subprocess.TimeoutExpired("busctl", 5)],
)
def test_command_execution_errors(error: Exception) -> None:
    with (
        patch("audiobook_qc.integrations.okular.subprocess.run", side_effect=error),
        pytest.raises(OkularError),
    ):
        SessionBus().list_services()


def test_dbus_failure_includes_method_and_original_detail() -> None:
    failed = subprocess.CompletedProcess([], 1, "", "Unknown method currentPage")
    with patch("audiobook_qc.integrations.okular.subprocess.run", return_value=failed):
        with pytest.raises(OkularError, match="currentPage.*Unknown method"):
            SessionBus().call(SERVICE, "/okular", "org.kde.okular", "currentPage", "u")


def test_transport_disables_service_activation_and_limits_execution() -> None:
    result = subprocess.CompletedProcess([], 0, '{"type":"as","data":[[]]}', "")
    with patch(
        "audiobook_qc.integrations.okular.subprocess.run", return_value=result
    ) as run:
        assert SessionBus().list_services() == []
    command = run.call_args.args[0]
    assert "--auto-start=no" in command
    assert "--user" in command
    assert "--timeout=3" in command
    assert run.call_args.kwargs["timeout"] == 5
    assert "shell" not in run.call_args.kwargs


def test_cli_expected_error_has_no_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch.object(
        okular_probe, "read_state", side_effect=OkularError("sin servicio")
    ):
        assert okular_probe.main([]) == 1
    assert capsys.readouterr().err == "Error: sin servicio\n"


def test_cli_explicit_service(capsys: pytest.CaptureFixture[str]) -> None:
    state = OkularState(SERVICE, "/tmp/a.pdf", Path("/tmp/a.pdf"), 3)
    with patch.object(okular_probe, "read_state", return_value=state) as read:
        assert okular_probe.main(["--service", SERVICE]) == 0
    read.assert_called_once_with(SERVICE)
    output = capsys.readouterr().out
    assert "Página (D-Bus): 3" in output
    assert f"Servicio: {SERVICE}" in output


def test_cli_lists_services(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(SessionBus, "list_services", return_value=[SERVICE]):
        assert okular_probe.main(["--list-services"]) == 0
    assert capsys.readouterr().out == SERVICE + "\n"
