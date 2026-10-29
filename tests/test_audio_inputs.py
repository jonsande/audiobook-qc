"""Expansión de carpetas: archivos temporales y lanzamiento mpv sustituido."""

import json
from pathlib import Path

import pytest

from audiobook_qc import job_sources, jobs_cli
from audiobook_qc.integrations.mpv import MpvError, MpvState
from audiobook_qc.job_sources import (
    DesktopSources,
    SourcesConfig,
    expand_audio_inputs,
    load_sources,
    save_sources,
)
from audiobook_qc.jobs import JobStore


@pytest.fixture
def job(tmp_path):
    store = JobStore()
    store.configure(str(tmp_path / "trabajos"))
    return store.create("Capítulos en carpeta")


@pytest.fixture
def launches(monkeypatch):
    calls = []

    def launch(job_id, paths, log):
        calls.append((job_id, paths, log))
        return {"status": "started"}

    monkeypatch.setattr(job_sources.job_mpv, "launch", launch)
    return calls


def make_files(directory: Path, names: list[str]) -> list[Path]:
    directory.mkdir(exist_ok=True)
    paths = [directory / name for name in names]
    for path in paths:
        path.write_bytes(b"audio simulado")
    return paths


def test_directory_expands_audio_in_natural_order_without_subdirectories(tmp_path):
    directory = tmp_path / "audios ñ"
    files = make_files(
        directory, ["Capítulo 10.mp3", "Capítulo 2.MP3", "Capítulo 1.flac"]
    )
    make_files(directory, ["notas.txt", "libro.pdf", "playlist.m3u"])
    make_files(directory / "subcarpeta.mp3", ["Capítulo 0.mp3"])
    assert expand_audio_inputs([str(directory)]) == (files[2], files[1], files[0])


def test_natural_order_has_deterministic_tie_breaker(tmp_path):
    directory = tmp_path / "audios"
    make_files(directory, ["cap2.mp3", "cap10.mp3", "Cap2.mp3", "cap02.mp3"])
    assert [p.name for p in expand_audio_inputs([str(directory)])] == [
        "Cap2.mp3",
        "cap02.mp3",
        "cap2.mp3",
        "cap10.mp3",
    ]


def test_mixed_files_and_multiple_directories_preserve_argument_order(tmp_path):
    a = make_files(tmp_path / "a", ["3.mp3", "1.mp3"])
    b = make_files(tmp_path / "b", ["10.opus", "2.m4b"])
    explicit = make_files(tmp_path, ["epílogo.wav"])[0]
    assert expand_audio_inputs([str(a[0].parent), str(explicit), str(b[0].parent)]) == (
        a[1],
        a[0],
        explicit,
        b[1],
        b[0],
    )


@pytest.mark.parametrize("explicit_first", [True, False])
def test_duplicate_files_directories_and_symlinks_keep_first_occurrence(
    tmp_path, explicit_first
):
    a, b = make_files(tmp_path / "audios", ["1.mp3", "2.mp3"])
    alias = tmp_path / "alias.mp3"
    alias.symlink_to(b)
    args = [str(b), str(a.parent)] if explicit_first else [str(a.parent), str(b)]
    args += [str(a.parent), str(alias)]
    assert expand_audio_inputs(args) == ((b, a) if explicit_first else (a, b))


@pytest.mark.parametrize("contents", ["empty", "non-audio", "nested-only"])
def test_empty_audio_directory_fails_without_launch_or_changing_sources(
    tmp_path, job, launches, capsys, contents
):
    directory = tmp_path / "sin audios"
    directory.mkdir()
    if contents == "non-audio":
        make_files(directory, ["notas.txt", "lista.m3u"])
    elif contents == "nested-only":
        make_files(directory / "subcarpeta", ["1.mp3"])
    previous = make_files(tmp_path, ["anterior.mp3"])[0]
    save_sources(job, SourcesConfig(audio_files=(previous,)))
    before = (job.directory / "sources.json").read_bytes()
    assert jobs_cli.main(["launch-mpv", job.id, str(directory)]) == 1
    assert "no contiene archivos de audio admitidos" in capsys.readouterr().err
    assert launches == []
    assert (job.directory / "sources.json").read_bytes() == before


def test_directory_playlist_persisted_and_reopened_without_rescanning(
    tmp_path, job, launches
):
    directory = tmp_path / "audios"
    files = make_files(directory, ["10.mp3", "2.mp3", "1.mp3"])
    expected = (files[2], files[1], files[0])
    assert jobs_cli.main(["launch-mpv", job.id, str(directory)]) == 0
    data = json.loads((job.directory / "sources.json").read_text())
    assert data["audio_files"] == [str(file) for file in expected]
    assert str(directory) not in data["audio_files"]
    make_files(directory, ["3.mp3"])
    assert jobs_cli.main(["launch-mpv", job.id]) == 0
    assert [call[1] for call in launches] == [expected, expected]
    assert load_sources(job).audio_files == expected


def test_expanded_playlist_still_rejects_undeclared_active_audio(
    tmp_path, job, launches, monkeypatch
):
    directory = tmp_path / "audios"
    file = make_files(directory, ["1.mp3"])[0]
    assert jobs_cli.main(["launch-mpv", job.id, str(directory)]) == 0
    sources = DesktopSources(Path("/unused.sock"), load_sources(job), None)
    monkeypatch.setattr(
        job_sources.job_mpv,
        "read_state",
        lambda path: MpvState(file.name, str(file), 19.300243, 100, True),
    )
    assert sources.read_audio().path == str(file)
    extra = make_files(directory, ["2.mp3"])[0]
    monkeypatch.setattr(
        job_sources.job_mpv,
        "read_state",
        lambda path: MpvState(extra.name, str(extra), 12.0, 100, True),
    )
    with pytest.raises(MpvError, match="capítulos asociados"):
        sources.read_audio()


def test_explicit_files_keep_their_original_order_and_extension_compatibility(tmp_path):
    a, b = make_files(tmp_path, ["10.mp3", "2.custom"])
    assert expand_audio_inputs([str(a), str(b)]) == (a, b)
