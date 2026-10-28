"""Consulta puntual del estado de una instancia existente de mpv por JSON IPC."""

import json
import math
import socket
import time
from dataclasses import dataclass

DEFAULT_SOCKET = "/tmp/audiobook-qc-mpv.sock"
DEFAULT_TIMEOUT = 3.0
MAX_MESSAGE_BYTES = 1024 * 1024


class MpvError(Exception):
    """Fallo esperado de conexión, protocolo o consulta a mpv."""


class MpvIPC:
    """Transporte secuencial de solo consulta sobre un socket ya conectado.

    No comparte una conexión entre hilos. Conserva los bytes que sobren después
    de cada línea y descarta eventos y respuestas ajenos a la petición actual.
    """

    def __init__(
        self, connection: socket.socket, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        self.connection = connection
        self.timeout = timeout
        self._buffer = b""
        self._request_id = 0

    def _read_message(self, deadline: float) -> dict[str, object]:
        while b"\n" not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MpvError("Tiempo de espera agotado al consultar mpv.")
            self.connection.settimeout(remaining)
            chunk = self.connection.recv(4096)
            if not chunk:
                raise MpvError("mpv cerró la conexión antes de completar la respuesta.")
            self._buffer += chunk
            if len(self._buffer.split(b"\n", 1)[0]) > MAX_MESSAGE_BYTES:
                raise MpvError("Respuesta IPC inválida: mensaje demasiado grande.")
        line, self._buffer = self._buffer.split(b"\n", 1)
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MpvError("Respuesta IPC inválida: se esperaba JSON UTF-8.") from exc
        if not isinstance(message, dict):
            raise MpvError("Respuesta IPC inválida: se esperaba un objeto JSON.")
        return message

    def get_property(self, name: str) -> object:
        """Obtiene datos nativos; devuelve None si la propiedad no está disponible."""
        self._request_id += 1
        request_id = self._request_id
        request = {"command": ["get_property", name], "request_id": request_id}
        deadline = time.monotonic() + self.timeout
        try:
            self.connection.settimeout(self.timeout)
            self.connection.sendall((json.dumps(request) + "\n").encode("utf-8"))
            while True:
                if time.monotonic() >= deadline:
                    raise MpvError("Tiempo de espera agotado al consultar mpv.")
                message = self._read_message(deadline)
                if "event" in message and "request_id" not in message:
                    continue
                response_id = message.get("request_id")
                if type(response_id) is not int:
                    raise MpvError(
                        "Respuesta IPC inválida: request_id ausente o inválido."
                    )
                if response_id != request_id:
                    continue
                error = message.get("error")
                if not isinstance(error, str):
                    raise MpvError("Respuesta IPC inválida: falta el estado error.")
                if error == "property unavailable":
                    return None
                if error != "success":
                    raise MpvError(f"mpv devolvió un error para {name}: {error}.")
                if "data" not in message:
                    raise MpvError("Respuesta IPC inválida: falta data.")
                return message["data"]
        except TimeoutError as exc:
            raise MpvError("Tiempo de espera agotado al consultar mpv.") from exc
        except OSError as exc:
            raise MpvError(f"Error de transporte IPC: {exc}.") from exc


@dataclass(frozen=True)
class MpvState:
    filename: str | None
    path: str | None
    position: float | None
    duration: float | None
    paused: bool | None


def _text(value: object, name: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise MpvError(f"Respuesta IPC inválida: {name} debe ser texto o null.")


def _seconds(value: object, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise MpvError(f"Respuesta IPC inválida: {name} debe ser un número o null.")
    try:
        number = float(value)
    except OverflowError as exc:
        raise MpvError(f"Respuesta IPC inválida: {name} fuera de rango.") from exc
    if not math.isfinite(number):
        raise MpvError(f"Respuesta IPC inválida: {name} no es finito.")
    return number


def query_state(ipc: MpvIPC) -> MpvState:
    """Lee cinco propiedades consecutivas; no es una instantánea atómica."""
    filename = _text(ipc.get_property("filename"), "filename")
    path = _text(ipc.get_property("path"), "path")
    position = _seconds(ipc.get_property("time-pos"), "time-pos")
    duration = _seconds(ipc.get_property("duration"), "duration")
    paused = ipc.get_property("pause")
    if paused is not None and type(paused) is not bool:
        raise MpvError("Respuesta IPC inválida: pause debe ser booleano o null.")
    return MpvState(filename, path, position, duration, paused)


def read_state(socket_path: str = DEFAULT_SOCKET) -> MpvState:
    """Conecta a mpv sin iniciarlo ni modificar su estado; siempre cierra el socket."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(DEFAULT_TIMEOUT)
            connection.connect(socket_path)
            return query_state(MpvIPC(connection))
    except FileNotFoundError as exc:
        raise MpvError(
            f"Socket inexistente: {socket_path}. Inicia mpv con --input-ipc-server."
        ) from exc
    except ConnectionRefusedError as exc:
        raise MpvError(
            f"Conexión rechazada: {socket_path}. mpv puede no estar ejecutándose."
        ) from exc
    except TimeoutError as exc:
        raise MpvError(
            f"Tiempo de espera agotado al conectar a {socket_path}."
        ) from exc
    except OSError as exc:
        raise MpvError(f"No se pudo acceder al socket {socket_path}: {exc}.") from exc
