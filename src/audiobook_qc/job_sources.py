"""Fuentes de escritorio asociadas a un trabajo, fuera del dominio de incidencias."""

import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from audiobook_qc.capture import CaptureError
from audiobook_qc.captured_incident import CapturedIncident
from audiobook_qc.correction_job import CorrectionJob
from audiobook_qc.integrations import job_mpv
from audiobook_qc.integrations.document_binding import (
    BoundDocument,
    DocumentNotOpen,
    resolve_document,
)
from audiobook_qc.integrations.mpv import MpvError, MpvState
from audiobook_qc.integrations.okular import OkularError, OkularState
from audiobook_qc.jobs import JobError, _read, _write

# Filtro de descubrimiento de carpetas; mpv comprueba la decodificación al abrir.
AUDIO_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".m4a",
        ".m4b",
        ".aac",
        ".flac",
        ".wav",
        ".ogg",
        ".oga",
        ".opus",
        ".aif",
        ".aiff",
        ".wma",
    }
)


class SourceError(CaptureError):
    """Una fuente explícita falta, es ambigua o no corresponde al trabajo."""


@dataclass(frozen=True)
class SourcesConfig:
    document: Path | None = None
    audio_files: tuple[Path, ...] = ()


def load_sources(job: CorrectionJob) -> SourcesConfig:
    path = job.directory / "sources.json"
    if not path.exists():
        return SourcesConfig()
    try:
        data = _read(path)
        if (
            set(data) != {"version", "document", "audio_files"}
            or type(data["version"]) is not int
            or data["version"] != 1
            or not isinstance(data["audio_files"], list)
            or any(
                not isinstance(file, str) or not Path(file).is_absolute()
                for file in data["audio_files"]
            )
            or (
                data["document"] is not None
                and (
                    not isinstance(data["document"], str)
                    or not Path(data["document"]).is_absolute()
                )
            )
        ):
            raise ValueError("campos o rutas inválidos")
        return SourcesConfig(
            Path(data["document"]) if data["document"] else None,
            tuple(Path(file) for file in data["audio_files"]),
        )
    except (JobError, ValueError, TypeError) as exc:
        raise SourceError(f"Asociación de fuentes inválida: {path}: {exc}") from exc


def save_sources(job: CorrectionJob, config: SourcesConfig) -> None:
    """El llamador conserva JobStore.job_context/destination durante los cambios."""
    _write(
        job.directory / "sources.json",
        dict(
            version=1,
            document=str(config.document) if config.document else None,
            audio_files=[str(file) for file in config.audio_files],
        ),
    )


def _file(value: str) -> Path:
    try:
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError("no es un archivo")
        return path
    except (OSError, ValueError, RuntimeError) as exc:
        raise SourceError(f"Fuente local inaccesible: {value}: {exc}") from exc


def set_document(job: CorrectionJob, document: str) -> SourcesConfig:
    config = replace(load_sources(job), document=_file(document))
    save_sources(job, config)
    return config


def _natural_audio_order(path: Path) -> tuple[tuple[str | int, ...], str]:
    parts = re.split(r"([0-9]+)", path.name.casefold())
    return tuple(
        int(part) if index % 2 else part for index, part in enumerate(parts)
    ), path.name


def expand_audio_inputs(values: list[str]) -> tuple[Path, ...]:
    """Conserva el orden de argumentos y ordena cada carpeta sin recursión.

    Deduplica por ruta canónica, conservando la primera aparición. Los archivos
    explícitos conservan la compatibilidad previa sin filtro de extensión.
    """
    result: dict[Path, None] = {}
    for value in values:
        try:
            path = Path(value).expanduser().resolve(strict=True)
            if path.is_dir():
                candidates = sorted(
                    (
                        child
                        for child in path.iterdir()
                        if child.is_file()
                        and child.suffix.casefold() in AUDIO_EXTENSIONS
                    ),
                    key=_natural_audio_order,
                )
                if not candidates:
                    raise SourceError(
                        f"El directorio no contiene archivos de audio admitidos: {path}"
                    )
            else:
                candidates = [path]
            for candidate in candidates:
                result[_file(str(candidate))] = None
        except (OSError, ValueError, RuntimeError) as exc:
            raise SourceError(f"Fuente local inaccesible: {value}: {exc}") from exc
    return tuple(result)


def launch_mpv(job: CorrectionJob, files: list[str]) -> dict:
    config = load_sources(job)
    paths = expand_audio_inputs(files) if files else config.audio_files
    for path in paths:
        _file(str(path))
    try:
        result = job_mpv.launch(job.id, paths, job.directory / "mpv.log")
    except MpvError as exc:
        raise SourceError(str(exc)) from exc
    if result["status"] == "running" and files and paths != config.audio_files:
        raise SourceError(
            "mpv ya está abierto; ciérralo antes de cambiar su lista de capítulos."
        )
    if files:
        save_sources(job, replace(config, audio_files=paths))
    return result


def launch_okular(job: CorrectionJob) -> dict:
    config = load_sources(job)
    if config.document is None:
        raise SourceError("Asocia primero el PDF con jobs_cli set-pdf UUID RUTA.")
    document = _file(str(config.document))
    try:
        view = resolve_document(document)
        return dict(status="running", owner=view.owner, object_path=view.object_path)
    except DocumentNotOpen:
        process = subprocess.Popen(
            ["okular", "--", str(document)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return dict(status="starting", pid=process.pid, document=str(document))
    except OkularError as exc:
        raise SourceError(str(exc)) from exc


@dataclass(frozen=True)
class DesktopSources:
    socket: Path
    config: SourcesConfig
    view: BoundDocument

    def read_document(self) -> OkularState:
        return self.view.read_state()

    def read_audio(self) -> MpvState:
        state = job_mpv.read_state(str(self.socket))
        if (
            state.path is None
            or not Path(state.path).is_absolute()
            or Path(state.path).resolve() not in self.config.audio_files
        ):
            raise MpvError(
                "El archivo cargado no está en los capítulos asociados al trabajo."
            )
        if state.filename is None or state.position is None:
            raise MpvError(
                "mpv del trabajo aún no tiene un archivo y posición disponibles."
            )
        return state

    def verify(self, captured: CapturedIncident) -> None:
        """Rechaza pérdida de dueño, duplicados y navegación observada antes de add."""
        try:
            current = resolve_document(self.view.document, bus=self.view.bus)
            if (current.owner, current.object_path) != (
                self.view.owner,
                self.view.object_path,
            ):
                raise OkularError("La vista de Okular se cerró o fue reemplazada.")
            state = current.read_state()
            if state.document != captured.document or state.page != captured.page:
                raise OkularError("Documento/página cambió durante la captura.")
        except (OkularError, OSError) as exc:
            raise SourceError(str(exc)) from exc


def prepare_job_sources(job: CorrectionJob) -> DesktopSources:
    config = load_sources(job)
    if config.document is None or not config.audio_files:
        raise SourceError(
            "Fuentes sin asociar: usa jobs_cli set-pdf y launch-mpv para este trabajo."
        )
    try:
        document = _file(str(config.document))
        sources = DesktopSources(
            job_mpv.socket_path(job.id), config, resolve_document(document)
        )
        sources.read_audio()
        return sources
    except (OkularError, MpvError, OSError) as exc:
        raise SourceError(str(exc)) from exc


def sources_data(job: CorrectionJob) -> dict:
    config = load_sources(job)
    try:
        socket = str(job_mpv.socket_path(job.id))
    except MpvError:
        # La asociación persistente puede consultarse fuera de una sesión gráfica.
        socket = None
    return dict(
        document=str(config.document) if config.document else None,
        audio_files=[str(file) for file in config.audio_files],
        mpv_socket=socket,
    )
