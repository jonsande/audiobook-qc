"""Resolución exacta por documento de las vistas D-Bus de Okular.

No selecciona por foco, PID ni orden. El nombre único de conexión fija al dueño
para toda la captura; las rutas de objetos se redescubren tras cada reapertura.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from audiobook_qc.integrations.okular import (
    INTERFACE,
    OkularError,
    OkularState,
    SessionBus,
    local_path,
    verify_interface,
)

DBUS = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
INTROSPECT = "org.freedesktop.DBus.Introspectable"


class DocumentNotOpen(OkularError):
    """Ninguna vista publicada corresponde al documento explícito del trabajo."""


def _matches(document: str, expected: Path) -> bool:
    path = local_path(document)
    try:
        return path is not None and path.resolve() == expected
    except (OSError, ValueError, RuntimeError) as exc:
        raise OkularError(
            f"No se pudo verificar la identidad del documento: {exc}"
        ) from exc


@dataclass(frozen=True)
class BoundDocument:
    owner: str
    object_path: str
    document: Path
    bus: SessionBus

    def read_state(self) -> OkularState:
        xml = cast(
            str,
            self.bus.call(self.owner, self.object_path, INTROSPECT, "Introspect", "s"),
        )
        verify_interface(xml)
        before = cast(
            str,
            self.bus.call(
                self.owner, self.object_path, INTERFACE, "currentDocument", "s"
            ),
        )
        page = cast(
            int,
            self.bus.call(self.owner, self.object_path, INTERFACE, "currentPage", "u"),
        )
        after = cast(
            str,
            self.bus.call(
                self.owner, self.object_path, INTERFACE, "currentDocument", "s"
            ),
        )
        if before != after or not _matches(before, self.document):
            raise OkularError("El documento de la vista cambió; captura rechazada.")
        return OkularState(self.owner, before, local_path(before), page)


def resolve_document(document: Path, *, bus: SessionBus | None = None) -> BoundDocument:
    """Exige una única vista exacta entre todos los objetos de todos los dueños.

    Si no puede inspeccionarse un servicio no se descarta silenciosamente: podría
    ocultar otra vista del mismo documento. APIs desconocidas se rechazan.
    """
    bus = bus if bus is not None else SessionBus()
    services = bus.list_services()
    if len(services) > 64:
        raise OkularError("Demasiados servicios Okular para resolver sin ambigüedad.")
    candidates = []
    owners = set()
    for service in services:
        owner = cast(
            str, bus.call(DBUS, DBUS_PATH, DBUS, "GetNameOwner", "s", "s", service)
        )
        if not re.fullmatch(r":[0-9]+\.[0-9]+", owner):
            raise OkularError("Dueño D-Bus inválido.")
        if owner in owners:
            continue
        owners.add(owner)
        xml = cast(str, bus.call(owner, "/", INTROSPECT, "Introspect", "s"))
        try:
            nodes = ET.fromstring(xml).findall("node")
        except ET.ParseError as exc:
            raise OkularError("Introspección de vistas inválida.") from exc
        paths = [
            "/" + node.get("name", "")
            for node in nodes
            if re.fullmatch(r"okular(?:[0-9]+)?", node.get("name", ""))
        ]
        if not paths or len(paths) > 64 or len(set(paths)) != len(paths):
            raise OkularError("No se puede enumerar inequívocamente las vistas Okular.")
        for path in paths:
            view = BoundDocument(owner, path, document, bus)
            # Verificar la interfaz incluso para las vistas que no coinciden.
            interface = cast(str, bus.call(owner, path, INTROSPECT, "Introspect", "s"))
            verify_interface(interface)
            current = cast(
                str, bus.call(owner, path, INTERFACE, "currentDocument", "s")
            )
            if _matches(current, document):
                candidates.append(view)
    if not candidates:
        raise DocumentNotOpen(f"Abre en Okular el documento asociado: {document}.")
    if len(candidates) != 1:
        raise OkularError("PDF abierto en varias vistas; cierra las copias ambiguas.")
    view = candidates[0]
    view.read_state()
    return view
