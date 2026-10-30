"""Reglas editoriales y edición segura; SQLite real, sin fuentes de escritorio."""

import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from audiobook_qc import capture_save_probe, incidents_cli
from audiobook_qc.incident import Incident
from audiobook_qc.incident_review import ReviewError, edit_incident
from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.jobs import JobStore, job_database
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository


def incident(**changes):
    data = dict(
        incident_type="INTER",
        audio_filename="capítulo.mp3",
        audio_path="./capítulo.mp3",
        audio_position_seconds=1104.5171234567,
        document="file:///libro.pdf",
        page=33,
        selected_text="  Texto parti-\r\ndo. e\u0301\n",
    )
    return Incident(**(data | changes))


@pytest.fixture
def jobs(tmp_path):
    store = JobStore()
    store.configure(str(tmp_path / "Correcciones á"))
    a, b = store.create("Libro A"), store.create("Libro B")
    store.select(a.id)
    return store, a, b


def add(job, **changes):
    with SQLiteIncidentRepository(job_database(job), existing=True) as repository:
        return repository.add(incident(**changes))


def get(job, incident_id=1):
    with SQLiteIncidentRepository(job_database(job), existing=True) as repository:
        return repository.get(incident_id)


def cli_json(capsys, args):
    assert incidents_cli.main([*args, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    "generic,comment,components",
    [
        (None, None, ()),
        ("", "", ()),
        (" \t\n", "\r\n\u2003", ()),
        (None, "Comentario ñ\nsegunda línea", ("Comentario ñ\nsegunda línea",)),
        ("Genérica", None, ("Genérica",)),
        ("", "Comentario", ("Comentario",)),
        ("Genérica", "", ("Genérica",)),
        ("Genérica", "Comentario", ("Genérica", "Comentario")),
        ("  Genérica \n", " e\u0301\r\n", ("  Genérica \n", " e\u0301\r\n")),
    ],
)
def test_editorial_readiness_and_composition_preserve_independent_components(
    generic, comment, components
):
    entity = incident(
        generic_description=generic, custom_comment=comment, exported=True
    )
    assert entity.editorial_components == components
    assert entity.editorially_complete is bool(components)
    assert entity.compose_editorial_description(separator="\n") == "\n".join(components)
    assert entity.compose_editorial_description(separator=" | ") == " | ".join(
        components
    )
    assert entity.generic_description == generic and entity.custom_comment == comment
    assert entity.exported is True


def test_list_empty_active_job_in_human_and_json(jobs, capsys):
    _, a, _ = jobs
    data = cli_json(capsys, ["list"])
    assert data == {"job": {"id": a.id, "name": "Libro A"}, "incidents": []}
    assert incidents_cli.main(["list"]) == 0
    output = capsys.readouterr().out
    assert "Libro A" in output and "Sin incidencias" in output


def test_list_is_ordered_by_creation_then_id_with_full_json_and_short_human_text(
    jobs, capsys
):
    _, a, b = jobs
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    first = add(a, created_at=now, selected_text="ñ" * 200)
    second = add(a, created_at=now - timedelta(days=1))
    third = add(a, created_at=now)
    add(b, selected_text="Texto B")
    data = cli_json(capsys, ["list"])
    assert [item["id"] for item in data["incidents"]] == [second.id, first.id, third.id]
    assert data["incidents"][1]["selected_text"] == "ñ" * 200
    assert incidents_cli.main(["list"]) == 0
    text = capsys.readouterr().out
    assert "…" in text and "ñ" * 200 not in text and "Texto B" not in text
    for value in [
        "Tipo",
        "Audio",
        "Posición",
        "Página",
        "generic_description",
        "custom_comment",
        "exported",
        "Completa",
    ]:
        assert value in text


def test_get_all_fields_exact_precision_and_stable_json_schema(jobs, capsys):
    _, a, _ = jobs
    saved = add(a)
    data = cli_json(capsys, ["get", "1"])
    view = data["incident"]
    assert set(view) == set(saved.__dataclass_fields__) | {
        "audio_position_formatted",
        "editorially_complete",
        "editorial_description_preview",
        "incident_type_info",
    }
    assert view["audio_position_seconds"].hex() == saved.audio_position_seconds.hex()
    assert view["audio_position_formatted"] == "00:18:24"
    assert view["selected_text"] == saved.selected_text
    assert view["created_at"] == saved.created_at.isoformat(timespec="microseconds")
    assert view["generic_description"] is None and view["custom_comment"] is None
    assert view["editorially_complete"] is False and view["exported"] is False
    assert incidents_cli.main(["get", "1"]) == 0
    text = capsys.readouterr().out
    assert "1104.5171234567" in text
    assert all(name in text for name in view)


def test_missing_incident_is_error_without_success_or_write(jobs, capsys):
    _, a, _ = jobs
    before = job_database(a).read_bytes()
    for args in [["get", "999"], ["edit", "999", "--comment", "No"]]:
        assert incidents_cli.main([*args, "--json"]) == 1
        output = capsys.readouterr()
        assert "inexistente" in output.err and output.out == ""
    assert job_database(a).read_bytes() == before


@pytest.mark.parametrize(
    "options,field,value",
    [
        (["--type", "PRON"], "incident_type", "PRON"),
        (["--position", "19.300243"], "audio_position_seconds", 19.300243),
        (["--document", "file:///corregido.pdf"], "document", "file:///corregido.pdf"),
        (["--page", "0"], "page", 0),
        (
            ["--selected-text", "  Nuevo\r\ntexto e\u0301\n"],
            "selected_text",
            "  Nuevo\r\ntexto e\u0301\n",
        ),
        (
            ["--generic-description", "Descripción ñ"],
            "generic_description",
            "Descripción ñ",
        ),
        (
            ["--comment", "Primera línea\nSegunda\r\n"],
            "custom_comment",
            "Primera línea\nSegunda\r\n",
        ),
    ],
)
def test_each_editable_field_persists_and_preserves_protected_fields(
    jobs, capsys, monkeypatch, options, field, value
):
    _, a, b = jobs
    saved = add(a, exported=True)
    add(b)
    b_before = job_database(b).read_bytes()
    now = saved.updated_at + timedelta(seconds=1)
    monkeypatch.setattr("audiobook_qc.sqlite_repository.utc_now", lambda: now)
    result = cli_json(capsys, ["edit", "1", *options])
    edited = get(a)
    assert getattr(edited, field) == value
    assert edited.created_at == saved.created_at and edited.updated_at == now
    assert edited.id == saved.id
    assert (
        edited.audio_filename == saved.audio_filename
        and edited.audio_path == saved.audio_path
    )
    assert edited.exported is True
    assert result["incident"]["updated_at"] == now.isoformat(timespec="microseconds")
    assert job_database(b).read_bytes() == b_before
    assert (
        replace(edited, **{field: getattr(saved, field)}, updated_at=saved.updated_at)
        == saved
    )


@pytest.mark.parametrize(
    "field,option,clear",
    [
        ("generic_description", "--generic-description", "--clear-generic-description"),
        ("custom_comment", "--comment", "--clear-comment"),
    ],
)
def test_nullable_fields_distinguish_missing_empty_and_explicit_null(
    jobs, capsys, field, option, clear
):
    _, a, _ = jobs
    add(a, generic_description="Genérica", custom_comment="Comentario")
    result = cli_json(capsys, ["edit", "1", option, ""])
    assert result["incident"][field] == ""
    assert result["incident"]["editorially_complete"] is True
    result = cli_json(capsys, ["edit", "1", clear])
    assert result["incident"][field] is None
    other = (
        "custom_comment" if field == "generic_description" else "generic_description"
    )
    assert result["incident"][other] == (
        "Comentario" if other == "custom_comment" else "Genérica"
    )
    result = cli_json(
        capsys, ["edit", "1", "--clear-generic-description", "--clear-comment"]
    )
    assert result["incident"]["editorially_complete"] is False
    assert result["incident"]["editorial_description_preview"] == ""


def test_both_editorial_fields_preview_is_composed_without_overwriting_storage(
    jobs, capsys
):
    _, a, _ = jobs
    add(a)
    data = cli_json(
        capsys,
        [
            "edit",
            "1",
            "--generic-description",
            "  Genérica ",
            "--comment",
            "Primera\nSegunda\n",
        ],
    )
    assert (
        data["incident"]["editorial_description_preview"]
        == "  Genérica \nPrimera\nSegunda\n"
    )
    saved = get(a)
    assert saved.generic_description == "  Genérica "
    assert saved.custom_comment == "Primera\nSegunda\n"
    assert saved.exported is False


@pytest.mark.parametrize(
    "options",
    [
        ["--id", "2"],
        ["--audio-path", "/otro"],
        ["--audio-filename", "otro"],
        ["--exported", "true"],
        ["--created-at", "2020"],
        ["--updated-at", "2020"],
        [],
        ["--comment", "nuevo", "--clear-comment"],
    ],
)
def test_parser_rejects_invalid_type_protected_fields_and_ambiguous_edits(
    jobs, options
):
    _, a, _ = jobs
    add(a)
    before = job_database(a).read_bytes()
    with pytest.raises(SystemExit) as error:
        incidents_cli.main(["edit", "1", *options])
    assert error.value.code == 2
    assert job_database(a).read_bytes() == before


@pytest.mark.parametrize(
    "options",
    [
        ["--type", "INVALID"],
        ["--type", "text"],
        ["--position", "nan"],
        ["--position", "inf"],
        ["--page", "-1"],
        ["--document", ""],
        ["--selected-text", ""],
    ],
)
def test_invalid_model_values_rejected_before_write(jobs, capsys, options):
    _, a, _ = jobs
    add(a)
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["edit", "1", *options]) == 1
    assert capsys.readouterr().out == ""
    assert job_database(a).read_bytes() == before


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "created_at",
        "updated_at",
        "audio_filename",
        "audio_path",
        "exported",
        "unknown",
    ],
)
def test_service_protects_fields_independently_of_cli(jobs, field):
    _, a, _ = jobs
    add(a)
    with SQLiteIncidentRepository(job_database(a)) as repository:
        with pytest.raises(ReviewError, match="protegidos"):
            edit_incident(repository, 1, {field: "invalid"})


def test_unchanged_edit_does_not_write_or_refresh_updated_at(jobs, capsys):
    _, a, _ = jobs
    saved = add(a)
    before = job_database(a).read_bytes()
    cli_json(capsys, ["edit", "1", "--page", str(saved.page), "--clear-comment"])
    assert get(a) == saved
    assert job_database(a).read_bytes() == before


def test_explicit_job_never_uses_or_changes_active_job(jobs, capsys):
    store, a, b = jobs
    saved_a = add(a, selected_text="A")
    add(b, selected_text="B")
    a_before = job_database(a).read_bytes()
    data = cli_json(capsys, ["edit", "1", "--job", b.id, "--comment", "Solo B"])
    assert data["job"]["id"] == b.id
    assert get(b).custom_comment == "Solo B"
    assert job_database(a).read_bytes() == a_before and get(a) == saved_a
    assert store.active() == a
    store.select(None)
    data = cli_json(capsys, ["list", "--job", b.id])
    assert data["incidents"][0]["selected_text"] == "B"


@pytest.mark.parametrize("identifier", ["missing", "", str(uuid4())])
def test_missing_or_invalid_explicit_job_does_not_fall_back_to_active(
    jobs, capsys, identifier
):
    _, a, _ = jobs
    add(a)
    before = job_database(a).read_bytes()
    assert (
        incidents_cli.main(["edit", "1", "--job", identifier, "--comment", "No"]) == 1
    )
    assert capsys.readouterr().out == ""
    assert job_database(a).read_bytes() == before


def test_no_active_job_rejects_user_cli_without_creating_database(jobs, capsys):
    store, a, _ = jobs
    store.select(None)
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["list"]) == 1
    assert "No hay trabajo activo" in capsys.readouterr().err
    assert job_database(a).read_bytes() == before


def test_unavailable_database_never_created_by_review(jobs):
    _, a, _ = jobs
    job_database(a).unlink()
    assert incidents_cli.main(["list"]) == 1
    assert not job_database(a).exists()


def test_common_options_work_before_and_after_subcommand(jobs, capsys):
    _, _, b = jobs
    add(b)
    assert incidents_cli.main(["--job", b.id, "--json", "get", "1"]) == 0
    before = json.loads(capsys.readouterr().out)
    after = cli_json(capsys, ["get", "1", "--job", b.id])
    assert before == after


def test_technical_db_paths_are_not_exposed_in_user_cli(jobs):
    with pytest.raises(SystemExit):
        incidents_cli.main(["list", "--db", "/tmp/other.sqlite3"])


def test_review_rejected_while_capture_holds_destination_across_processes(jobs):
    store, a, _ = jobs
    saved = add(a)
    with store.destination():
        for args in [["edit", "1", "--comment", "No"], ["list"]]:
            result = subprocess.run(
                [sys.executable, "-m", "audiobook_qc.incidents_cli", *args],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 1 and "en curso" in result.stderr
            assert result.stdout == ""
    assert get(a) == saved


def test_edit_holds_lock_against_selection_other_edit_and_capture(
    jobs, monkeypatch, capsys
):
    store, a, b = jobs
    add(a)
    original = SQLiteIncidentRepository.update
    monkeypatch.setattr(capture_save_probe, "check_desktop_activation", lambda: None)
    monkeypatch.setattr(capture_save_probe, "notify", lambda *a, **kw: None)
    monkeypatch.setattr(
        capture_save_probe, "capture_incident", lambda *a, **kw: pytest.fail("captura")
    )

    def update(repository, entity):
        with pytest.raises(ActivationBusy):
            store.select(b.id)
        assert incidents_cli.main(["edit", "1", "--comment", "Otro"]) == 1
        assert capture_save_probe.main(["--desktop", "INTER"]) == 1
        return original(repository, entity)

    monkeypatch.setattr(SQLiteIncidentRepository, "update", update)
    cli_json(capsys, ["edit", "1", "--comment", "Original"])
    assert get(a).custom_comment == "Original" and store.active() == a


def test_huge_valid_timestamp_keeps_detail_available(jobs, capsys):
    _, a, _ = jobs
    add(a, audio_position_seconds=1.7e308)
    data = cli_json(capsys, ["get", "1"])
    assert data["incident"]["audio_position_seconds"] == 1.7e308
    hours, minutes, seconds = map(
        int, data["incident"]["audio_position_formatted"].split(":")
    )
    assert hours * 3600 + minutes * 60 + seconds == int(1.7e308)


@pytest.mark.parametrize(
    "seconds,formatted",
    [
        (120.081537, "00:02:00"),
        (240.413568, "00:04:00"),
        (300.11545, "00:05:00"),
        (120.999, "00:02:00"),
        (59.999, "00:00:59"),
        (3599.999, "00:59:59"),
        (3600.999, "01:00:00"),
        (3661.999, "01:01:01"),
        (90061.999, "25:01:01"),
        (360000.999, "100:00:00"),
        (0.999, "00:00:00"),
        (-120.999, "-00:02:00"),
    ],
)
def test_editorial_position_truncates_without_changing_stored_or_json_precision(
    jobs, capsys, seconds, formatted
):
    _, a, _ = jobs
    add(a, audio_position_seconds=seconds)
    before = job_database(a).read_bytes()
    for args in (["get", "1"], ["list"]):
        data = cli_json(capsys, args)
        view = data["incident"] if "incident" in data else data["incidents"][0]
        assert view["audio_position_formatted"] == formatted
        assert view["audio_position_seconds"].hex() == seconds.hex()
        assert incidents_cli.main(args) == 0
        assert formatted in capsys.readouterr().out
    assert get(a).audio_position_seconds.hex() == seconds.hex()
    assert job_database(a).read_bytes() == before
