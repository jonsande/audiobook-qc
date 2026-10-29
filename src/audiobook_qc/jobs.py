"""Catálogo local y resolución exclusiva del destino de las capturas.

El mismo flock protege configuración, selección, modo on y captura completa.
No se espera a una operación concurrente: el usuario debe volver a intentarlo.
"""

import fcntl
import json
import os
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from audiobook_qc.correction_job import CorrectionJob
from audiobook_qc.integrations.activation import ActivationBusy
from audiobook_qc.sqlite_repository import SchemaError, SQLiteIncidentRepository


class JobError(Exception):
    """Configuración o trabajo inválido/inaccesible."""


class NoActiveJob(JobError):
    """No se ha seleccionado un destino para las capturas."""


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("se esperaba un objeto JSON")
        return data
    except (OSError, ValueError, UnicodeError) as exc:
        raise JobError(f"No se pudo leer {path}: {exc}") from exc


def _write(path: Path, data: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _identifier(value: str) -> str:
    try:
        if str(UUID(value)) != value:
            raise ValueError("UUID no canónico")
        return value
    except (ValueError, TypeError, AttributeError) as exc:
        raise JobError(
            "Identificador de trabajo inválido; utiliza su UUID completo."
        ) from exc


class JobStore:
    def __init__(self, config: Path | None = None) -> None:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        if not root.is_absolute():
            raise JobError("XDG_CONFIG_HOME debe ser absoluto.")
        self.config = config or root / "audiobook-qc/jobs.json"

    @contextmanager
    def lock(self) -> Iterator[None]:
        try:
            self.config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            handle = self.config.with_suffix(".lock").open("a")
        except OSError as exc:
            raise JobError(f"Configuración de trabajos inaccesible: {exc}") from exc
        with handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ActivationBusy(
                    "Hay una captura o cambio de trabajo/modo en curso; reinténtalo."
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _load(self) -> dict:
        if not self.config.exists():
            raise JobError(
                "Configura primero el directorio principal con "
                "python -m audiobook_qc.jobs_cli configure."
            )
        data = _read(self.config)
        if (
            set(data) != {"version", "root", "active"}
            or type(data["version"]) is not int
            or data["version"] != 1
            or not isinstance(data["root"], str)
            or not Path(data["root"]).is_absolute()
        ):
            raise JobError("Configuración de trabajos inválida; no se sobrescribe.")
        if data["active"] is not None:
            _identifier(data["active"])
        return data

    def configuration(self) -> dict:
        with self.lock():
            return self._load()

    def configure(self, directory: str) -> None:
        if not directory.strip():
            raise JobError("Indica un directorio principal no vacío.")
        root = Path(directory).expanduser().resolve()
        with self.lock():
            previous = self._load() if self.config.exists() else None
            root.mkdir(parents=True, exist_ok=True)
            # El cambio explícito no mueve trabajos y elimina la selección anterior.
            active = (
                previous["active"]
                if previous and previous["root"] == str(root)
                else None
            )
            _write(self.config, dict(version=1, root=str(root), active=active))

    def _get(self, data: dict, job_id: str) -> CorrectionJob:
        directory = Path(data["root"]) / _identifier(job_id)
        metadata = _read(directory / "job.json")
        try:
            if set(metadata) != {"version", "id", "name", "created_at"}:
                raise ValueError("campos inesperados")
            if (
                type(metadata["version"]) is not int
                or metadata["version"] != 1
                or metadata["id"] != job_id
                or not isinstance(metadata["name"], str)
                or not metadata["name"].strip()
            ):
                raise ValueError("identidad o nombre inválido")
            created = datetime.fromisoformat(metadata["created_at"])
            if created.utcoffset() is None:
                raise ValueError("fecha sin zona horaria")
            if directory.is_symlink():
                raise ValueError("el directorio del trabajo no puede ser un enlace")
            return CorrectionJob(job_id, metadata["name"], directory, created)
        except (ValueError, TypeError) as exc:
            raise JobError(
                f"Metadatos de trabajo inválidos: {directory}: {exc}"
            ) from exc

    def create(self, name: str) -> CorrectionJob:
        if not name.strip():
            raise JobError("El nombre del audiolibro no puede estar vacío.")
        with self.lock():
            data = self._load()
            root = Path(data["root"])
            if not root.is_dir():
                raise JobError("El directorio principal no está disponible.")
            job_id = str(uuid4())
            # Solo la identidad determina la carpeta; se admiten títulos repetidos.
            job = CorrectionJob(job_id, name, root / job_id, datetime.now(timezone.utc))
            job.directory.mkdir(mode=0o700)
            with SQLiteIncidentRepository(job_database(job)) as repository:
                repository.initialize()
            # Publicar metadatos al final; una creación interrumpida se rechaza.
            _write(
                job.directory / "job.json",
                dict(
                    version=1,
                    id=job.id,
                    name=job.name,
                    created_at=job.created_at.isoformat(),
                ),
            )
            return job

    def get(self, job_id: str) -> CorrectionJob:
        with self.lock():
            return self._get(self._load(), job_id)

    @contextmanager
    def job_context(self, job_id: str) -> Iterator[CorrectionJob]:
        """Mantiene la identidad fija mientras un adaptador configura sus fuentes."""
        with self.lock():
            yield self._get(self._load(), job_id)

    def list(self) -> list[CorrectionJob]:
        with self.lock():
            data = self._load()
            root = Path(data["root"])
            if not root.is_dir():
                raise JobError("El directorio principal no está disponible.")
            jobs = []
            for directory in sorted(root.iterdir()):
                try:
                    _identifier(directory.name)
                except JobError:
                    continue
                jobs.append(self._get(data, directory.name))
            return jobs

    @contextmanager
    def _repository(self, job: CorrectionJob) -> Iterator[SQLiteIncidentRepository]:
        try:
            if job_database(job).is_symlink():
                raise JobError("La base del trabajo no puede ser un enlace.")
            if not os.access(job_database(job), os.R_OK | os.W_OK) or not os.access(
                job.directory, os.R_OK | os.W_OK | os.X_OK
            ):
                raise JobError(
                    f"Trabajo inválido o inaccesible — {job.name}: "
                    "se requiere acceso de lectura/escritura a la base y su carpeta."
                )
            repository = SQLiteIncidentRepository(job_database(job), existing=True)
            try:
                repository.validate_schema()
            except BaseException:
                repository.close()
                raise
        except (OSError, sqlite3.Error, SchemaError) as exc:
            raise JobError(
                f"Trabajo inválido o inaccesible — {job.name}: {exc}"
            ) from exc
        with repository:
            yield repository

    def select(self, job_id: str | None) -> None:
        with self.lock():
            data = self._load()
            if job_id is not None:
                with self._repository(self._get(data, job_id)):
                    pass
            data["active"] = job_id
            _write(self.config, data)

    @contextmanager
    def destination(self) -> Iterator[tuple[CorrectionJob, SQLiteIncidentRepository]]:
        """Fija y valida el destino hasta terminar el commit, sin crear SQLite."""
        with self.lock():
            data = self._load()
            if data["active"] is None:
                raise NoActiveJob(
                    "No hay trabajo activo; selecciona uno con "
                    "python -m audiobook_qc.jobs_cli select."
                )
            job = self._get(data, data["active"])
            with self._repository(job) as repository:
                yield job, repository

    def active(self) -> CorrectionJob:
        with self.destination() as (job, _):
            return job


def job_database(job: CorrectionJob) -> Path:
    """La organización SQLite pertenece al adaptador, no a la entidad."""
    return job.directory / "incidencias.sqlite3"


def job_data(job: CorrectionJob) -> dict:
    return dict(asdict(job), database=str(job_database(job)))
