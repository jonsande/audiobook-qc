"""Instancia mpv dedicada: socket reconstruible por UUID y lectura coherente."""

import os
import socket
import stat
import subprocess
import time
from pathlib import Path

from audiobook_qc.integrations.mpv import (
    DEFAULT_TIMEOUT,
    MpvError,
    MpvIPC,
    MpvState,
    query_state,
)


def socket_path(job_id: str) -> Path:
    root = Path(os.environ.get("XDG_RUNTIME_DIR", ""))
    if not root.is_absolute():
        raise MpvError("Se requiere XDG_RUNTIME_DIR absoluto para el mpv del trabajo.")
    path = root / "audiobook-qc" / (job_id + ".sock")
    if len(os.fsencode(path)) >= 108:
        raise MpvError(
            "Ruta runtime demasiado larga para un socket Unix (máximo 107 bytes)."
        )
    return path


def read_state(path: str) -> MpvState:
    """Mismo socket/conexión; rechaza cambios de archivo observados en la lectura."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(DEFAULT_TIMEOUT)
            connection.connect(path)
            ipc = MpvIPC(connection)
            before = ipc.get_property("path")
            state = query_state(ipc)
            after = ipc.get_property("path")
            if before != state.path or before != after:
                raise MpvError("mpv cambió de archivo durante la captura; reinténtalo.")
            return state
    except OSError as exc:
        raise MpvError(f"mpv del trabajo no disponible en {path}: {exc}") from exc


def _live(path: Path, *, clean_stale: bool = False) -> bool:
    if path.is_symlink():
        raise MpvError("La ruta IPC no puede ser un enlace simbólico.")
    if not path.exists():
        return False
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise MpvError(
            "La ruta IPC está ocupada por un archivo/enlace ajeno; no se reemplaza."
        )
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(DEFAULT_TIMEOUT)
            connection.connect(str(path))
        return True
    except ConnectionRefusedError:
        # Solo launch elimina un socket sin servidor, bajo el bloqueo del trabajo.
        if clean_stale:
            path.unlink()
        return False
    except OSError as exc:
        raise MpvError(f"No se pudo comprobar el socket del trabajo: {exc}") from exc


def launch(job_id: str, files: tuple[Path, ...], log: Path) -> dict:
    path = socket_path(job_id)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = parent.stat()
    if (
        parent.is_symlink()
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise MpvError("El directorio runtime de audiobook-qc debe ser privado (0700).")
    if _live(path, clean_stale=True):
        read_state(str(path))
        return dict(status="running", socket=str(path))
    if not files:
        raise MpvError("Indica los archivos de audio al lanzar mpv por primera vez.")
    command = [
        "mpv",
        "--idle=yes",
        "--pause",
        "--force-window=yes",
        f"--input-ipc-server={path}",
        "--",
        *(str(file) for file in files),
    ]
    with log.open("ab") as output:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            start_new_session=True,
        )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise MpvError(f"mpv terminó al arrancar; consulta {log}.")
        if _live(path):
            return dict(status="started", socket=str(path), pid=process.pid)
        time.sleep(0.05)
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    raise MpvError(
        f"mpv no publicó su socket; se cerró el proceso lanzado. Consulta {log}."
    )
