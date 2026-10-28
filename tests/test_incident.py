"""Dominio persistente sin aplicaciones externas ni archivos de audio/PDF reales."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.incident import Incident


@pytest.fixture
def incident() -> Incident:
    return Incident(
        incident_type=IncidentType.INTER,
        audio_filename="capítulo.mp3",
        audio_path="relative/audio.mp3",
        audio_position_seconds=1104.5171234567,
        document="https://example.org/libro.pdf",
        page=0,
        selected_text="  ¿Qué quieres decir?\r\nparti-\nda. e\u0301\n",
    )


def test_conversion_preserves_all_capture_fields(incident: Incident) -> None:
    capture = CapturedIncident(
        incident.incident_type,
        incident.audio_filename,
        incident.audio_path,
        incident.audio_position_seconds,
        incident.document,
        incident.page,
        incident.selected_text,
    )
    converted = Incident.from_capture(
        capture, generic_description="Descripción", custom_comment="Comentario\npropio"
    )
    for field in capture.__dataclass_fields__:
        assert getattr(converted, field) == getattr(capture, field)
    assert converted.id is None
    assert converted.generic_description == "Descripción"
    assert converted.custom_comment == "Comentario\npropio"
    assert converted.exported is False
    assert converted.created_at.utcoffset() == timedelta(0)
    assert converted.updated_at == converted.created_at


@pytest.mark.parametrize(
    "code", ["TEXT", "PRON", "DICC", "RUID", "RESP", "INTER", "OTRO"]
)
def test_valid_codes_use_existing_enum(code: str, incident: Incident) -> None:
    assert replace(incident, incident_type=code).incident_type is IncidentType(code)


@pytest.mark.parametrize("code", ["text", " INTER", "INTER ", "", "OTHER", None])
def test_invalid_codes(code: object, incident: Incident) -> None:
    with pytest.raises(ValueError):
        replace(incident, incident_type=code)


@pytest.mark.parametrize(
    "field", ["audio_filename", "audio_path", "document", "selected_text"]
)
@pytest.mark.parametrize("value", [None, "", 42])
def test_required_text_fields(field: str, value: object, incident: Incident) -> None:
    with pytest.raises(ValueError, match=field):
        replace(incident, **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("audio_position_seconds", None),
        ("audio_position_seconds", True),
        ("audio_position_seconds", "1.2"),
        ("audio_position_seconds", float("nan")),
        ("audio_position_seconds", float("inf")),
        ("audio_position_seconds", -float("inf")),
        ("page", None),
        ("page", -1),
        ("page", True),
        ("page", 1.5),
        ("exported", 1),
        ("exported", None),
        ("id", 0),
        ("id", -1),
        ("id", True),
        ("generic_description", 1),
        ("custom_comment", []),
    ],
)
def test_invalid_values(field: str, value: object, incident: Incident) -> None:
    with pytest.raises(ValueError):
        replace(incident, **{field: value})


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_naive_dates_rejected(field: str, incident: Incident) -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        replace(incident, **{field: datetime(2026, 1, 1)})


def test_aware_dates_normalized_without_changing_instant(incident: Incident) -> None:
    date = datetime(2026, 1, 1, 8, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    converted = replace(incident, created_at=date, updated_at=date)
    assert converted.created_at == datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
    assert converted.created_at.tzinfo is timezone.utc
    assert converted.updated_at.tzinfo is timezone.utc


def test_no_text_normalization_or_new_business_rules(incident: Incident) -> None:
    changed = replace(incident, selected_text=" \t\n", audio_position_seconds=-0.311595)
    assert changed.selected_text == " \t\n"
    assert changed.audio_position_seconds == -0.311595
    assert changed.page == 0
    assert incident.selected_text.startswith("  ¿")
