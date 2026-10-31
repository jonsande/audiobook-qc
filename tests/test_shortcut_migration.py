"""Migración real del protocolo con escritorio en memoria; nunca GSettings real."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from audiobook_qc import correction_mode, shortcut_migration_cli
from audiobook_qc.integrations.gnome_shortcuts import (
    CUSTOM_SCHEMA,
    GSettingsShortcuts,
    Shortcut,
    ShortcutError,
)
from audiobook_qc.jobs import JobStore
from audiobook_qc.migration_state import MigrationStateFile, durable_text
from audiobook_qc.shortcut_migration import CommandMigration, commands
from audiobook_qc.shortcut_mode import BindingJournal, SavedBinding, ShortcutMode
from audiobook_qc.type_config import load_types, types_data, types_path

PYTHON = "/project/.venv/bin/python"
PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"


class Interrupted(BaseException):
    """Simula muerte del proceso, sin ejecutar handlers de Exception."""


class MemoryBackend:
    def __init__(self, entries, flag):
        self.entries = {e.path: e for e in entries}
        self.flag = flag
        self.writes = []
        self.fail_before = None
        self.interrupt_after = None
        self.before_write = lambda: None

    def paths(self):
        return list(self.entries)

    def read(self, path):
        return self.entries[path]

    def write_command(self, expected, command):
        assert not self.flag[0]
        assert all(not e.binding for e in self.entries.values() if e.owned)
        self.before_write()
        if self.fail_before == len(self.writes):
            raise OSError("set fallido")
        if self.entries[expected.path] != expected:
            raise ShortcutError("Cambio concurrente antes del set")
        self.entries[expected.path] = replace(expected, command=command)
        self.writes.append((expected.path, command))
        if self.interrupt_after == len(self.writes):
            raise Interrupted()

    def write_binding(self, expected, binding):
        assert self.entries[expected.path] == expected
        self.entries[expected.path] = replace(expected, binding=binding)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("DISPLAY", ":synthetic")
    journal = BindingJournal()
    entries = [
        Shortcut(f"{PREFIX}type-{i}/", f"Name {i}", old, "")
        for i, (old, _) in enumerate(commands(PYTHON), 1)
    ]
    foreign = Shortcut(f"{PREFIX}custom0/", "Bob", "gnome-terminal", "<Primary><Alt>t")
    flag = [False]
    backend = MemoryBackend([foreign, *reversed(entries)], flag)
    records = {
        e.path: SavedBinding(e.command, f"F{i}", True) for i, e in enumerate(entries, 1)
    }
    journal.save(records)
    original = journal.path.read_bytes()
    migration = CommandMigration(backend, journal, lambda: flag[0], load_types)
    return SimpleNamespace(
        journal=journal,
        backend=backend,
        flag=flag,
        entries=entries,
        foreign=foreign,
        records=records,
        original=original,
        migration=migration,
    )


def execute(env):
    token = env.migration.plan(PYTHON)["token"]
    return token, env.migration.apply(PYTHON, token)


def assert_original(env):
    assert env.journal.path.read_bytes() == env.original
    assert all(env.backend.read(e.path) == e for e in env.entries)
    assert env.backend.read(env.foreign.path) == env.foreign
    assert not env.flag[0]


def test_seven_commands_free_keys_and_normal_mode_cycle(env):
    token, result = execute(env)
    assert result["phase"] == "complete" and not result["pending"]
    assert len(result["changed"]) == 7
    for i, e in enumerate(env.entries):
        assert env.backend.read(e.path) == replace(e, command=commands(PYTHON)[i][1])
        assert env.journal.load()[e.path] == SavedBinding(
            commands(PYTHON)[i][1], f"F{i + 1}", True
        )
    assert not env.flag[0] and env.backend.read(env.foreign.path) == env.foreign
    controller = ShortcutMode(
        env.backend, env.journal, lambda v: env.flag.__setitem__(0, v)
    )
    controller.on()
    assert env.flag[0] and controller.status(True)[1]
    controller.off()
    assert not env.flag[0] and controller.status(False)[1]
    assert all(not env.backend.read(e.path).binding for e in env.entries)
    assert env.migration.recover(token)["phase"] == "rolled_back"
    assert_original(env)


def test_plan_is_read_only_and_bound_to_full_snapshot(env):
    first = env.migration.plan(PYTHON)
    assert not env.migration.state.path.exists() and not env.backend.writes
    assert_original(env)
    env.backend.entries[env.foreign.path] = replace(env.foreign, name="Changed")
    with pytest.raises(ShortcutError, match="Huella"):
        env.migration.apply(PYTHON, first["token"])
    assert not env.migration.state.path.exists()


def test_type_order_and_formulas_do_not_determine_hotkeys(env):
    catalog = types_data(load_types())
    catalog["types"].reverse()
    for row in catalog["types"]:
        row["default_generic_description"] = "Otra fórmula"
    catalog["types"].insert(
        0,
        dict(id="MUSI", label="Música", enabled=True, default_generic_description=None),
    )
    types_path().write_text(json.dumps(catalog))
    execute(env)
    assert env.journal.load()[env.entries[1].path].binding == "F2"
    assert env.backend.read(env.entries[1].path).command.endswith("--hotkey F2")


@pytest.mark.parametrize(
    "case",
    [
        "active",
        "binding",
        "command",
        "missing",
        "name_after_plan",
        "extra_own",
        "journal_corrupt",
        "journal_missing",
        "journal_extra",
        "journal_binding",
        "journal_command",
        "journal_unsuspended",
        "journal_version",
        "journal_duplicate",
        "catalog_corrupt",
        "catalog_disabled",
        "catalog_unknown",
        "catalog_remapped",
    ],
)
def test_security_rejections_before_first_write(env, case):
    token = env.migration.plan(PYTHON)["token"]
    e = env.entries[0]
    if case == "active":
        env.flag[0] = True
    elif case == "binding":
        env.backend.entries[e.path] = replace(e, binding="F1")
    elif case == "command":
        env.backend.entries[e.path] = replace(e, command=e.command + " --db /other")
    elif case == "missing":
        del env.backend.entries[e.path]
    elif case == "name_after_plan":
        env.backend.entries[e.path] = replace(e, name="External edit")
    elif case == "extra_own":
        env.backend.entries[PREFIX + "extra/"] = replace(e, path=PREFIX + "extra/")
    elif case.startswith("journal_"):
        raw = json.loads(env.original)
        if case == "journal_corrupt":
            env.journal.path.write_text("{")
        elif case == "journal_duplicate":
            env.journal.path.write_text('{"version":1,"version":1,"entries":{}}')
        else:
            if case == "journal_missing":
                del raw["entries"][e.path]
            elif case == "journal_extra":
                raw["entries"][PREFIX + "extra/"] = raw["entries"][e.path]
            elif case == "journal_binding":
                raw["entries"][e.path]["binding"] = "F7"
            elif case == "journal_command":
                raw["entries"][e.path]["command"] += " bad"
            elif case == "journal_unsuspended":
                raw["entries"][e.path]["suspended"] = False
            elif case == "journal_version":
                raw["version"] = 2
            env.journal.path.write_text(json.dumps(raw))
    elif case == "catalog_corrupt":
        types_path().write_text("{")
    else:
        raw = types_data(load_types())
        if case == "catalog_disabled":
            raw["types"][0]["enabled"] = False
        elif case == "catalog_unknown":
            raw["hotkeys"]["F1"] = "MISSING"
        else:
            raw["hotkeys"]["F1"] = "PRON"
        types_path().write_text(json.dumps(raw))
    with pytest.raises((ShortcutError, ValueError)):
        env.migration.apply(PYTHON, token)
    assert not env.backend.writes and not env.migration.state.path.exists()


@pytest.mark.parametrize("stop", range(7))
def test_set_failures_are_diagnosable_and_recoverable(env, stop):
    token = env.migration.plan(PYTHON)["token"]
    env.backend.fail_before = stop
    with pytest.raises(ShortcutError, match="incompleta"):
        env.migration.apply(PYTHON, token)
    state = env.migration.status()
    assert state["pending"] and len(state["changed"]) == stop
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    env.backend.fail_before = None
    env.migration.recover(token)
    assert_original(env)


@pytest.mark.parametrize("stop", range(1, 8))
def test_process_interruption_after_set_before_journal(env, stop):
    token = env.migration.plan(PYTHON)["token"]
    env.backend.interrupt_after = stop
    with pytest.raises(Interrupted):
        env.migration.apply(PYTHON, token)
    # A new coordinator uses only durable intent and observations, not memory.
    fresh = CommandMigration(env.backend, env.journal, lambda: False, load_types)
    assert len(fresh.status()["changed"]) == stop
    env.backend.interrupt_after = None
    fresh.recover(token)
    assert_original(env)


@pytest.mark.parametrize("phase", ["prepared", "commands", "journal", "complete"])
@pytest.mark.parametrize("after_publication", [False, True])
def test_state_persistence_failures(env, monkeypatch, phase, after_publication):
    token = env.migration.plan(PYTHON)["token"]
    original_save = env.migration.state.save

    def fail(data, **kwargs):
        if data["phase"] == phase:
            if after_publication:
                original_save(data, **kwargs)
            raise OSError("fsync/state failure")
        original_save(data, **kwargs)

    monkeypatch.setattr(env.migration.state, "save", fail)
    with pytest.raises((OSError, ShortcutError)):
        env.migration.apply(PYTHON, token)
    monkeypatch.setattr(env.migration.state, "save", original_save)
    if env.migration.state.load() is not None:
        env.migration.recover(token)
    assert_original(env)


@pytest.mark.parametrize("after_publication", [False, True])
def test_interruption_at_journal_publication(env, monkeypatch, after_publication):
    from audiobook_qc import shortcut_migration

    original = shortcut_migration.durable_text
    token = env.migration.plan(PYTHON)["token"]

    def interrupt(path, text):
        if after_publication:
            original(path, text)
        raise Interrupted()

    monkeypatch.setattr(shortcut_migration, "durable_text", interrupt)
    with pytest.raises(Interrupted):
        env.migration.apply(PYTHON, token)
    assert env.migration.state.load()["phase"] == "journal"
    monkeypatch.setattr(shortcut_migration, "durable_text", original)
    env.migration.recover(token)
    assert_original(env)


@pytest.mark.parametrize(
    "change", ["command", "binding", "name", "foreign", "journal", "catalog", "mode"]
)
def test_concurrent_changes_stop_before_further_writes(env, change):
    token = env.migration.plan(PYTHON)["token"]

    def mutate():
        e = env.entries[2]
        if change in ("command", "binding", "name"):
            value = {
                "command": "foreign-app",
                "binding": "F3",
                "name": "Externally changed",
            }[change]
            env.backend.entries[e.path] = replace(e, **{change: value})
        elif change == "foreign":
            env.backend.entries[env.foreign.path] = replace(env.foreign, name="new")
        elif change == "journal":
            env.journal.path.write_text("{}")
        elif change == "catalog":
            types_path().write_text("{")
        else:
            env.flag[0] = True
        env.backend.before_write = lambda: None

    env.backend.before_write = mutate
    with pytest.raises((ShortcutError, ValueError)):
        env.migration.apply(PYTHON, token)
    assert len(env.backend.writes) <= 1
    count = len(env.backend.writes)
    if change != "catalog":
        with pytest.raises((ShortcutError, OSError)):
            env.migration.recover(token)
        assert len(env.backend.writes) == count
    else:
        env.migration.recover(token)  # recovery does not need a live catalog
        assert_original(env)


def test_compare_before_write_rejects_change_of_target(env):
    token = env.migration.plan(PYTHON)["token"]
    e = env.entries[0]
    env.backend.before_write = lambda: env.backend.entries.__setitem__(
        e.path, replace(e, command="other")
    )
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    assert not env.backend.writes and env.backend.read(e.path).command == "other"


@pytest.mark.parametrize("stop", range(7))
def test_recovery_failure_retains_explicit_partial_state(env, stop):
    token, _ = execute(env)
    env.backend.fail_before = len(env.backend.writes) + stop
    with pytest.raises(ShortcutError, match="parcial"):
        env.migration.recover(token)
    assert env.migration.status()["phase"] == "recovering"
    assert env.migration.status()["pending"]
    env.backend.fail_before = None
    env.migration.recover(token)
    assert_original(env)


def test_recovery_preserves_new_external_edit_after_partial_rollback(env):
    token, _ = execute(env)
    env.backend.fail_before = 8  # reverse one entry, then fail
    with pytest.raises(ShortcutError):
        env.migration.recover(token)
    e = env.entries[-1]
    env.backend.entries[e.path] = replace(e, command="external-command")
    count = len(env.backend.writes)
    env.backend.fail_before = None
    with pytest.raises(ShortcutError):
        env.migration.recover(token)
    diagnostic = env.migration.status()
    assert diagnostic["phase"] == "recovering" and not diagnostic["coherent"]
    assert len(env.backend.writes) == count
    assert env.backend.read(e.path).command == "external-command"


def test_completed_and_recovered_intents_cannot_be_reused(env):
    token, _ = execute(env)
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    env.migration.recover(token)
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    with pytest.raises(ShortcutError):
        env.migration.recover(token)


@pytest.mark.parametrize("action", ["on", "off", "status"])
def test_pending_intent_blocks_ordinary_controller_without_changing_journal(
    env, action
):
    token = env.migration.plan(PYTHON)["token"]
    env.backend.fail_before = 2
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    journal_before = env.journal.path.read_bytes()
    controller = ShortcutMode(
        env.backend, env.journal, lambda v: env.flag.__setitem__(0, v)
    )
    with pytest.raises(ShortcutError, match="pendiente"):
        getattr(controller, action)(False) if action == "status" else getattr(
            controller, action
        )()
    assert env.journal.path.read_bytes() == journal_before


def test_existing_desired_protection_is_not_relaxed(env):
    e = env.entries[0]
    with pytest.raises(ShortcutError, match="comando cambiado"):
        ShortcutMode._desired(
            replace(e, command=commands(PYTHON)[0][1]), env.records[e.path]
        )


@pytest.mark.parametrize(
    "content", ["{", "null", '{"version":99}', '{"version":1,"version":1}']
)
def test_corrupt_intent_never_allows_mode_or_recovery(env, content):
    env.migration.state.path.write_text(content)
    with pytest.raises(ShortcutError):
        env.migration.recover("bad")
    with pytest.raises(ShortcutError):
        env.migration.state.ensure_idle()
    assert_original(env)


def test_durable_store_never_overwrites_existing_intent_or_symlink(env, tmp_path):
    target = tmp_path / "target"
    target.write_text("preserve")
    env.migration.state.path.symlink_to(target)
    with pytest.raises(ShortcutError):
        env.migration.plan(PYTHON)
    with pytest.raises(ShortcutError):
        durable_text(env.migration.state.path, "bad")
    assert target.read_text() == "preserve"
    file = tmp_path / "exists"
    file.write_text("preserve")
    with pytest.raises(FileExistsError):
        durable_text(file, "bad", exclusive=True)
    assert file.read_text() == "preserve"


def test_command_adapter_writes_only_command_and_detects_readback(env, monkeypatch):
    backend = GSettingsShortcuts()
    e = env.entries[0]
    calls = []
    current = [e]
    monkeypatch.setattr(backend, "paths", lambda: [e.path])
    monkeypatch.setattr(backend, "read", lambda p: current[0])

    def run(*args):
        calls.append(args)
        current[0] = replace(e, command=commands(PYTHON)[0][1])
        return ""

    monkeypatch.setattr(backend, "_run", run)
    backend.write_command(e, commands(PYTHON)[0][1])
    assert calls == [
        ("set", CUSTOM_SCHEMA + e.path, "command", repr(commands(PYTHON)[0][1]))
    ]
    with pytest.raises(ShortcutError):
        backend.write_command(e, commands(PYTHON)[0][1])
    assert len(calls) == 1


@pytest.fixture
def cli(env, monkeypatch):
    monkeypatch.setattr(
        shortcut_migration_cli, "GSettingsShortcuts", lambda: env.backend
    )
    monkeypatch.setattr(shortcut_migration_cli, "is_active", lambda: env.flag[0])
    return shortcut_migration_cli.main


def test_cli_plan_apply_status_recover_with_explicit_confirmation(cli, env, capsys):
    assert cli(["plan", "--interpreter", PYTHON]) == 0
    plan = json.loads(capsys.readouterr().out)
    with pytest.raises(SystemExit):
        cli(["apply", "--interpreter", PYTHON, "--confirm", plan["token"]])
    assert not env.backend.writes
    assert (
        cli(["apply", "--interpreter", PYTHON, "--confirm", plan["token"], "--execute"])
        == 0
    )
    assert cli(["status"]) == 0
    assert cli(["recover", "--confirm", plan["token"], "--execute"]) == 0
    assert_original(env)


def test_cli_rejects_mismatched_token_and_lock_contention(cli, env):
    with env.journal.lock():
        assert cli(["plan", "--interpreter", PYTHON]) == 1
    with JobStore().lock():
        assert cli(["plan", "--interpreter", PYTHON]) == 1
    assert cli(["apply", "--interpreter", PYTHON, "--confirm", "bad", "--execute"]) == 1
    assert_original(env)


def test_ordinary_cli_pending_check_precedes_sources(env, monkeypatch):
    token = env.migration.plan(PYTHON)["token"]
    env.backend.fail_before = 0
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    monkeypatch.setattr(
        correction_mode, "prepare_job_sources", lambda job: pytest.fail("sources")
    )
    assert correction_mode.main(["on"]) == 1
    assert_original(env)


@pytest.mark.parametrize("fsync_call", [1, 2])
def test_actual_file_or_directory_fsync_failure_before_commands(
    env, monkeypatch, fsync_call
):
    from audiobook_qc import migration_state

    token = env.migration.plan(PYTHON)["token"]
    original = migration_state.os.fsync
    calls = []

    def fail(fd):
        calls.append(fd)
        if len(calls) == fsync_call:
            raise OSError("fsync failed")
        original(fd)

    monkeypatch.setattr(migration_state.os, "fsync", fail)
    with pytest.raises(OSError):
        env.migration.apply(PYTHON, token)
    assert not env.backend.writes
    monkeypatch.setattr(migration_state.os, "fsync", original)
    if env.migration.state.load() is not None:
        env.migration.recover(token)
    assert_original(env)


@pytest.mark.parametrize("stop", [1, 4, 7])
def test_process_interruption_during_recovery_can_resume(env, stop):
    token, _ = execute(env)
    env.backend.interrupt_after = 7 + stop
    with pytest.raises(Interrupted):
        env.migration.recover(token)
    env.backend.interrupt_after = None
    fresh = CommandMigration(env.backend, env.journal, lambda: False, load_types)
    assert fresh.status()["phase"] == "recovering"
    fresh.recover(token)
    assert_original(env)


def test_external_change_of_intent_is_not_overwritten(env):
    token = env.migration.plan(PYTHON)["token"]

    def mutate_record():
        env.migration.state.path.write_text("external record")
        env.backend.before_write = lambda: None

    env.backend.before_write = mutate_record
    with pytest.raises(ShortcutError):
        env.migration.apply(PYTHON, token)
    assert env.migration.state.path.read_text() == "external record"
    assert len(env.backend.writes) == 1


def test_initial_journal_whitespace_is_restored_exactly(env):
    env.journal.path.write_text(
        json.dumps(json.loads(env.original), separators=(",", ":")) + "\n"
    )
    env.original = env.journal.path.read_bytes()
    token, _ = execute(env)
    env.migration.recover(token)
    assert_original(env)


def test_recovery_requires_exact_confirmation_without_writing(env):
    token, _ = execute(env)
    count = len(env.backend.writes)
    with pytest.raises(ShortcutError, match="Huella"):
        env.migration.recover(token + "0")
    assert len(env.backend.writes) == count


def test_adapter_rejects_busy_binding_and_unconfirmed_readback(env, monkeypatch):
    backend = GSettingsShortcuts()
    e = env.entries[0]
    calls = []
    monkeypatch.setattr(backend, "paths", lambda: [e.path])
    monkeypatch.setattr(backend, "read", lambda p: e)
    monkeypatch.setattr(backend, "_run", lambda *a: calls.append(a))
    with pytest.raises(ShortcutError):
        backend.write_command(replace(e, binding="F1"), commands(PYTHON)[0][1])
    assert not calls
    with pytest.raises(ShortcutError, match="confirmar"):
        backend.write_command(e, commands(PYTHON)[0][1])
    assert len(calls) == 1


def test_cli_pending_status_and_recovery_failure_are_errors(cli, env, capsys):
    token = env.migration.plan(PYTHON)["token"]
    env.backend.fail_before = 3
    assert cli(["apply", "--interpreter", PYTHON, "--confirm", token, "--execute"]) == 1
    capsys.readouterr()
    assert cli(["status"]) == 1
    assert json.loads(capsys.readouterr().out)["pending"]
    assert cli(["recover", "--confirm", token, "--execute"]) == 1
    assert env.migration.state.load()["phase"] == "recovering"


def test_intent_is_persisted_before_every_command_write(env):
    def inspect_intent():
        data = MigrationStateFile(env.journal.path).load()
        assert data["phase"] == "commands"
        assert data["attempted"] == list(range(len(env.backend.writes) + 1))
        assert env.journal.path.read_bytes() == env.original

    env.backend.before_write = inspect_intent
    execute(env)


@pytest.mark.parametrize("after_publication", [False, True])
def test_failure_restoring_journal_retains_recoverable_state(
    env, monkeypatch, after_publication
):
    from audiobook_qc import shortcut_migration

    token, _ = execute(env)
    original = shortcut_migration.durable_text

    def fail(path, text):
        if after_publication:
            original(path, text)
        raise OSError("journal restore failure")

    monkeypatch.setattr(shortcut_migration, "durable_text", fail)
    with pytest.raises(ShortcutError, match="parcial"):
        env.migration.recover(token)
    assert env.migration.state.load()["phase"] == "recovering"
    monkeypatch.setattr(shortcut_migration, "durable_text", original)
    env.migration.recover(token)
    assert_original(env)


@pytest.mark.parametrize("after_publication", [False, True])
def test_failure_publishing_rollback_completion_is_diagnosable(
    env, monkeypatch, after_publication
):
    token, _ = execute(env)
    original_save = env.migration.state.save

    def fail(data, **kwargs):
        if data["phase"] == "rolled_back":
            if after_publication:
                original_save(data, **kwargs)
            raise OSError("completion failure")
        original_save(data, **kwargs)

    monkeypatch.setattr(env.migration.state, "save", fail)
    with pytest.raises(ShortcutError, match="parcial"):
        env.migration.recover(token)
    monkeypatch.setattr(env.migration.state, "save", original_save)
    status = env.migration.status()
    if status["pending"]:
        env.migration.recover(token)
    else:
        assert status["phase"] == "rolled_back"
    assert_original(env)
