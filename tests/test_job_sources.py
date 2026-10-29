"""Asociaciones explícitas sin aplicaciones reales ni configuración del usuario."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiobook_qc import capture_save_probe, correction_mode, job_sources, jobs_cli
from audiobook_qc.integrations import job_mpv
from audiobook_qc.integrations.document_binding import resolve_document
from audiobook_qc.integrations.mpv import MpvError, MpvState
from audiobook_qc.integrations.okular import OkularError
from audiobook_qc.integrations.selection import Selection
from audiobook_qc.job_sources import (
    SourceError,
    SourcesConfig,
    launch_mpv,
    launch_okular,
    load_sources,
    save_sources,
    set_document,
)
from audiobook_qc.jobs import JobStore, job_database
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository

INTERFACE_XML = """<node><interface name="org.kde.okular">
<method name="currentDocument"><arg direction="out" type="s"/></method>
<method name="currentPage"><arg direction="out" type="u"/></method>
</interface></node>"""


class FakeBus:
    def __init__(self, views, names=None):
        self.views = views
        self.names = names or {
            f"org.kde.okular-{index}": owner
            for index, owner in enumerate(views, start=1)
        }
        self.calls = []

    def list_services(self):
        return list(self.names)

    def call(self, service, path, interface, method, signature, *arguments):
        self.calls.append((service, path, method, arguments))
        if method == "GetNameOwner":
            return self.names[arguments[1]]
        if service not in self.views:
            raise OkularError("La conexión desapareció")
        if method == "Introspect":
            if path == "/":
                return (
                    "<node>"
                    + "".join(
                        f'<node name="{part[1:]}"/>' for part in self.views[service]
                    )
                    + "</node>"
                )
            return INTERFACE_XML
        document, page = self.views[service][path]
        if method == "currentDocument":
            return document
        if method == "currentPage":
            return page
        pytest.fail(f"Consulta inesperada: {method}")


@pytest.fixture
def runtime(monkeypatch):
    # El límite de sockaddr_un no admite los nombres largos de tmp_path.
    with tempfile.TemporaryDirectory(prefix="aqc-") as directory:
        monkeypatch.setenv("XDG_RUNTIME_DIR", directory)
        yield Path(directory)


@pytest.fixture
def setup(tmp_path, monkeypatch, runtime):
    store = JobStore()
    store.configure(str(tmp_path / "Correcciones"))
    a, b = store.create("Audiolibro A"), store.create("Audiolibro B")
    configs = {}
    for job in [a, b]:
        pdf = tmp_path / (job.name + ".pdf")
        pdf.write_text("PDF de prueba")
        files = tuple(tmp_path / f"{job.name}-{i}.mp3" for i in range(2))
        for file in files:
            file.write_bytes(b"audio simulado")
        config = SourcesConfig(pdf, files)
        configs[job.id] = config
        save_sources(job, config)
    # Dos vistas dentro del mismo proceso: no basta escoger el servicio.
    bus = FakeBus(
        {
            ":1.10": {
                "/okular": (str(configs[a.id].document), 11),
                "/okular2": (str(configs[b.id].document), 22),
            }
        }
    )
    monkeypatch.setattr(
        job_sources,
        "resolve_document",
        lambda document, **kw: resolve_document(document, bus=bus),
    )
    states = {
        str(job_mpv.socket_path(job.id)): MpvState(
            configs[job.id].audio_files[0].name,
            str(configs[job.id].audio_files[0]),
            19.300243,
            100,
            True,
        )
        for job in [a, b]
    }
    calls = []

    def read(path):
        calls.append(path)
        if path not in states:
            raise MpvError("Socket del trabajo ausente o conexión rechazada")
        return states[path]

    monkeypatch.setattr(job_mpv, "read_state", read)
    monkeypatch.setattr(capture_save_probe, "is_active", lambda: True)
    monkeypatch.setattr(capture_save_probe, "active_application", lambda: "okular")
    monkeypatch.setattr(
        capture_save_probe.selection,
        "read_selection",
        lambda name: Selection(name, "  Frase parti-\r\nda e\u0301\n"),
    )
    messages = []
    monkeypatch.setattr(
        capture_save_probe, "notify", lambda *a, **kw: messages.append(a)
    )
    return SimpleNamespace(
        store=store,
        a=a,
        b=b,
        configs=configs,
        bus=bus,
        states=states,
        calls=calls,
        messages=messages,
    )


def incidents(job):
    with SQLiteIncidentRepository(job_database(job), existing=True) as repository:
        return repository.list()


def test_a_b_a_sources_and_databases_are_isolated_and_other_mpv_is_ignored(setup):
    env = setup
    sa, sb = map(lambda job: str(job_mpv.socket_path(job.id)), [env.a, env.b])
    assert sa != sb
    env.states["/some/foreign/mpv.sock"] = MpvState(
        "ajeno.mp3", "/ajeno", 999, 1000, False
    )
    for job, expected_socket in [(env.a, sa), (env.b, sb), (env.a, sa)]:
        env.calls.clear()
        env.bus.calls.clear()
        env.store.select(job.id)
        assert capture_save_probe.main(["--desktop", "INTER"]) == 0
        assert set(env.calls) == {expected_socket}
        page_calls = [
            (s, p) for s, p, method, args in env.bus.calls if method == "currentPage"
        ]
        expected_view = "/okular" if job == env.a else "/okular2"
        assert set(page_calls) == {(":1.10", expected_view)}
    assert len(incidents(env.a)) == 2
    assert len(incidents(env.b)) == 1
    for job, page in [(env.a, 11), (env.b, 22)]:
        for incident in incidents(job):
            assert incident.document == str(env.configs[job.id].document)
            assert incident.page == page
            assert incident.audio_path == str(env.configs[job.id].audio_files[0])
            assert incident.audio_position_seconds.hex() == (19.300243).hex()
            assert incident.selected_text == "  Frase parti-\r\nda e\u0301\n"
    assert "Audiolibro A" in env.messages[-1][1]


def test_successive_chapters_in_one_mpv_preserve_each_filename_and_position(setup):
    env = setup
    env.store.select(env.a.id)
    path = str(job_mpv.socket_path(env.a.id))
    for index, position in enumerate([19.300243, 1104.5171234567]):
        file = env.configs[env.a.id].audio_files[index]
        env.states[path] = MpvState(file.name, str(file), position, 2000, True)
        assert capture_save_probe.main(["--desktop", "TEXT"]) == 0
    for incident, file, position in zip(
        incidents(env.a),
        env.configs[env.a.id].audio_files,
        [19.300243, 1104.5171234567],
    ):
        assert incident.audio_filename == file.name
        assert incident.audio_path == str(file)
        assert incident.audio_position_seconds.hex() == position.hex()


def test_missing_job_socket_never_falls_back_to_another_instance(setup):
    env = setup
    env.store.select(env.a.id)
    del env.states[str(job_mpv.socket_path(env.a.id))]
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert set(env.calls) == {str(job_mpv.socket_path(env.a.id))}
    assert incidents(env.a) == incidents(env.b) == []
    assert "Socket del trabajo ausente" in env.messages[-1][1]


@pytest.mark.parametrize("path", ["/ajeno.mp3", "relativo.mp3", None])
def test_undeclared_or_ambiguous_audio_path_rejected(setup, path):
    env = setup
    env.store.select(env.a.id)
    env.states[str(job_mpv.socket_path(env.a.id))] = MpvState(
        "otro", path, 12, 100, True
    )
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert incidents(env.a) == []
    assert "capítulos asociados" in env.messages[-1][1]


def test_missing_sources_reject_without_reading_primary(setup, monkeypatch):
    env = setup
    (env.a.directory / "sources.json").unlink()
    env.store.select(env.a.id)
    monkeypatch.setattr(
        capture_save_probe.selection,
        "read_selection",
        lambda *a: pytest.fail("PRIMARY"),
    )
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert "Fuentes sin asociar" in env.messages[-1][1]
    assert incidents(env.a) == []


def test_duplicate_pdf_in_two_views_rejects_instead_of_choosing_focus(setup):
    env = setup
    env.store.select(env.a.id)
    env.bus.views[":1.10"]["/okular3"] = (str(env.configs[env.a.id].document), 99)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert "varias vistas" in env.messages[-1][1]
    assert incidents(env.a) == []
    assert env.calls == []


def test_other_pdf_is_not_used_when_associated_pdf_is_closed(setup):
    env = setup
    env.store.select(env.a.id)
    del env.bus.views[":1.10"]["/okular"]
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert incidents(env.a) == []
    assert "documento asociado" in env.messages[-1][1]


def test_reopening_okular_rediscovers_new_owner_and_object_without_rebinding(setup):
    env = setup
    env.store.select(env.a.id)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 0
    document = str(env.configs[env.a.id].document)
    env.bus.names = {"org.kde.okular-200": ":1.99"}
    env.bus.views = {":1.99": {"/okular8": (document, 54)}}
    assert capture_save_probe.main(["--desktop", "INTER"]) == 0
    assert [i.page for i in incidents(env.a)] == [11, 54]
    assert load_sources(env.a).document == Path(document)


@pytest.mark.parametrize("damage", ["document", "page", "owner", "duplicate"])
def test_change_after_resolution_rejected_before_sqlite_add(setup, monkeypatch, damage):
    env = setup
    env.store.select(env.a.id)
    original = capture_save_probe.capture_incident

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        if damage == "owner":
            env.bus.views.clear()
        elif damage == "duplicate":
            env.bus.views[":1.10"]["/okular3"] = (result.document, 11)
        else:
            env.bus.views[":1.10"]["/okular"] = (
                str(env.configs[env.b.id].document)
                if damage == "document"
                else result.document,
                55 if damage == "page" else 11,
            )
        return result

    monkeypatch.setattr(capture_save_probe, "capture_incident", capture)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert incidents(env.a) == incidents(env.b) == []
    assert all(summary != "Incidencia guardada" for summary, body in env.messages)


@pytest.mark.parametrize(
    "options",
    [
        ["--mpv-socket", "/tmp/old/mpv.sock"],
        ["--okular-service", "org.kde.okular-123"],
    ],
)
def test_desktop_rejects_stale_source_overrides_with_migration_message(setup, options):
    setup.store.select(setup.a.id)
    assert capture_save_probe.main(["--desktop", "INTER", *options]) == 1
    assert "Retira --mpv-socket y --okular-service" in setup.messages[-1][1]
    assert setup.calls == []
    assert incidents(setup.a) == []


def test_mode_on_rejects_unavailable_sources_before_changing_gnome(
    setup, monkeypatch, tmp_path
):
    setup.store.select(setup.a.id)
    setup.states.clear()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(
        correction_mode,
        "make_controller",
        lambda journal: SimpleNamespace(
            on=lambda: pytest.fail("GNOME no debe cambiar")
        ),
    )
    assert correction_mode.main(["on"]) == 1


def test_sources_persist_and_socket_reconstructed_in_new_process(setup):
    job = setup.a
    result = subprocess.run(
        [sys.executable, "-m", "audiobook_qc.jobs_cli", "sources", job.id],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["document"] == str(setup.configs[job.id].document)
    assert data["audio_files"] == [str(p) for p in setup.configs[job.id].audio_files]
    assert data["mpv_socket"] == str(job_mpv.socket_path(job.id))
    assert "socket" not in json.loads((job.directory / "sources.json").read_text())


def test_cli_sets_and_queries_pdf_without_modifying_job_identity(
    setup, tmp_path, capsys
):
    pdf = tmp_path / "Nueva versión ñ.pdf"
    pdf.write_text("PDF")
    before = (setup.a.directory / "job.json").read_bytes()
    assert jobs_cli.main(["set-pdf", setup.a.id, str(pdf)]) == 0
    assert jobs_cli.main(["sources", setup.a.id]) == 0
    assert load_sources(setup.a).document == pdf
    assert (setup.a.directory / "job.json").read_bytes() == before
    assert str(pdf) in capsys.readouterr().out


@pytest.mark.parametrize(
    "data",
    [
        [],
        {},
        {"version": 2},
        {"version": 1, "document": "relative.pdf", "audio_files": []},
        {"version": 1, "document": None, "audio_files": [False]},
    ],
)
def test_corrupt_sources_never_replaced_silently(setup, data, tmp_path):
    path = setup.a.directory / "sources.json"
    path.write_text(json.dumps(data))
    original = path.read_bytes()
    with pytest.raises(SourceError):
        set_document(setup.a, str(setup.configs[setup.a.id].document))
    assert path.read_bytes() == original


def test_mpv_launch_persists_chapters_and_reuses_them_days_later(setup, monkeypatch):
    env = setup
    calls = []

    def launch(job_id, paths, log):
        calls.append((job_id, paths, log))
        return dict(status="started", socket=str(job_mpv.socket_path(job_id)))

    monkeypatch.setattr(job_mpv, "launch", launch)
    paths = [str(p) for p in env.configs[env.a.id].audio_files]
    assert jobs_cli.main(["launch-mpv", env.a.id, *paths]) == 0
    assert jobs_cli.main(["launch-mpv", env.a.id]) == 0
    assert calls[0] == calls[1]
    assert calls[0][0] == env.a.id
    assert calls[0][1] == env.configs[env.a.id].audio_files


def test_changing_running_playlist_requires_explicit_close(setup, monkeypatch):
    env = setup
    monkeypatch.setattr(job_mpv, "launch", lambda *a: {"status": "running"})
    before = load_sources(env.a)
    with pytest.raises(SourceError, match="ciérralo"):
        launch_mpv(env.a, [str(env.configs[env.b.id].audio_files[0])])
    assert load_sources(env.a) == before


def test_launch_okular_reuses_unique_view_and_reopens_missing_document(
    setup, monkeypatch
):
    assert launch_okular(setup.a)["status"] == "running"
    setup.bus.views.clear()
    setup.bus.names.clear()
    commands = []

    def popen(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(job_sources.subprocess, "Popen", popen)
    assert jobs_cli.main(["launch-okular", setup.a.id]) == 0
    assert commands[0][0] == ["okular", "--", str(setup.configs[setup.a.id].document)]
    assert "shell" not in commands[0][1]


def test_launch_okular_refuses_ambiguity_instead_of_opening_more_views(
    setup, monkeypatch
):
    setup.bus.views[":1.10"]["/okular3"] = (str(setup.configs[setup.a.id].document), 9)
    monkeypatch.setattr(
        job_sources.subprocess, "Popen", lambda *a, **kw: pytest.fail("no abrir")
    )
    with pytest.raises(SourceError, match="varias vistas"):
        launch_okular(setup.a)


def test_okular_aliases_with_same_unique_owner_are_not_duplicate_views(setup):
    setup.bus.names["org.kde.okular-999"] = ":1.10"
    view = resolve_document(setup.configs[setup.a.id].document, bus=setup.bus)
    assert view.object_path == "/okular"


def test_unknown_okular_root_or_broken_interface_fails_closed(setup, monkeypatch):
    original = setup.bus.call

    def call(service, path, interface, method, signature, *args):
        if path == "/" and method == "Introspect":
            return '<node><node name="unknown"/></node>'
        return original(service, path, interface, method, signature, *args)

    monkeypatch.setattr(setup.bus, "call", call)
    with pytest.raises(OkularError, match="enumerar"):
        resolve_document(setup.configs[setup.a.id].document, bus=setup.bus)


def test_bound_view_rejects_document_change_between_page_reads(setup, monkeypatch):
    view = resolve_document(setup.configs[setup.a.id].document, bus=setup.bus)
    original = setup.bus.call

    def call(service, path, interface, method, signature, *args):
        result = original(service, path, interface, method, signature, *args)
        if method == "currentPage":
            setup.bus.views[service][path] = (
                str(setup.configs[setup.b.id].document),
                22,
            )
        return result

    monkeypatch.setattr(setup.bus, "call", call)
    with pytest.raises(OkularError, match="cambió"):
        view.read_state()


def test_source_configuration_can_be_queried_without_runtime(setup, monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR")
    data = job_sources.sources_data(setup.a)
    assert data["mpv_socket"] is None
    assert data["document"] == str(setup.configs[setup.a.id].document)
    with pytest.raises(SourceError, match="XDG_RUNTIME_DIR"):
        job_sources.prepare_job_sources(setup.a)


def test_missing_pdf_path_rejected_before_launch_or_capture(setup):
    setup.store.select(setup.a.id)
    setup.configs[setup.a.id].document.unlink()
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert incidents(setup.a) == []
    with pytest.raises(SourceError, match="inaccesible"):
        launch_okular(setup.a)


def test_unique_document_url_matches_configured_absolute_path(setup):
    setup.bus.views[":1.10"]["/okular"] = (
        setup.configs[setup.a.id].document.as_uri(),
        44,
    )
    setup.store.select(setup.a.id)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 0
    assert incidents(setup.a)[0].page == 44
    assert incidents(setup.a)[0].document.startswith("file:")


def test_uninspectable_unrelated_service_is_not_silently_ignored(setup, monkeypatch):
    setup.bus.names["org.kde.okular-999"] = ":1.999"
    setup.store.select(setup.a.id)
    assert capture_save_probe.main(["--desktop", "INTER"]) == 1
    assert incidents(setup.a) == []
    assert "desapareció" in setup.messages[-1][1]


def test_valid_sources_are_checked_under_same_lock_as_mode_activation(
    setup, monkeypatch, tmp_path
):
    from audiobook_qc.integrations.activation import ActivationBusy

    setup.store.select(setup.a.id)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(correction_mode, "is_active", lambda: True)
    calls = []

    def activate():
        with pytest.raises(ActivationBusy):
            setup.store.select(setup.b.id)
        calls.append("on")

    monkeypatch.setattr(
        correction_mode,
        "make_controller",
        lambda journal: SimpleNamespace(
            on=activate, status=lambda active: ("activo", True)
        ),
    )
    assert correction_mode.main(["on"]) == 0
    assert calls == ["on"]
    assert set(setup.calls) == {str(job_mpv.socket_path(setup.a.id))}
