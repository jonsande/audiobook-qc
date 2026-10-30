"""Trabajos reales en SQLite temporal; nunca se usa GNOME o configuración personal."""

import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

import pytest

from audiobook_qc import capture_save_probe, correction_mode, jobs_cli
from audiobook_qc.capture import CaptureError
from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.jobs import JobError, JobStore, NoActiveJob, job_database
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository


@pytest.fixture
def store(tmp_path):
    store = JobStore()
    store.configure(str(tmp_path / "Correcciones audiolibros á"))
    return store


@pytest.fixture
def job(store):
    job = store.create("El partido")
    store.select(job.id)
    return job


@pytest.fixture
def desktop(monkeypatch, isolated_desktop_sources):
    messages = []
    monkeypatch.setattr(capture_save_probe, "is_active", lambda: True)
    monkeypatch.setattr(capture_save_probe, "active_application", lambda: "okular")
    monkeypatch.setattr(
        capture_save_probe, "notify", lambda *a, **kw: messages.append((a, kw))
    )
    return messages


def captured(code="INTER", text="  parti-\r\nda e\u0301\n"):
    return CapturedIncident(
        code, "á.mp3", "./á.mp3", 19.300243, "file:///á.pdf", 33, text
    )


def run_python(code, *args):
    return subprocess.run(
        [sys.executable, "-c", code, *args], capture_output=True, text=True, check=False
    )


def test_configuration_persists_unicode_paths_and_requires_explicit_setup(tmp_path):
    store = JobStore()
    with pytest.raises(JobError, match="Configura primero"):
        store.configuration()
    assert not store.config.exists()
    root = tmp_path / "raíz con espacios"
    store.configure(str(root))
    assert JobStore().configuration() == dict(version=1, root=str(root), active=None)
    assert root.is_dir()
    result = run_python(
        "from audiobook_qc.jobs import JobStore; import json; "
        "print(json.dumps(JobStore().configuration()))"
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["root"] == str(root)


def test_xdg_default_and_relative_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert JobStore().config == tmp_path / ".config/audiobook-qc/jobs.json"
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert JobStore().config == tmp_path / ".config/audiobook-qc/jobs.json"
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative")
    with pytest.raises(JobError, match="absoluto"):
        JobStore()


def test_create_repeated_titles_unique_ids_and_portable_metadata(store):
    a = store.create("La montaña mágica / parte 1")
    b = store.create(a.name)
    assert a.id != b.id
    assert str(UUID(a.id)) == a.id
    assert a.directory.name == a.id
    assert a.created_at.utcoffset().total_seconds() == 0
    metadata = json.loads((a.directory / "job.json").read_text())
    assert set(metadata) == {"version", "id", "name", "created_at"}
    assert metadata["id"] == a.id
    assert store.get(a.id) == a
    assert set(store.list()) == {a, b}
    assert store.configuration()["active"] is None
    with SQLiteIncidentRepository(job_database(a), existing=True) as repo:
        repo.validate_schema()
        assert repo.list() == []


@pytest.mark.parametrize("name", ["", "  ", "\n\t"])
def test_empty_titles_do_not_create_directories(store, name):
    with pytest.raises(JobError):
        store.create(name)
    assert store.list() == []


@pytest.mark.parametrize("identifier", ["../escape", "", "id", "A" * 36, None, 1])
def test_identifiers_cannot_escape_storage(store, identifier):
    with pytest.raises(JobError):
        store.get(identifier)


def test_selection_persists_across_processes_and_clear_is_explicit(store, job):
    result = run_python(
        "from audiobook_qc.jobs import JobStore; print(JobStore().active().id)"
    )
    assert result.returncode == 0 and result.stdout.strip() == job.id
    result = run_python(
        "from audiobook_qc.jobs import JobStore; JobStore().select(None)"
    )
    assert result.returncode == 0
    with pytest.raises(NoActiveJob):
        store.active()
    store.select(None)
    assert job_database(job).exists()


def test_changing_root_is_explicit_clears_selection_and_does_not_move_data(
    store, job, tmp_path
):
    old_root = store.configuration()["root"]
    store.configure(old_root)
    assert store.active() == job
    other = tmp_path / "nuevo destino"
    store.configure(str(other))
    assert store.list() == []
    with pytest.raises(NoActiveJob):
        store.active()
    assert job_database(job).exists()
    store.configure(old_root)
    assert store.get(job.id) == job
    with pytest.raises(NoActiveJob):
        store.active()


@pytest.mark.parametrize("data", [[], {}, {"version": 2}, {"active": "../bad"}])
def test_corrupt_configuration_not_replaced_silently(store, data, tmp_path):
    original = json.dumps(data)
    store.config.write_text(original)
    with pytest.raises(JobError):
        store.configure(str(tmp_path / "new"))
    assert store.config.read_text() == original


@pytest.mark.parametrize(
    "damage",
    ["missing", "empty", "version", "columns", "invalid", "symlink", "directory"],
)
def test_invalid_databases_rejected_before_capture_without_initialization(
    store, job, desktop, monkeypatch, damage
):
    if damage == "missing":
        job_database(job).unlink()
    elif damage == "empty":
        job_database(job).write_bytes(b"")
    elif damage == "invalid":
        job_database(job).write_bytes(b"no es sqlite")
    elif damage == "symlink":
        alternate = job.directory / "other.sqlite3"
        job_database(job).rename(alternate)
        job_database(job).symlink_to(alternate)
    elif damage == "directory":
        job_database(job).unlink()
        job_database(job).mkdir()
    else:
        with sqlite3.connect(job_database(job)) as conn:
            if damage == "version":
                conn.execute("PRAGMA user_version=3")
            else:
                conn.execute("DROP TABLE incidents")
    before = job_database(job).read_bytes() if job_database(job).is_file() else None
    monkeypatch.setattr(
        capture_save_probe, "capture_incident", lambda *a, **kw: pytest.fail("captura")
    )
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert desktop[0][0][0] == "Trabajo inválido o inaccesible"
    assert (
        not job_database(job)
        .with_name(job_database(job).name + ".capture.lock")
        .exists()
    )
    if damage == "missing":
        assert not job_database(job).exists()
    elif before is not None:
        assert job_database(job).read_bytes() == before


def test_missing_selection_and_metadata_never_capture(store, job, desktop, monkeypatch):
    monkeypatch.setattr(
        capture_save_probe, "capture_incident", lambda *a, **kw: pytest.fail("captura")
    )
    store.select(None)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert desktop[-1][0][0] == "Sin trabajo activo"
    store.select(job.id)
    (job.directory / "job.json").unlink()
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert desktop[-1][0][0] == "Trabajo inválido o inaccesible"
    with SQLiteIncidentRepository(job_database(job)) as repo:
        assert repo.list() == []


def test_inaccessible_database_is_job_error(store, job, desktop, monkeypatch):
    original = sqlite3.connect

    def denied(*a, **kw):
        raise sqlite3.OperationalError("permiso denegado")

    monkeypatch.setattr(sqlite3, "connect", denied)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert "permiso denegado" in desktop[-1][0][1]
    monkeypatch.setattr(sqlite3, "connect", original)
    assert store.active() == job


def test_two_jobs_desktop_capture_isolation_and_exact_data(
    store, job, desktop, monkeypatch, capsys
):
    b = store.create("La montaña mágica")
    for target, code in [(job, "TEXT"), (b, "INTER"), (job, "OTRO")]:
        store.select(target.id)
        from audiobook_qc.integrations.mpv import MpvState
        from audiobook_qc.integrations.okular import OkularState
        from audiobook_qc.integrations.selection import Selection

        expected = captured(code)
        monkeypatch.setattr(
            capture_save_probe.selection,
            "read_selection",
            lambda name: Selection(name, expected.selected_text),
        )
        monkeypatch.setattr(
            capture_save_probe.okular,
            "read_state",
            lambda service: OkularState(
                "org.kde.okular-test", expected.document, None, expected.page
            ),
        )
        monkeypatch.setattr(
            capture_save_probe.mpv,
            "read_state",
            lambda socket: MpvState(
                expected.audio_filename,
                expected.audio_path,
                expected.audio_position_seconds,
                None,
                True,
            ),
        )
        assert capture_save_probe.main(["--desktop", code]) == 0
        entity = json.loads(capsys.readouterr().out)
        assert target.name in desktop[-1][0][1]
        assert f"#{entity['id']}" in desktop[-1][0][1]
    for target, codes in [(job, ["TEXT", "OTRO"]), (b, ["INTER"])]:
        with SQLiteIncidentRepository(job_database(target), existing=True) as repo:
            saved = repo.list()
        assert [i.incident_type for i in saved] == codes
        for incident in saved:
            expected = captured(incident.incident_type)
            assert {k: getattr(incident, k) for k in asdict(expected)} == asdict(
                expected
            )
            assert (
                incident.audio_position_seconds.hex()
                == expected.audio_position_seconds.hex()
            )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "audiobook_qc.incident_probe",
                "--db",
                str(job_database(target)),
                "get",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["incident_type"] == codes[0]


def test_old_shortcut_cannot_write_to_different_database(
    store, job, desktop, monkeypatch
):
    other = store.create("Otro")
    monkeypatch.setattr(
        capture_save_probe, "capture_incident", lambda *a, **kw: pytest.fail("captura")
    )
    assert (
        capture_save_probe.main(["--desktop", "--db", str(job_database(other)), "TEXT"])
        == 1
    )
    assert "retira --db" in desktop[-1][0][1]
    for target in [job, other]:
        with SQLiteIncidentRepository(job_database(target)) as repo:
            assert repo.list() == []


def test_capture_and_selection_exclude_each_other_across_processes(store, job):
    other = store.create("Otro")
    with store.destination() as (target, _):
        assert target == job
        for statement in [
            f"JobStore().select('{other.id}')",
            "JobStore().select(None)",
            "JobStore().active()",
            f"JobStore().configure({str(other.directory)!r})",
        ]:
            result = run_python(
                "from audiobook_qc.jobs import JobStore; "
                "from audiobook_qc.integrations.activation import ActivationBusy\n"
                "try:\n    "
                + statement
                + "\nexcept ActivationBusy:\n    raise SystemExit(7)"
            )
            assert result.returncode == 7, result.stderr
    assert store.active() == job
    store.select(other.id)
    assert store.active() == other


def test_switch_and_overlapping_capture_rejected_during_use_case(
    store, job, desktop, monkeypatch
):
    other = store.create("Otro")

    def capture(code, **kw):
        with pytest.raises(ActivationBusy):
            JobStore().select(other.id)
        assert capture_save_probe.main(["--desktop", "PRON"]) == 1
        return captured(code)

    monkeypatch.setattr(capture_save_probe, "capture_incident", capture)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 0
    assert desktop[0][0][0] == "Activación omitida"
    with SQLiteIncidentRepository(job_database(job)) as repo:
        assert len(repo.list()) == 1
    with SQLiteIncidentRepository(job_database(other)) as repo:
        assert repo.list() == []
    store.select(other.id)


def test_failed_capture_releases_selection_lock(store, job, desktop, monkeypatch):
    def fail(*a, **kw):
        raise CaptureError("sin PRIMARY")

    monkeypatch.setattr(capture_save_probe, "capture_incident", fail)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    store.select(None)
    assert "Error de captura" in desktop[0][0][1]


def test_cli_commands_and_exit_codes(tmp_path, capsys):
    assert jobs_cli.main(["config"]) == 1
    assert jobs_cli.main(["configure", str(tmp_path / "trabajos")]) == 0
    assert jobs_cli.main(["create", "Título idéntico"]) == 0
    job = JobStore().list()[0]
    assert jobs_cli.main(["list"]) == 0
    assert jobs_cli.main(["get", job.id]) == 0
    assert jobs_cli.main(["select", job.id]) == 0
    assert jobs_cli.main(["active"]) == 0
    assert job.name in capsys.readouterr().out
    assert jobs_cli.main(["clear"]) == 0
    assert jobs_cli.main(["active"]) == 1
    assert "No hay trabajo activo" in capsys.readouterr().err


def test_mode_on_requires_valid_job_before_touching_gnome(
    store, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("DISPLAY", ":0")

    class Controller:
        def on(self):
            pytest.fail("No debe cambiar GNOME ni indicador")

    monkeypatch.setattr(
        correction_mode, "make_controller", lambda journal: Controller()
    )
    assert correction_mode.main(["on"]) == 1
    assert "No hay trabajo activo" in capsys.readouterr().err
    job = store.create("Libro")
    store.select(job.id)
    job_database(job).unlink()
    assert correction_mode.main(["on"]) == 1
    assert "Trabajo inválido" in capsys.readouterr().err
    assert not correction_mode.is_active()


def test_mode_on_holds_destination_until_activation(
    store, job, monkeypatch, tmp_path, isolated_desktop_sources
):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(correction_mode, "is_active", lambda: True)

    class Controller:
        def on(self):
            with pytest.raises(ActivationBusy):
                store.select(None)

        def status(self, active):
            return "activo", True

    monkeypatch.setattr(
        correction_mode, "make_controller", lambda journal: Controller()
    )
    assert correction_mode.main(["on"]) == 0
    assert store.active() == job


def test_unavailable_root_never_recreated_by_capture(store, job, desktop):
    root = job.directory.parent
    moved = root.with_name("apartado")
    root.rename(moved)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert not root.exists()


def test_configuration_write_failure_preserves_previous_selection(
    store, job, monkeypatch
):
    def denied(*a, **kw):
        raise PermissionError("sin permiso")

    before = store.config.read_bytes()
    monkeypatch.setattr(Path, "replace", denied)
    with pytest.raises(PermissionError):
        store.select(None)
    assert store.config.read_bytes() == before
    assert store.active() == job


@pytest.mark.parametrize(
    "change",
    [
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"version": 2},
        {"name": " "},
        {"created_at": "2026-10-29"},
        {"created_at": []},
    ],
)
def test_invalid_metadata_rejected_by_get_list_and_capture(store, job, desktop, change):
    path = job.directory / "job.json"
    data = json.loads(path.read_text())
    data.update(change)
    path.write_text(json.dumps(data))
    with pytest.raises(JobError):
        store.get(job.id)
    with pytest.raises(JobError):
        store.list()
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1


def test_uuid_collision_never_overwrites_existing_job(store, job, monkeypatch):
    from audiobook_qc import jobs

    before = job_database(job).read_bytes()
    monkeypatch.setattr(jobs, "uuid4", lambda: UUID(job.id))
    with pytest.raises(FileExistsError):
        store.create("Título distinto")
    assert store.get(job.id) == job
    assert job_database(job).read_bytes() == before


def test_config_lock_failure_reported_as_job_error(store, job, desktop, monkeypatch):
    def denied(*a, **kw):
        raise PermissionError("configuración inaccesible")

    monkeypatch.setattr(Path, "mkdir", denied)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert desktop[-1][0][0] == "Trabajo inválido o inaccesible"


def test_select_invalid_job_preserves_previous_destination(store, job):
    other = store.create("Otro")
    job_database(other).unlink()
    with pytest.raises(JobError):
        store.select(other.id)
    assert store.active() == job
    assert not job_database(other).exists()


def test_mode_on_and_capture_reject_simultaneous_selection_change(
    store, job, desktop, monkeypatch, tmp_path
):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    # make_controller solo construye el adaptador, no debe llamar GSettings.
    class Controller:
        def on(self):
            pytest.fail("No debe activar durante el cambio de trabajo")

    monkeypatch.setattr(
        correction_mode, "make_controller", lambda journal: Controller()
    )
    with store.lock():
        assert correction_mode.main(["on"]) == 1
        assert capture_save_probe.main(["--desktop", "INTER"]) == 1


@pytest.mark.parametrize("target", ["database", "directory"])
def test_readonly_destination_rejected_before_reading_sources(
    store, job, desktop, monkeypatch, target
):
    from audiobook_qc import jobs

    blocked = job_database(job) if target == "database" else job.directory
    real_access = jobs.os.access
    monkeypatch.setattr(
        jobs.os,
        "access",
        lambda path, mode: False if path == blocked else real_access(path, mode),
    )
    monkeypatch.setattr(
        capture_save_probe, "capture_incident", lambda *a, **kw: pytest.fail("captura")
    )
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert "lectura/escritura" in desktop[-1][0][1]
    assert desktop[-1][0][0] == "Trabajo inválido o inaccesible"
