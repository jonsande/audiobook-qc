"""GSettings sustituido: nunca se toca el escritorio real desde los tests."""

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from audiobook_qc import correction_mode
from audiobook_qc.integrations.gnome_shortcuts import (
    GSettingsShortcuts,
    Shortcut,
    ShortcutError,
)
from audiobook_qc.shortcut_mode import BindingJournal, SavedBinding, ShortcutMode

PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"


def shortcut(index: int, binding: str, *, own: bool = True) -> Shortcut:
    command = (
        "/project/.venv/bin/python -m audiobook_qc.capture_save_probe "
        "--desktop --db /data/qc.db TEXT"
        if own
        else "gnome-terminal"
    )
    return Shortcut(f"{PREFIX}custom{index}/", "Nombre editable", command, binding)


class MemoryBindings:
    def __init__(self, entries: list[Shortcut]):
        self.entries = {entry.path: entry for entry in entries}
        self.writes = []
        self.failures: set[str] = set()
        self.read_failures: set[str] = set()
        self.fail_after_write = False

    def paths(self):
        return list(self.entries)

    def read(self, path):
        if path in self.read_failures:
            raise ShortcutError("fallo de lectura")
        return self.entries[path]

    def write_binding(self, expected, binding):
        assert expected.owned
        assert self.entries[expected.path] == expected
        if expected.path in self.failures:
            self.failures.remove(expected.path)
            if self.fail_after_write:
                self.entries[expected.path] = replace(expected, binding=binding)
            raise ShortcutError("fallo de escritura")
        self.writes.append((expected.path, binding))
        self.entries[expected.path] = replace(expected, binding=binding)


@pytest.fixture
def setup(tmp_path: Path):
    entries = [
        shortcut(12, "F1"),
        shortcut(40, "<Shift>F6"),
        shortcut(2, "<Ctrl><Alt>t", own=False),
    ]
    backend = MemoryBindings(entries)
    journal = BindingJournal(tmp_path / "state.json")
    flags = []

    def set_flag(value):
        if value:
            assert backend.entries[entries[0].path].binding
        flags.append(value)

    controller = ShortcutMode(backend, journal, set_flag)
    return controller, backend, journal, flags, entries


def test_off_preserves_custom_bindings_commands_names_registry_and_foreign_entries(
    setup,
):
    controller, backend, journal, flags, entries = setup
    controller.off()
    assert flags == [False]
    assert list(backend.entries) == [entry.path for entry in entries]
    assert backend.entries[entries[2].path] == entries[2]
    for entry in entries[:2]:
        assert backend.entries[entry.path] == replace(entry, binding="")
        assert journal.load()[entry.path] == SavedBinding(
            entry.command, entry.binding, True
        )


def test_on_restores_custom_bindings_only_then_activates_mode(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    controller.on()
    assert list(backend.entries.values()) == entries
    assert flags == [False, False, True]
    assert controller.status(True)[1]
    assert not any(record.suspended for record in journal.load().values())


def test_repeated_on_off_is_idempotent(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    saved = journal.load()
    controller.off()
    assert journal.load() == saved
    controller.on()
    writes = list(backend.writes)
    controller.on()
    assert backend.writes == writes
    assert list(backend.entries.values()) == entries


def test_restart_recovers_after_runtime_disappears(setup):
    controller, backend, journal, flags, entries = setup
    controller.on()
    restarted = ShortcutMode(backend, BindingJournal(journal.path), flags.append)
    assert not restarted.status(False)[1]
    restarted.off()
    assert restarted.status(False)[1]
    restarted.on()
    assert list(backend.entries.values()) == entries


@pytest.mark.parametrize("after_write", [False, True])
def test_partial_on_failure_rolls_back_and_never_sets_active(setup, after_write):
    controller, backend, journal, flags, entries = setup
    controller.off()
    backend.failures.add(entries[1].path)
    backend.fail_after_write = after_write
    with pytest.raises(ShortcutError):
        controller.on()
    assert True not in flags
    assert all(not backend.entries[entry.path].binding for entry in entries[:2])
    controller.on()
    assert list(backend.entries.values()) == entries


def test_partial_off_failure_continues_other_keys_and_can_be_retried(setup):
    controller, backend, journal, flags, entries = setup
    backend.failures.add(entries[0].path)
    with pytest.raises(ShortcutError, match="liberación con incidencias"):
        controller.off()
    assert flags == [False]
    assert backend.entries[entries[0].path].binding == "F1"
    assert backend.entries[entries[1].path].binding == ""
    assert not controller.status(False)[1]
    controller.off()
    assert controller.status(False)[1]
    controller.on()
    assert list(backend.entries.values()) == entries


def test_manual_binding_edit_while_disabled_takes_priority(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    backend.entries[entries[0].path] = replace(entries[0], binding="<Shift>F1")
    controller.on()
    assert backend.entries[entries[0].path].binding == "<Shift>F1"
    controller.off()
    controller.on()
    assert backend.entries[entries[0].path].binding == "<Shift>F1"


def test_manual_disable_while_enabled_is_not_undone(setup):
    controller, backend, journal, flags, entries = setup
    controller.on()
    backend.entries[entries[1].path] = replace(entries[1], binding="")
    controller.off()
    controller.on()
    assert backend.entries[entries[1].path].binding == ""
    assert controller.status(True)[1]


def test_removed_or_repurposed_entry_is_never_recreated_or_written(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    del backend.entries[entries[1].path]
    repurposed = replace(entries[0], command="firefox", binding="<Ctrl>j")
    backend.entries[entries[0].path] = repurposed
    backend.writes.clear()
    with pytest.raises(ShortcutError, match="No hay combinaciones"):
        controller.on()
    assert backend.entries[entries[0].path] == repurposed
    assert backend.writes == []


def test_changed_own_command_is_not_restored_from_old_backup(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    backend.entries[entries[0].path] = replace(
        backend.entries[entries[0].path],
        command=entries[0].command.replace("TEXT", "PRON"),
    )
    with pytest.raises(ShortcutError):
        controller.on()
    assert backend.entries[entries[0].path].binding == ""
    assert True not in flags


def test_conflict_with_foreign_shortcut_does_not_activate_or_change_foreign_entry(
    setup,
):
    controller, backend, journal, flags, entries = setup
    controller.off()
    foreign = replace(entries[2], binding="F1")
    backend.entries[foreign.path] = foreign
    with pytest.raises(ShortcutError, match="otro atajo personal"):
        controller.on()
    assert backend.entries[foreign.path] == foreign
    assert True not in flags


def test_read_failure_does_not_prevent_off_releasing_other_own_keys(setup):
    controller, backend, journal, flags, entries = setup
    backend.read_failures.add(entries[0].path)
    with pytest.raises(ShortcutError, match="lectura"):
        controller.off()
    assert backend.entries[entries[1].path].binding == ""
    assert flags == [False]


def test_mode_flag_failure_does_not_prevent_releasing_keys(setup):
    controller, backend, journal, flags, entries = setup

    def fail(active):
        raise ShortcutError("indicador no escribible")

    controller.set_mode = fail
    with pytest.raises(ShortcutError, match="indicador"):
        controller.off()
    assert all(not backend.entries[entry.path].binding for entry in entries[:2])


def test_journal_write_failure_prevents_activation_but_off_still_releases(
    setup, monkeypatch
):
    controller, backend, journal, flags, entries = setup

    def fail(records):
        raise ShortcutError("disco lleno")

    monkeypatch.setattr(journal, "save", fail)
    with pytest.raises(ShortcutError, match="disco lleno"):
        controller.on()
    assert True not in flags
    assert all(not backend.entries[entry.path].binding for entry in entries[:2])


def test_corrupt_journal_is_preserved_and_off_prioritizes_keyboard_recovery(setup):
    controller, backend, journal, flags, entries = setup
    journal.path.write_text("CORRUPTO")
    with pytest.raises(ShortcutError, match="Restauración manual"):
        controller.off()
    assert journal.path.read_text() == "CORRUPTO"
    assert all(not backend.entries[entry.path].binding for entry in entries[:2])


def test_crash_after_saving_but_before_disabling_is_recoverable(setup):
    controller, backend, journal, flags, entries = setup
    journal.save(
        {
            entry.path: SavedBinding(entry.command, entry.binding, True)
            for entry in entries[:2]
        }
    )
    controller.off()
    controller.on()
    assert list(backend.entries.values()) == entries


def test_crash_after_restoring_but_before_journal_confirmation_is_recoverable(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    backend.entries[entries[0].path] = entries[0]
    controller.on()
    assert list(backend.entries.values()) == entries


def test_journal_lock_rejects_overlapping_control_commands(setup):
    journal = setup[2]
    with journal.lock():
        with pytest.raises(ShortcutError, match="otro cambio"):
            with journal.lock():
                pytest.fail("No debe adquirir el mismo bloqueo")


@pytest.mark.parametrize(
    "command,owned",
    [
        (
            "/usr/bin/python3 -m audiobook_qc.capture_save_probe "
            "--desktop --db /x TEXT",
            True,
        ),
        ("/usr/bin/python3 -m audiobook_qc.capture_save_probe --db /x TEXT", False),
        ("echo -m audiobook_qc.capture_save_probe --desktop", False),
        ("/usr/bin/python3 -m otro_modulo --desktop", False),
        ('"sin cierre', False),
        ("gnome-terminal", False),
    ],
)
def test_ownership_uses_command_signature_not_name_index_or_path(command, owned):
    assert (
        replace(shortcut(999, "F1"), name="audiobook-qc", command=command).owned
        is owned
    )


def test_real_adapter_changes_only_binding_and_reads_back(monkeypatch):
    entry = shortcut(999, "F1")
    backend = GSettingsShortcuts()
    commands = []

    def run(*args):
        commands.append(args)
        if args[0] == "set":
            assert args[2:] == ("binding", repr(""))
            return ""
        key = args[-1]
        if key == "custom-keybindings":
            return repr([entry.path])
        if key == "binding":
            return repr(
                "" if any(command[0] == "set" for command in commands) else "F1"
            )
        return repr(getattr(entry, key))

    monkeypatch.setattr(backend, "_run", run)
    backend.write_binding(entry, "")
    assert [command for command in commands if command[0] == "set"] == [
        (
            "set",
            "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:"
            + entry.path,
            "binding",
            "''",
        )
    ]


def test_adapter_refuses_overwriting_concurrent_manual_edit(monkeypatch):
    entry = shortcut(999, "F1")
    backend = GSettingsShortcuts()
    monkeypatch.setattr(backend, "paths", lambda: [entry.path])
    monkeypatch.setattr(
        backend, "read", lambda path: replace(entry, binding="<Shift>F1")
    )
    monkeypatch.setattr(backend, "_run", lambda *args: pytest.fail("No debe escribir"))
    with pytest.raises(ShortcutError, match="cambió"):
        backend.write_binding(entry, "")


def test_gsettings_transport_errors_are_explicit(monkeypatch):
    backend = GSettingsShortcuts()

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("gsettings", 5)

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(ShortcutError):
        backend.paths()


def test_gsettings_success_without_persisting_binding_is_rejected(monkeypatch):
    entry = shortcut(77, "F1")
    backend = GSettingsShortcuts()
    monkeypatch.setattr(backend, "paths", lambda: [entry.path])
    monkeypatch.setattr(backend, "read", lambda path: entry)
    monkeypatch.setattr(backend, "_run", lambda *args: "")
    with pytest.raises(ShortcutError, match="confirmar"):
        backend.write_binding(entry, "")


@pytest.mark.parametrize(
    "value", ["['/fuera/de/gnome/']", "['x', 'x']", "'no es lista'", "INVALIDO"]
)
def test_invalid_gsettings_paths_cannot_target_arbitrary_configuration(
    monkeypatch, value
):
    backend = GSettingsShortcuts()
    monkeypatch.setattr(backend, "_run", lambda *args: value)
    with pytest.raises(ShortcutError):
        backend.paths()


def test_rename_is_preserved_and_does_not_change_ownership(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    backend.entries[entries[0].path] = replace(
        backend.entries[entries[0].path], name="Mi atajo personal de texto"
    )
    controller.on()
    assert backend.entries[entries[0].path].name == "Mi atajo personal de texto"
    assert backend.entries[entries[0].path].binding == "F1"


def test_lost_backup_never_invents_combinations_for_blank_entries(setup):
    controller, backend, journal, flags, entries = setup
    controller.off()
    journal.path.unlink()
    with pytest.raises(ShortcutError, match="No hay combinaciones"):
        controller.on()
    assert True not in flags
    assert all(not backend.entries[entry.path].binding for entry in entries[:2])


def test_active_status_detects_manual_changes(setup):
    controller, backend, journal, flags, entries = setup
    controller.on()
    backend.entries[entries[1].path] = replace(entries[1], binding="<Shift>F7")
    message, synced = controller.status(True)
    assert not synced and "DESINCRONIZADOS" in message


def test_mode_flag_activation_failure_releases_bindings_again(setup):
    controller, backend, journal, flags, entries = setup

    def set_flag(active):
        flags.append(active)
        if active:
            raise ShortcutError("no se pudo activar el indicador")

    controller.set_mode = set_flag
    with pytest.raises(ShortcutError, match="indicador"):
        controller.on()
    assert flags[-1] is False
    assert all(not backend.entries[entry.path].binding for entry in entries[:2])


def test_cli_mode_status_and_operations_use_fake_gnome_only(
    tmp_path, monkeypatch, capsys, isolated_desktop_sources
):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("DISPLAY", ":0")
    from audiobook_qc.jobs import JobStore

    store = JobStore()
    store.configure(str(tmp_path / "trabajos"))
    store.select(store.create("Prueba GNOME").id)
    backend = MemoryBindings([shortcut(37, "F6")])
    monkeypatch.setattr(correction_mode, "GSettingsShortcuts", lambda: backend)
    assert correction_mode.main(["status"]) == 1
    assert "DESINCRONIZADOS" in capsys.readouterr().out
    assert correction_mode.main(["off"]) == 0
    assert not correction_mode.is_active()
    assert correction_mode.main(["on"]) == 0
    assert correction_mode.is_active()
    assert correction_mode.main(["off"]) == 0
    assert not correction_mode.is_active()
    assert backend.entries[shortcut(37, "F6").path].binding == ""
