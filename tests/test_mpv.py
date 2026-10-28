"""Pruebas del protocolo sin ejecutar mpv ni necesitar sockets del sistema."""

import json
import socket
from collections import deque
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from audiobook_qc import mpv_probe
from audiobook_qc.integrations.mpv import (
    MpvError,
    MpvIPC,
    MpvState,
    query_state,
    read_state,
)


class Stream:
    """Doble mínimo que entrega fragmentos de un flujo de bytes."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = deque(chunks)
        self.sent: list[bytes] = []

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, size: int) -> bytes:
        return self.chunks.popleft() if self.chunks else b""

    def settimeout(self, timeout: float) -> None:
        pass

    def client(self) -> MpvIPC:
        return MpvIPC(cast(socket.socket, self))


def reply(data: object, request_id: int = 1, error: str = "success") -> bytes:
    return (
        json.dumps(
            {"data": data, "error": error, "request_id": request_id}, ensure_ascii=False
        ).encode("utf-8")
        + b"\n"
    )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00.000"),
        (1104.517, "00:18:24.517"),
        (59.9996, "00:01:00.000"),
        (3599.9996, "01:00:00.000"),
        (360000.001, "100:00:00.001"),
        (-1.25, "-00:00:01.250"),
        (-0.0001, "00:00:00.000"),
    ],
)
def test_time_format(seconds: float, expected: str) -> None:
    assert mpv_probe.format_time(seconds) == expected


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), -float("inf")])
def test_time_format_rejects_nonfinite_values(seconds: float) -> None:
    with pytest.raises(ValueError):
        mpv_probe.format_time(seconds)


def test_fragmented_json_including_multibyte_utf8() -> None:
    payload = reply("capítulo.mp3")
    stream = Stream([bytes([byte]) for byte in payload])
    assert stream.client().get_property("filename") == "capítulo.mp3"
    assert stream.sent[0].endswith(b"\n")
    assert json.loads(stream.sent[0]) == {
        "command": ["get_property", "filename"],
        "request_id": 1,
    }


def test_grouped_replies_events_and_request_ids() -> None:
    stream = Stream(
        [
            b'{"event":"file-loaded"}\n'
            + reply("unrelated", 99)
            + reply("chapter.wav", 1)
            + reply("/audio/chapter.wav", 2)
            + reply(1104.517123, 3)
            + reply(2272.041, 4)
            + reply(True, 5)
        ]
    )
    state = query_state(stream.client())
    assert state == MpvState(
        "chapter.wav", "/audio/chapter.wav", 1104.517123, 2272.041, True
    )
    commands = [json.loads(data) for data in stream.sent]
    assert [command["command"] for command in commands] == [
        ["get_property", name]
        for name in ("filename", "path", "time-pos", "duration", "pause")
    ]
    assert [command["request_id"] for command in commands] == [1, 2, 3, 4, 5]
    assert "Posición (segundos): 1104.517123" in mpv_probe.format_state(state)


def test_mpv_error_is_not_silenced() -> None:
    stream = Stream([reply(None, error="property not found")])
    with pytest.raises(MpvError, match="filename: property not found"):
        stream.client().get_property("filename")


def test_unavailable_properties_and_null_values() -> None:
    stream = Stream(
        [
            reply(None, 1, "property unavailable")
            + reply(None, 2)
            + reply(None, 3, "property unavailable")
            + reply(None, 4, "property unavailable")
            + reply(False, 5)
        ]
    )
    state = query_state(stream.client())
    assert state == MpvState(None, None, None, None, False)
    output = mpv_probe.format_state(state)
    assert "Posición: no disponible temporalmente" in output
    assert "Duración: no disponible temporalmente" in output
    assert "Pausado: no" in output


@pytest.mark.parametrize(
    "payload",
    [
        b"not json\n",
        b"\xff\n",
        b"[]\n",
        b'{"error":"success","data":1}\n',
        b'{"request_id":true,"error":"success","data":1}\n',
        b'{"request_id":1,"data":1}\n',
        b'{"request_id":1,"error":"success"}\n',
    ],
)
def test_invalid_response(payload: bytes) -> None:
    with pytest.raises(MpvError, match="Respuesta IPC inválida"):
        Stream([payload]).client().get_property("time-pos")


def test_connection_closed_with_partial_message() -> None:
    with pytest.raises(MpvError, match="cerró la conexión"):
        Stream([b'{"data":']).client().get_property("time-pos")


def test_response_size_is_bounded() -> None:
    with (
        patch("audiobook_qc.integrations.mpv.MAX_MESSAGE_BYTES", 10),
        pytest.raises(MpvError, match="demasiado grande"),
    ):
        Stream([b"x" * 11]).client().get_property("time-pos")


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionResetError("reset")])
def test_transport_errors(error: OSError) -> None:
    stream = Stream([])
    with (
        patch.object(stream, "recv", side_effect=error),
        pytest.raises(MpvError),
    ):
        stream.client().get_property("time-pos")


def test_deadline_applies_even_when_unrelated_events_arrive() -> None:
    with (
        patch(
            "audiobook_qc.integrations.mpv.time.monotonic",
            side_effect=[0.0, 0.0, 0.0, 4.0],
        ),
        pytest.raises(MpvError, match="Tiempo de espera"),
    ):
        Stream([b'{"event":"tick"}\n']).client().get_property("time-pos")


@pytest.mark.parametrize(
    ("index", "value"), [(0, 42), (2, True), (2, float("nan")), (3, "1"), (4, "yes")]
)
def test_property_types_are_validated(index: int, value: object) -> None:
    values: list[object] = ["a.wav", "/a.wav", 1.125, 3.0, True]
    values[index] = value
    stream = Stream([b"".join(reply(item, i + 1) for i, item in enumerate(values))])
    with pytest.raises(MpvError, match="Respuesta IPC inválida"):
        query_state(stream.client())


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (FileNotFoundError(), "Socket inexistente"),
        (ConnectionRefusedError(), "Conexión rechazada"),
        (PermissionError(), "No se pudo acceder"),
        (TimeoutError(), "Tiempo de espera"),
    ],
)
def test_connection_errors(error: OSError, message: str) -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.connect.side_effect = error
    with (
        patch("audiobook_qc.integrations.mpv.socket.socket", return_value=connection),
        pytest.raises(MpvError, match=message),
    ):
        read_state("/test.sock")
    connection.__exit__.assert_called_once()


def test_cli_expected_error_is_readable(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(
        mpv_probe, "read_state", side_effect=MpvError("Socket inexistente")
    ):
        assert mpv_probe.main(["--socket", "/missing.sock"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: Socket inexistente\n"


def test_cli_success(capsys: pytest.CaptureFixture[str]) -> None:
    state = MpvState("a.wav", "/a.wav", 0.125123, None, True)
    with patch.object(mpv_probe, "read_state", return_value=state) as read:
        assert mpv_probe.main(["--socket", "/test.sock"]) == 0
    read.assert_called_once_with("/test.sock")
    output = capsys.readouterr().out
    assert "Posición: 00:00:00.125" in output
    assert "Posición (segundos): 0.125123" in output
    assert "Pausado: sí" in output
