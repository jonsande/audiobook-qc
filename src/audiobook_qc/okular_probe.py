"""CLI de consulta puntual a una instancia existente de Okular."""

import argparse
import sys

from audiobook_qc.integrations.okular import (
    OBJECT_PATH,
    OkularError,
    OkularState,
    SessionBus,
    read_state,
)


def format_state(state: OkularState) -> str:
    missing = "no disponible"
    lines = [
        "Estado de Okular",
        f"Servicio: {state.service}",
        f"Objeto: {OBJECT_PATH}",
        f"Documento: {state.document if state.document is not None else missing}",
    ]
    if state.path is not None:
        lines.append(f"Ruta local: {state.path}")
    lines.append(f"Página (D-Bus): {state.page if state.page is not None else missing}")
    lines.append(
        "Se muestra el valor nativo; no se calcula índice ni numeración impresa."
    )
    lines.append(
        "La vista activa no se identifica; usa una sola ventana/documento por servicio."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consulta de Okular por D-Bus de sesión."
    )
    parser.add_argument(
        "--service", help="Servicio explícito cuando hay varios Okular."
    )
    parser.add_argument(
        "--list-services", action="store_true", help="Lista los servicios."
    )
    args = parser.parse_args(argv)
    try:
        if args.list_services:
            services = SessionBus().list_services()
            print("\n".join(services) if services else "No hay servicios de Okular.")
        else:
            print(format_state(read_state(args.service)))
    except OkularError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
