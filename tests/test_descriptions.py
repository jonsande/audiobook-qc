"""Catálogo y revisión con SQLite real, configuración y escritorio aislados."""

import json
import subprocess
import sys
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiobook_qc import capture_save_probe, descriptions_cli, incidents_cli
from audiobook_qc.captured_incident import CapturedIncident, IncidentType
from audiobook_qc.description_config import catalog_path, load_catalog
from audiobook_qc.descriptions import CatalogError
from audiobook_qc.incident import Incident
from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.jobs import JobStore, job_database
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository


def entry(identifier="pron", text="  Pronunciación e\u0301\n¿ñ?  ", types=None):
    return dict(id=identifier, text=text, incident_types=types or ["PRON"])


def write_catalog(entries=None):
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            dict(version=1, descriptions=entries if entries is not None else [entry()]),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def jobs(tmp_path):
    store = JobStore()
    store.configure(str(tmp_path / "jobs"))
    a, b = store.create("A"), store.create("B")
    for job in (a, b):
        with SQLiteIncidentRepository(job_database(job), existing=True) as repo:
            repo.add(
                Incident(
                    "PRON",
                    "audio.mp3",
                    "/audio.mp3",
                    120.081537,
                    "/libro.pdf",
                    2,
                    "Selección",
                    exported=True,
                )
            )
    store.select(a.id)
    write_catalog()
    return store, a, b


def read(job):
    with SQLiteIncidentRepository(job_database(job), existing=True) as repo:
        return repo.get(1)


def cli(capsys, *args):
    assert incidents_cli.main([*args, "--json"]) == 0
    return json.loads(capsys.readouterr().out)["incident"]


def test_valid_catalog_unicode_order_and_multiple_types():
    entries = [entry(), entry("shared", "Otra", ["PRON", "TEXT"])]
    write_catalog(entries)
    catalog = load_catalog()
    assert [asdict(item) for item in catalog.list()] == [
        item
        | {"incident_types": tuple(IncidentType(t) for t in item["incident_types"])}
        for item in entries
    ]
    assert [item.id for item in catalog.list(IncidentType.PRON)] == ["pron", "shared"]
    assert [item.id for item in catalog.list(IncidentType.TEXT)] == ["shared"]
    assert catalog.list(IncidentType.RUID) == ()


def test_xdg_path(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom"))
    assert catalog_path() == tmp_path / "custom/audiobook-qc/descriptions.json"


@pytest.mark.parametrize("value", [None, ""])
def test_fallback(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv("XDG_CONFIG_HOME")
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", value)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert catalog_path() == tmp_path / ".config/audiobook-qc/descriptions.json"


def test_relative_xdg_rejected(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative")
    with pytest.raises(CatalogError, match="absoluto"):
        load_catalog()


def test_empty_catalog_and_cli(capsys):
    write_catalog([])
    assert load_catalog().descriptions == ()
    assert descriptions_cli.main(["list"]) == 0
    assert "Sin descripciones" in capsys.readouterr().out
    assert descriptions_cli.main(["validate", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 0


@pytest.mark.parametrize(
    "entries",
    [
        [entry(), entry()],
        [entry(types=["INVALID"])],
        [entry(types=["pron"])],
        [entry(text="")],
        [entry(text=" \n\t")],
        [entry(text=None)],
        [entry() | {"text": 12}],
        [entry() | {"incident_types": []}],
        [entry(types=["PRON", "PRON"])],
        [entry() | {"incident_types": "PRON"}],
        [entry() | {"incident_types": [True]}],
        [entry() | {"extra": "unknown"}],
        [{"id": "pron", "incident_types": ["PRON"]}],
        [entry(identifier="")],
        [entry(identifier="spaces invalid")],
        [entry(identifier=12)],
        [None],
    ],
)
def test_invalid_entries(entries):
    write_catalog(entries)
    with pytest.raises(CatalogError):
        load_catalog()


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"\xff",
        b"[]",
        b"null",
        b"{}",
        b'{"version":true,"descriptions":[]}',
        b'{"version":2,"descriptions":[]}',
        b'{"version":1,"descriptions":{}}',
        b'{"version":1,"descriptions":[],"extra":0}',
        b'{"version":1,"version":1,"descriptions":[]}',
        b'{"version":1,"descriptions":[{"id":"a","id":"b"}]}',
    ],
)
def test_corrupt_structure_has_clear_path_error(raw, capsys):
    path = write_catalog()
    path.write_bytes(raw)
    with pytest.raises(CatalogError, match=str(path)):
        load_catalog()
    assert descriptions_cli.main(["validate", "--json"]) == 1
    output = capsys.readouterr()
    assert output.out == "" and str(path) in output.err


def test_missing_catalog_is_error_without_creation(capsys):
    assert descriptions_cli.main(["list"]) == 1
    assert str(catalog_path()) in capsys.readouterr().err
    assert not catalog_path().exists()


def test_list_filter_human_json_and_validate(capsys):
    entries = [entry(), entry("noise", "Ruido provisional", ["RUID"])]
    write_catalog(entries)
    assert descriptions_cli.main(["--json", "list"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {
        "catalog": str(catalog_path()),
        "version": 1,
        "descriptions": entries,
    }
    assert descriptions_cli.main(["list", "PRON", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["descriptions"] == entries[:1]
    assert descriptions_cli.main(["list", "RUID"]) == 0
    output = capsys.readouterr().out
    assert "noise" in output and "Ruido provisional" in output and "RUID" in output
    assert descriptions_cli.main(["validate"]) == 0
    assert "válido" in capsys.readouterr().out


def test_assignment_preserves_fields_completeness_history_and_job_isolation(
    jobs, capsys, monkeypatch
):
    store, a, b = jobs
    before = read(a)
    b_bytes = job_database(b).read_bytes()
    now = before.updated_at + timedelta(seconds=1)
    monkeypatch.setattr("audiobook_qc.sqlite_repository.utc_now", lambda: now)
    assert not before.editorially_complete
    result = cli(capsys, "edit", "1", "--generic-description-id", "pron")
    assert result["editorially_complete"] is True
    after = read(a)
    assert after.generic_description == entry()["text"]
    assert after.updated_at == now
    assert after.exported is before.exported is True
    assert after.custom_comment is None
    write_catalog([entry(text="Texto cambiado")])
    assert read(a) == after
    assert job_database(b).read_bytes() == b_bytes
    cli(capsys, "edit", "1", "--clear-generic-description")
    assert not read(a).editorially_complete
    assert store.active() == a


def test_assignment_preserves_multiline_comment_and_explicit_job(jobs, capsys):
    store, a, b = jobs
    comment = "  Línea ñ\nSegunda\r\n"
    cli(capsys, "edit", "1", "--comment", comment)
    store.select(b.id)
    b_bytes = job_database(b).read_bytes()
    cli(capsys, "--job", a.id, "edit", "1", "--generic-description-id", "pron")
    assert read(a).custom_comment == comment
    assert read(a).generic_description == entry()["text"]
    assert job_database(b).read_bytes() == b_bytes
    assert store.active() == b


@pytest.mark.parametrize("case", ["unknown", "incompatible", "missing", "corrupt"])
def test_rejections_never_write_sqlite(jobs, capsys, case):
    _, a, _ = jobs
    identifier, incident_id = "pron", "1"
    if case == "unknown":
        identifier = "absent"
    elif case == "incompatible":
        write_catalog([entry(types=["TEXT"])])
    elif case == "missing":
        incident_id = "999"
    else:
        catalog_path().write_text("{", encoding="utf-8")
    before = job_database(a).read_bytes()
    assert (
        incidents_cli.main(
            [
                "edit",
                incident_id,
                "--generic-description-id",
                identifier,
                "--comment",
                "No",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert output.out == "" and output.err
    assert job_database(a).read_bytes() == before


def test_manual_descriptions_and_other_edits_ignore_corrupt_catalog(jobs, capsys):
    _, a, _ = jobs
    catalog_path().write_text("{", encoding="utf-8")
    cli(capsys, "edit", "1", "--generic-description", "Manual fuera del catálogo")
    cli(capsys, "edit", "1", "--comment", "Comentario")
    assert read(a).generic_description == "Manual fuera del catálogo"
    assert read(a).editorially_complete
    cli(capsys, "get", "1")


def test_type_change_rejected_then_clear_or_replace_or_compatible_id(jobs, capsys):
    _, a, _ = jobs
    cli(capsys, "edit", "1", "--generic-description-id", "pron")
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["edit", "1", "--type", "TEXT"]) == 1
    assert "Elimina o reemplaza" in capsys.readouterr().err
    assert job_database(a).read_bytes() == before
    # Cambiar el tipo y seleccionar un ID se valida contra el tipo resultante.
    assert (
        incidents_cli.main(
            ["edit", "1", "--type", "TEXT", "--generic-description-id", "pron"]
        )
        == 1
    )
    capsys.readouterr()
    assert job_database(a).read_bytes() == before
    cli(capsys, "edit", "1", "--type", "TEXT", "--clear-generic-description")
    assert read(a).incident_type == IncidentType.TEXT
    cli(capsys, "edit", "1", "--generic-description", "Manual")
    cli(capsys, "edit", "1", "--type", "PRON", "--generic-description", "Otra manual")
    write_catalog([entry(types=["PRON", "TEXT"])])
    cli(capsys, "edit", "1", "--generic-description-id", "pron")
    cli(capsys, "edit", "1", "--type", "TEXT", "--generic-description-id", "pron")
    assert read(a).incident_type == IncidentType.TEXT


@pytest.mark.parametrize(
    "other", ["--generic-description", "--clear-generic-description"]
)
def test_id_cannot_be_combined_with_manual_or_clear(jobs, other):
    _, a, _ = jobs
    before = job_database(a).read_bytes()
    options = [other, "manual"] if other == "--generic-description" else [other]
    with pytest.raises(SystemExit):
        incidents_cli.main(["edit", "1", "--generic-description-id", "pron", *options])
    assert job_database(a).read_bytes() == before


def test_assignment_uses_lock_and_blocks_capture_selection_other_edit(
    jobs, monkeypatch, capsys
):
    store, a, b = jobs
    original = SQLiteIncidentRepository.update
    monkeypatch.setattr(capture_save_probe, "check_desktop_activation", lambda: None)
    monkeypatch.setattr(capture_save_probe, "notify", lambda *a, **kw: None)

    def update(repository, entity):
        with pytest.raises(ActivationBusy):
            store.select(b.id)
        assert (
            incidents_cli.main(["edit", "1", "--generic-description-id", "pron"]) == 1
        )
        assert capture_save_probe.main(["--desktop", "PRON"]) == 1
        return original(repository, entity)

    monkeypatch.setattr(SQLiteIncidentRepository, "update", update)
    cli(capsys, "edit", "1", "--generic-description-id", "pron")
    assert read(a).generic_description == entry()["text"]
    assert store.active() == a


def test_assignment_rejected_by_capture_lock_across_processes(jobs):
    store, a, _ = jobs
    before = job_database(a).read_bytes()
    with store.destination():
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "audiobook_qc.incidents_cli",
                "edit",
                "1",
                "--generic-description-id",
                "pron",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 1 and "en curso" in result.stderr
    assert job_database(a).read_bytes() == before


@pytest.mark.parametrize("code", [t.value for t in IncidentType])
def test_desktop_capture_all_seven_codes_ignores_invalid_catalog(
    jobs, monkeypatch, capsys, code
):
    _, a, _ = jobs
    catalog_path().write_text("{", encoding="utf-8")
    monkeypatch.setattr(capture_save_probe, "check_desktop_activation", lambda: None)
    monkeypatch.setattr(capture_save_probe, "notify", lambda *a, **kw: None)
    monkeypatch.setattr(
        capture_save_probe,
        "prepare_job_sources",
        lambda job: SimpleNamespace(
            read_document=lambda: None,
            read_audio=lambda: None,
            verify=lambda captured: None,
        ),
    )
    monkeypatch.setattr(
        capture_save_probe,
        "capture_incident",
        lambda code, **kw: CapturedIncident(
            IncidentType(code),
            "cap.mp3",
            "/cap.mp3",
            120.081537,
            "/libro.pdf",
            3,
            "Selección",
        ),
    )
    assert capture_save_probe.main(["--desktop", code]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["incident_type"] == code
    with SQLiteIncidentRepository(job_database(a), existing=True) as repo:
        assert len(repo.list()) == 2
        assert repo.get(2).incident_type == IncidentType(code)


def test_service_requires_validated_catalog_and_rejects_ambiguous_selection(jobs):
    from audiobook_qc.incident_review import ReviewError, edit_incident

    _, a, _ = jobs
    before = job_database(a).read_bytes()
    with SQLiteIncidentRepository(job_database(a), existing=True) as repo:
        with pytest.raises(ReviewError, match="catálogo validado"):
            edit_incident(repo, 1, {}, description_id="pron")
        with pytest.raises(ReviewError, match="No combines"):
            edit_incident(
                repo,
                1,
                {"generic_description": "manual"},
                catalog=load_catalog(),
                description_id="pron",
            )
    assert job_database(a).read_bytes() == before


def test_reassign_same_text_does_not_write_or_refresh_timestamp(jobs, capsys):
    _, a, _ = jobs
    cli(capsys, "edit", "1", "--generic-description-id", "pron")
    saved = read(a)
    before = job_database(a).read_bytes()
    cli(capsys, "edit", "1", "--generic-description-id", "pron")
    assert read(a) == saved
    assert job_database(a).read_bytes() == before


def test_type_policy_does_not_infer_provenance_or_read_current_catalog(jobs, capsys):
    _, a, _ = jobs
    cli(capsys, "edit", "1", "--generic-description", "Texto histórico manual")
    catalog_path().unlink()
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["edit", "1", "--type", "TEXT"]) == 1
    assert "podría ser incompatible" in capsys.readouterr().err
    assert job_database(a).read_bytes() == before
    cli(capsys, "edit", "1", "--clear-generic-description")
    cli(capsys, "edit", "1", "--type", "TEXT")
    assert read(a).incident_type == IncidentType.TEXT
