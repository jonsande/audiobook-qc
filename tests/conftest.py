"""Ningún test puede consultar o modificar la selección real del usuario."""

import pytest


@pytest.fixture(autouse=True)
def isolated_job_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.fixture
def isolated_desktop_sources(monkeypatch):
    """Dobles de la nueva frontera; suites históricas siguen probando su alcance."""
    from types import SimpleNamespace

    from audiobook_qc import capture_save_probe, correction_mode

    def prepare(job):
        return SimpleNamespace(
            read_document=lambda: capture_save_probe.okular.read_state(None),
            read_audio=lambda: capture_save_probe.mpv.read_state(
                "/associated/job.sock"
            ),
            verify=lambda captured: None,
        )

    monkeypatch.setattr(capture_save_probe, "prepare_job_sources", prepare)
    monkeypatch.setattr(correction_mode, "prepare_job_sources", prepare)
