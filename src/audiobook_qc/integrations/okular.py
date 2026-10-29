"""Consulta aislada de Okular por D-Bus, sin activación ni control del visor."""

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit

OBJECT_PATH = "/okular"
INTERFACE = "org.kde.okular"
SERVICE_PATTERN = re.compile(r"org\.kde\.okular(?:-\d+)?\Z")


class OkularError(Exception):
    """Error esperado de descubrimiento, transporte o respuesta D-Bus."""


def parse_reply(output: str, signature: str) -> object:
    """Extrae un único resultado del JSON tipado que emite busctl."""
    try:
        reply = json.loads(output)
    except json.JSONDecodeError as exc:
        raise OkularError(
            "Respuesta D-Bus inválida: se esperaba JSON de busctl."
        ) from exc
    if (
        not isinstance(reply, dict)
        or reply.get("type") != signature
        or not isinstance(reply.get("data"), list)
        or len(reply["data"]) != 1
    ):
        raise OkularError(
            f"Respuesta D-Bus inválida: se esperaba la firma {signature}."
        )
    value = reply["data"][0]
    if signature == "s" and isinstance(value, str):
        return value
    if signature == "u" and type(value) is int and 0 <= value <= 2**32 - 1:
        return value
    if signature == "as" and isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return value
    raise OkularError(f"Respuesta D-Bus inválida para la firma {signature}.")


class SessionBus:
    """Ejecuta consultas sin shell ni autoactivación de servicios."""

    def call(
        self,
        service: str,
        path: str,
        interface: str,
        method: str,
        signature: str,
        *arguments: str,
    ) -> object:
        command = [
            "busctl",
            "--user",
            "--json=short",
            "--auto-start=no",
            "--allow-interactive-authorization=no",
            "--timeout=3",
            "call",
            service,
            path,
            interface,
            method,
            *arguments,
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=5, check=False
            )
        except FileNotFoundError as exc:
            raise OkularError(
                "No se encuentra busctl; esta prueba requiere esa herramienta."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise OkularError(f"Tiempo agotado en la consulta D-Bus {method}.") from exc
        except (OSError, UnicodeError) as exc:
            raise OkularError(f"No se pudo ejecutar busctl: {exc}.") from exc
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "sin detalle"
            raise OkularError(
                f"Fallo D-Bus en {service} {path} {method}: {detail} "
                f"(salida {result.returncode})."
            )
        return parse_reply(result.stdout, signature)

    def list_services(self) -> list[str]:
        names = cast(
            list[str],
            self.call(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
                "as",
            ),
        )
        return sorted({name for name in names if SERVICE_PATTERN.fullmatch(name)})


def select_service(services: list[str], requested: str | None = None) -> str:
    """Nunca adivina la ventana activa ni elige el primer servicio ambiguo."""
    if requested is not None:
        if requested not in services:
            raise OkularError(
                f"El servicio solicitado no está registrado: {requested}."
            )
        return requested
    if not services:
        raise OkularError(
            "No hay servicios de Okular; abre un PDF en la sesión actual."
        )
    if len(services) != 1:
        raise OkularError(
            "Hay varios servicios de Okular; elige uno con --service: "
            + ", ".join(services)
        )
    return services[0]


def verify_interface(xml: str) -> None:
    """Verifica las firmas reales antes de consultar la API observada en 21.12.3."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise OkularError("Introspección D-Bus inválida: XML mal formado.") from exc
    for name, signature in (("currentDocument", "s"), ("currentPage", "u")):
        method = root.find(f"./interface[@name='{INTERFACE}']/method[@name='{name}']")
        if method is None:
            raise OkularError(
                f"API de Okular incompatible: falta {name} en {OBJECT_PATH}."
            )
        args = [
            (arg.get("direction", "in"), arg.get("type"))
            for arg in method.findall("arg")
        ]
        if args != [("out", signature)]:
            raise OkularError(
                f"API de Okular incompatible: firma inesperada de {name}."
            )


def local_path(document: str) -> Path | None:
    """Normaliza solo rutas absolutas o URLs file locales inequívocas."""
    if document.startswith("/") and not document.startswith("//"):
        return Path(document)
    try:
        url = urlsplit(document)
    except ValueError:
        return None
    if (
        url.scheme == "file"
        and url.netloc.lower() in ("", "localhost")
        and url.path.startswith("/")
        and not url.query
        and not url.fragment
    ):
        return Path(unquote(url.path))
    return None


@dataclass(frozen=True)
class OkularState:
    service: str
    document: str | None
    path: Path | None
    page: int | None


def read_state(
    service: str | None = None, *, bus: SessionBus | None = None
) -> OkularState:
    """Consulta el objeto /okular; requiere un solo documento/ventana por servicio.

    No identifica la vista activa ni calcula índices o etiquetas del PDF.
    """
    bus = bus if bus is not None else SessionBus()
    selected = select_service(bus.list_services(), service)
    xml = cast(
        str,
        bus.call(
            selected,
            OBJECT_PATH,
            "org.freedesktop.DBus.Introspectable",
            "Introspect",
            "s",
        ),
    )
    verify_interface(xml)
    document = cast(
        str, bus.call(selected, OBJECT_PATH, INTERFACE, "currentDocument", "s")
    )
    page = cast(int, bus.call(selected, OBJECT_PATH, INTERFACE, "currentPage", "u"))
    # Sin documento, el número devuelto por el visor carece de contexto.
    return OkularState(
        selected,
        document or None,
        local_path(document) if document else None,
        page if document else None,
    )
