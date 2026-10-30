"""Tipos/atajos configurables, historial y migración explícita con SQLite real."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiobook_qc import (
    capture_save_probe,
    descriptions_cli,
    incidents_cli,
    jobs_cli,
    types_cli,
)
from audiobook_qc.capture import CaptureError, capture_incident
from audiobook_qc.capture_and_save import capture_and_save_incident
from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.description_config import catalog_path, load_catalog
from audiobook_qc.incident import Incident
from audiobook_qc.incident_review import ReviewError, edit_incident
from audiobook_qc.integrations.mpv import MpvState
from audiobook_qc.integrations.okular import OkularState
from audiobook_qc.integrations.selection import Selection
from audiobook_qc.jobs import JobStore, job_database
from audiobook_qc.sqlite_repository import SchemaError, SQLiteIncidentRepository
from audiobook_qc.type_catalog import TypeConfigError
from audiobook_qc.type_config import (
    install_initial_types,
    load_types,
    types_data,
    types_path,
)


def config():
    return json.loads(types_path().read_text(encoding="utf-8"))


def save(data):
    types_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def set_type(identifier, **changes):
    data = config()
    item = next(item for item in data["types"] if item["id"] == identifier)
    item.update(changes)
    if changes.get("enabled") is False:
        data["hotkeys"] = {
            key: None if value == identifier else value
            for key, value in data["hotkeys"].items()
        }
    save(data)


def add_music():
    data = config()
    data["types"].append(
        dict(
            id="MUSI",
            label="Música ñ",
            enabled=True,
            default_generic_description="Revisar música.",
        )
    )
    data["hotkeys"]["F7"] = "MUSI"
    save(data)


def entity(code="PRON", **changes):
    return Incident(
        code,
        "cap.mp3",
        "/cap.mp3",
        120.081537,
        "/libro.pdf",
        3,
        "Selección ñ",
        **changes,
    )


@pytest.fixture
def jobs(tmp_path):
    store = JobStore()
    store.configure(str(tmp_path / "jobs"))
    a, b = store.create("A"), store.create("B")
    for job in (a, b):
        with SQLiteIncidentRepository(job_database(job), existing=True) as repo:
            repo.add(entity())
    store.select(a.id)
    return store, a, b


@pytest.fixture
def desktop(monkeypatch):
    monkeypatch.setattr(capture_save_probe, "check_desktop_activation", lambda: None)
    monkeypatch.setattr(capture_save_probe, "notify", lambda *a, **kw: None)
    monkeypatch.setattr(
        capture_save_probe.selection,
        "read_selection",
        lambda name: Selection("primary", "Selección ñ"),
    )
    monkeypatch.setattr(
        capture_save_probe,
        "prepare_job_sources",
        lambda job: SimpleNamespace(
            read_document=lambda: OkularState("test", "/libro.pdf", None, 3),
            read_audio=lambda: MpvState("cap.mp3", "/cap.mp3", 120.081537, None, True),
            verify=lambda captured: None,
        ),
    )


def read(job, identifier=1):
    with SQLiteIncidentRepository(job_database(job), existing=True) as repo:
        return repo.get(identifier)


def review(capsys, *args):
    assert incidents_cli.main([*args, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def capture(capsys, hotkey):
    assert capture_save_probe.main(["--desktop", "--hotkey", hotkey]) == 0
    return json.loads(capsys.readouterr().out)


def test_initial_real_configuration_and_order():
    catalog = load_types()
    assert [
        (t.id, t.label, t.enabled, t.default_generic_description) for t in catalog.types
    ] == [
        ("TEXT", "Texto", True, None),
        ("PRON", "Pronunciación", True, "Revisar pronunciación."),
        ("DICC", "Dicción", True, "Revisar dicción."),
        ("RUID", "Ruido", True, "Ruido."),
        ("RESP", "Respiración", True, "Respiración."),
        ("INTER", "Entonación", True, "Revisar entonación."),
        ("OTRO", "Otro", True, None),
    ]
    assert list(dict(catalog.hotkeys).items()) == [
        (f"F{i}", item.id) for i, item in enumerate(catalog.types, 1)
    ]
    assert types_data(catalog) == config()


def test_xdg_location_and_missing_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "other"))
    assert types_path() == tmp_path / "other/audiobook-qc/incident_types.json"
    with pytest.raises(TypeConfigError, match="types_cli init"):
        load_types()
    assert not types_path().exists()


@pytest.mark.parametrize("value", ["", None])
def test_home_fallback(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv("XDG_CONFIG_HOME")
    else:
        monkeypatch.setenv("XDG_CONFIG_HOME", value)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert types_path() == tmp_path / ".config/audiobook-qc/incident_types.json"


def test_relative_xdg_rejected(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative")
    with pytest.raises(TypeConfigError, match="absoluto"):
        load_types()


def test_explicit_install_no_overwrite_or_partial_file(capsys):
    path = types_path()
    original = path.read_bytes()
    assert types_cli.main(["init"]) == 1
    assert path.read_bytes() == original
    assert not list(path.parent.glob(".incident_types-*"))
    capsys.readouterr()
    path.unlink()
    assert types_cli.main(["init", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["types"][1]["id"] == "PRON"
    assert path.read_bytes() == original


def test_install_does_not_overwrite_symlink(tmp_path):
    path = types_path()
    path.unlink()
    other = tmp_path / "other.json"
    other.write_text("do not replace")
    path.symlink_to(other)
    with pytest.raises(FileExistsError):
        install_initial_types()
    assert path.is_symlink() and other.read_text() == "do not replace"


@pytest.mark.parametrize(
    "patch",
    [
        {"id": ""},
        {"id": "lower"},
        {"id": None},
        {"id": "PRON-"},
        {"label": None},
        {"label": " \n"},
        {"label": 1},
        {"enabled": 1},
        {"enabled": "true"},
        {"enabled": None},
        {"default_generic_description": 12},
        {"extra": "unknown"},
    ],
)
def test_invalid_type_fields(patch):
    data = config()
    data["types"][1].update(patch)
    save(data)
    with pytest.raises(TypeConfigError):
        load_types()


@pytest.mark.parametrize(
    "field", ["id", "label", "enabled", "default_generic_description"]
)
def test_missing_field(field):
    data = config()
    del data["types"][0][field]
    save(data)
    with pytest.raises(TypeConfigError):
        load_types()


def test_duplicate_type_ids():
    data = config()
    data["types"].append(data["types"][0])
    save(data)
    with pytest.raises(TypeConfigError, match="duplicados"):
        load_types()


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "[]",
        "null",
        "{}",
        '{"version":true,"types":[],"hotkeys":{}}',
        '{"version":2,"types":[],"hotkeys":{}}',
        '{"version":1,"types":{},"hotkeys":{}}',
        '{"version":1,"types":[],"hotkeys":[]}',
        '{"version":1,"version":1,"types":[],"hotkeys":{}}',
        '{"version":1,"types":[],"hotkeys":{"F1":null,"F1":null}}',
        '{"version":1,"types":[],"hotkeys":{},"unknown":null}',
    ],
)
def test_corrupt_structure(raw, capsys):
    types_path().write_text(raw)
    assert types_cli.main(["validate", "--json"]) == 1
    output = capsys.readouterr()
    assert output.out == "" and str(types_path()) in output.err


def test_invalid_utf8(capsys):
    types_path().write_bytes(b"\xff")
    assert types_cli.main(["list"]) == 1
    assert "Error de tipos" in capsys.readouterr().err


@pytest.mark.parametrize("formula", [None, "", " \n", " Fórmula e\u0301\nñ "])
def test_nullable_empty_unicode_formulas(formula):
    set_type("PRON", default_generic_description=formula)
    assert load_types().get("PRON").default_generic_description == formula


def test_cli_consultation_json_human_and_label_changes(capsys):
    set_type("PRON", label="Revisar pronunciación ñ")
    assert types_cli.main(["--json", "list"]) == 0
    assert (
        json.loads(capsys.readouterr().out)["types"][1]["label"]
        == "Revisar pronunciación ñ"
    )
    assert types_cli.main(["get", "PRON", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["type"] == asdict(load_types().get("PRON"))
    assert types_cli.main(["hotkeys", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["hotkeys"] == config()["hotkeys"]
    assert types_cli.main(["validate"]) == 0
    assert "válida" in capsys.readouterr().out
    assert types_cli.main(["list"]) == 0
    assert "Revisar pronunciación ñ" in capsys.readouterr().out
    assert types_cli.main(["get", "MISSING"]) == 1
    assert "inexistente" in capsys.readouterr().err


def test_empty_catalog_and_unassigned_hotkeys():
    save(dict(version=1, types=[], hotkeys={"F1": None}))
    assert load_types().types == ()
    with pytest.raises(TypeConfigError, match="sin asignación"):
        load_types().resolve_hotkey("F2")


@pytest.mark.parametrize("mapping", [{"F8": "PRON"}, {"F1": "MISSING"}, {"F2": True}])
def test_invalid_hotkey_mapping(mapping):
    data = config()
    data["hotkeys"] = mapping
    save(data)
    with pytest.raises(TypeConfigError):
        load_types()


def test_disabled_type_must_be_unbound():
    data = config()
    data["types"][4]["enabled"] = False
    save(data)
    with pytest.raises(TypeConfigError, match="deshabilitado"):
        load_types()


def test_hotkey_reassignment_new_type_and_no_automatic_formula(jobs, desktop, capsys):
    _, a, b = jobs
    before_b = job_database(b).read_bytes()
    pron = capture(capsys, "F2")
    assert pron["incident_type"] == "PRON" and pron["generic_description"] is None
    data = config()
    data["hotkeys"]["F2"] = "DICC"
    save(data)
    assert capture(capsys, "F2")["incident_type"] == "DICC"
    add_music()
    music = capture(capsys, "F7")
    assert music["incident_type"] == "MUSI"
    assert read(a, music["id"]).incident_type == "MUSI"
    view = review(capsys, "get", str(music["id"]))["incident"]
    assert view["incident_type_info"] == dict(
        id="MUSI", label="Música ñ", enabled=True, status="enabled"
    )
    assert job_database(b).read_bytes() == before_b


@pytest.mark.parametrize(
    "case", ["unbound", "disabled", "missing", "corrupt", "absent"]
)
def test_unsafe_capture_fails_before_sources_and_write(jobs, capsys, monkeypatch, case):
    _, a, _ = jobs
    if case == "corrupt":
        types_path().write_text("{")
    elif case == "absent":
        types_path().unlink()
    else:
        data = config()
        data["hotkeys"]["F2"] = (
            None if case == "unbound" else "MISSING" if case == "missing" else "PRON"
        )
        if case == "disabled":
            data["types"][1]["enabled"] = False
        save(data)
    monkeypatch.setattr(capture_save_probe, "check_desktop_activation", lambda: None)
    monkeypatch.setattr(capture_save_probe, "notify", lambda *a, **kw: None)
    monkeypatch.setattr(
        capture_save_probe, "prepare_job_sources", lambda *a: pytest.fail("fuentes")
    )
    before = job_database(a).read_bytes()
    assert capture_save_probe.main(["--desktop", "--hotkey", "F2"]) == 1
    assert capsys.readouterr().out == ""
    assert job_database(a).read_bytes() == before


def test_disable_reactivate_historical_read_edit_and_direct_capture(
    jobs, desktop, capsys
):
    _, a, _ = jobs
    old = capture(capsys, "F5")
    set_type("RESP", enabled=False)
    before = job_database(a).read_bytes()
    view = review(capsys, "get", str(old["id"]))["incident"]
    assert (
        view["incident_type"] == "RESP"
        and view["incident_type_info"]["status"] == "disabled"
    )
    assert job_database(a).read_bytes() == before
    assert capture_save_probe.main(["--desktop", "RESP"]) == 1
    capsys.readouterr()
    assert incidents_cli.main(["edit", "1", "--type", "RESP"]) == 1
    capsys.readouterr()
    assert job_database(a).read_bytes() == before
    review(capsys, "edit", str(old["id"]), "--comment", "Revisión histórica")
    set_type("RESP", enabled=True)
    assert capture_save_probe.main(["--desktop", "RESP"]) == 0


def test_removed_type_stays_readable_and_editable_without_reassignment(
    jobs, desktop, capsys
):
    _, a, _ = jobs
    saved = capture(capsys, "F5")
    data = config()
    data["types"] = [t for t in data["types"] if t["id"] != "RESP"]
    data["hotkeys"]["F5"] = None
    save(data)
    before = job_database(a).read_bytes()
    info = review(capsys, "get", str(saved["id"]))["incident"]["incident_type_info"]
    assert info == dict(id="RESP", label="RESP", enabled=None, status="historical")
    assert job_database(a).read_bytes() == before
    review(
        capsys, "edit", str(saved["id"]), "--generic-description", "Manual histórica"
    )
    assert read(a, saved["id"]).generic_description == "Manual histórica"
    assert incidents_cli.main(["edit", "1", "--type", "RESP"]) == 1


def test_corrupt_config_degrades_review_json_and_manual_edits_safely(jobs, capsys):
    _, a, _ = jobs
    types_path().write_text("{")
    before = job_database(a).read_bytes()
    data = review(capsys, "list")
    assert "type_configuration_error" in data
    assert data["incidents"][0]["incident_type_info"]["status"] == "unavailable"
    assert job_database(a).read_bytes() == before
    review(
        capsys, "edit", "1", "--generic-description", "Manual", "--comment", "Libre\nñ"
    )
    assert read(a).custom_comment == "Libre\nñ"
    before = job_database(a).read_bytes()
    for options in (["--type", "TEXT"], ["--default-description"]):
        assert incidents_cli.main(["edit", "1", *options]) == 1
        capsys.readouterr()
        assert job_database(a).read_bytes() == before


def test_default_formula_snapshot_comment_exported_and_updated_at(jobs, capsys):
    _, a, b = jobs
    review(capsys, "edit", "1", "--comment", " \n")
    before = read(a)
    assert not before.editorially_complete
    b_bytes = job_database(b).read_bytes()
    result = review(capsys, "edit", "1", "--default-description")["incident"]
    assert result["generic_description"] == "Revisar pronunciación."
    assert result["editorially_complete"] is True
    saved = read(a)
    assert saved.custom_comment == before.custom_comment
    assert saved.exported == before.exported and saved.updated_at > before.updated_at
    set_type(
        "PRON", default_generic_description="Fórmula nueva.", label="Etiqueta nueva"
    )
    assert read(a) == saved
    assert (
        review(capsys, "get", "1")["incident"]["incident_type_info"]["label"]
        == "Etiqueta nueva"
    )
    review(capsys, "edit", "1", "--default-description")
    assert read(a).generic_description == "Fórmula nueva."
    assert job_database(b).read_bytes() == b_bytes


@pytest.mark.parametrize("formula", [None, "", " \n"])
def test_no_effective_default_rejects_without_erasing(jobs, capsys, formula):
    _, a, _ = jobs
    review(capsys, "edit", "1", "--generic-description", "Manual")
    set_type("PRON", default_generic_description=formula)
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["edit", "1", "--default-description"]) == 1
    assert "no tiene fórmula" in capsys.readouterr().err
    assert job_database(a).read_bytes() == before


def test_new_type_edit_default_and_safe_type_change(jobs, capsys):
    _, a, _ = jobs
    add_music()
    review(capsys, "edit", "1", "--default-description")
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["edit", "1", "--type", "MUSI"]) == 1
    assert "Elimina o reemplaza" in capsys.readouterr().err
    assert job_database(a).read_bytes() == before
    result = review(capsys, "edit", "1", "--type", "MUSI", "--default-description")[
        "incident"
    ]
    assert result["incident_type"] == "MUSI"
    assert result["generic_description"] == "Revisar música."
    review(capsys, "edit", "1", "--generic-description", "Manual ajena")
    assert read(a).generic_description == "Manual ajena"


@pytest.mark.parametrize("identifier", ["MISSING", "bad", ""])
def test_unknown_new_type_rejected(jobs, capsys, identifier):
    _, a, _ = jobs
    before = job_database(a).read_bytes()
    assert incidents_cli.main(["edit", "1", "--type", identifier]) == 1
    capsys.readouterr()
    assert job_database(a).read_bytes() == before


def test_existing_description_catalog_supports_new_types(jobs, capsys):
    _, a, _ = jobs
    add_music()
    catalog_path().write_text(
        json.dumps(
            dict(
                version=1,
                descriptions=[
                    dict(
                        id="music",
                        text="Otra fórmula de música.",
                        incident_types=["MUSI"],
                    )
                ],
            )
        ),
        encoding="utf-8",
    )
    assert load_catalog().resolve("music", "MUSI") == "Otra fórmula de música."
    assert descriptions_cli.main(["list", "MUSI", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["descriptions"][0]["id"] == "music"
    review(capsys, "edit", "1", "--type", "MUSI", "--generic-description-id", "music")
    assert read(a).generic_description == "Otra fórmula de música."


def test_snapshot_consistency_during_capture(jobs, desktop, capsys, monkeypatch):
    original = capture_save_probe.prepare_job_sources

    def prepare(job):
        data = config()
        data["hotkeys"]["F2"] = "DICC"
        save(data)
        return original(job)

    monkeypatch.setattr(capture_save_probe, "prepare_job_sources", prepare)
    assert capture(capsys, "F2")["incident_type"] == "PRON"
    assert capture(capsys, "F2")["incident_type"] == "DICC"


def test_domain_services_require_enabled_catalog_without_io(jobs):
    _, a, _ = jobs
    types = load_types()
    set_type("PRON", enabled=False)
    disabled = load_types()
    with SQLiteIncidentRepository(job_database(a), existing=True) as repo:
        with pytest.raises(TypeConfigError, match="deshabilitado"):
            capture_and_save_incident(
                "PRON",
                types=disabled,
                repository=repo,
                capture=lambda code: pytest.fail("captura"),
            )
        with pytest.raises(ReviewError, match="catálogo de tipos"):
            edit_incident(repo, 1, {"incident_type": "TEXT"})
        with pytest.raises(ValueError, match="otro tipo"):
            capture_and_save_incident(
                "TEXT",
                types=types,
                repository=repo,
                capture=lambda code: CapturedIncident(
                    "PRON", "c", "/c", 1.1, "/p", 1, "t"
                ),
            )
    with pytest.raises(CaptureError, match="Código de incidencia inválido"):
        capture_incident(
            "PRON",
            types=disabled,
            read_primary=lambda: pytest.fail("PRIMARY"),
            read_document=lambda: None,
            read_audio=lambda: None,
        )


@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    sql = Path(__file__).with_name("fixtures").joinpath("incidents_v1.sql").read_text()
    with sqlite3.connect(path) as connection:
        connection.executescript(sql)
    with SQLiteIncidentRepository(path, existing=True) as repo:
        repo.add(
            entity(generic_description="Histórica", custom_comment="ñ\n", exported=True)
        )
        deleted = repo.add(entity("RESP"))
        repo.delete(deleted.id)
    return path


def test_legacy_reads_and_initialization_never_migrate(legacy):
    before = legacy.read_bytes()
    with SQLiteIncidentRepository(legacy, existing=True) as repo:
        repo.initialize()
        repo.validate_schema()
        assert repo.get(1).generic_description == "Histórica"
        assert len(repo.list()) == 1
        with pytest.raises(SchemaError, match="migración explícita"):
            repo.add(entity("MUSI"))
    assert legacy.read_bytes() == before


def test_explicit_migration_preserves_all_values_sequence_and_is_idempotent(legacy):
    with SQLiteIncidentRepository(legacy, existing=True) as repo:
        original = repo.list()
        assert repo.migrate_types() is True
        assert repo.list() == original
        assert (
            repo.get(1).audio_position_seconds.hex()
            == original[0].audio_position_seconds.hex()
        )
        assert repo.add(entity("MUSI")).id == 3
        assert repo.migrate_types() is False
    with sqlite3.connect(legacy) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_empty_legacy_migration(tmp_path):
    path = tmp_path / "empty.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            Path(__file__)
            .with_name("fixtures")
            .joinpath("incidents_v1.sql")
            .read_text()
        )
    with SQLiteIncidentRepository(path, existing=True) as repo:
        assert repo.migrate_types()
        assert repo.add(entity("MUSI")).id == 1


@pytest.mark.parametrize("damage", ["index", "extra_column", "invalid_data"])
def test_migration_failure_rolls_back_without_changing_history(legacy, damage):
    with sqlite3.connect(legacy) as connection:
        if damage == "index":
            connection.execute("CREATE INDEX extra ON incidents (page)")
        elif damage == "extra_column":
            connection.execute("ALTER TABLE incidents ADD COLUMN extra TEXT")
        else:
            connection.execute("PRAGMA ignore_check_constraints=ON")
            connection.execute(
                "UPDATE incidents SET created_at='2026-01-01T00:00:00+00:00'"
            )
    before = legacy.read_bytes()
    with SQLiteIncidentRepository(legacy, existing=True) as repo:
        with pytest.raises((SchemaError, sqlite3.IntegrityError)):
            repo.migrate_types()
    assert legacy.read_bytes() == before
    with sqlite3.connect(legacy) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_migration_cli_uses_job_lock_and_does_not_change_active(jobs, legacy, capsys):
    store, a, b = jobs
    job_database(a).write_bytes(legacy.read_bytes())
    store.select(b.id)
    b_before = job_database(b).read_bytes()
    with store.destination():
        assert jobs_cli.main(["migrate-types", a.id]) == 1
    capsys.readouterr()
    assert jobs_cli.main(["migrate-types", a.id]) == 0
    assert json.loads(capsys.readouterr().out)["migrated"] is True
    assert store.active() == b and job_database(b).read_bytes() == b_before
    assert read(a).generic_description == "Histórica"


def test_malformed_historical_id_is_not_treated_as_valid(legacy):
    with sqlite3.connect(legacy) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute("UPDATE incidents SET incident_type='bad-id'")
    with SQLiteIncidentRepository(legacy, existing=True) as repo:
        with pytest.raises(TypeConfigError, match="ID de tipo"):
            repo.list()


def test_migration_preserves_sequence_even_when_all_rows_deleted(legacy):
    with SQLiteIncidentRepository(legacy, existing=True) as repo:
        repo.delete(1)
        assert repo.migrate_types()
        assert repo.add(entity("MUSI")).id == 3


@pytest.mark.parametrize(
    "other",
    [
        "--generic-description",
        "--generic-description-id",
        "--clear-generic-description",
    ],
)
def test_default_selection_is_exclusive_with_other_description_options(jobs, other):
    _, a, _ = jobs
    before = job_database(a).read_bytes()
    options = [other] if other == "--clear-generic-description" else [other, "text"]
    with pytest.raises(SystemExit) as caught:
        incidents_cli.main(["edit", "1", "--default-description", *options])
    assert caught.value.code == 2 and job_database(a).read_bytes() == before
