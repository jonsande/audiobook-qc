"""Instalación, consulta y validación de tipos/atajos configurables."""

import argparse
import json
import sys
from dataclasses import asdict

from audiobook_qc.type_config import (
    install_initial_types,
    load_types,
    types_data,
    types_path,
)


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    commands = parser.add_subparsers(dest="action", required=True)
    for name in ("init", "list", "validate", "hotkeys"):
        commands.add_parser(name, parents=[common])
    commands.add_parser("get", parents=[common]).add_argument("id")
    args = parser.parse_args(argv)
    try:
        if args.action == "init":
            install_initial_types()
        catalog = load_types()
        result = {"configuration": str(types_path()), "version": 1}
        if args.action in ("list", "init"):
            result.update(types_data(catalog))
        elif args.action == "get":
            result["type"] = asdict(catalog.get(args.id))
        elif args.action == "hotkeys":
            result["hotkeys"] = dict(catalog.hotkeys)
        else:
            result.update(valid=True, count=len(catalog.types))
    except (ValueError, OSError) as exc:
        print(f"Error de tipos: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    else:
        print(f"Configuración: {result['configuration']}")
        if "types" in result or "type" in result:
            print("ID | Nombre | Habilitado | Fórmula predeterminada")
            for item in result.get("types", [result.get("type")]):
                formula = json.dumps(
                    item["default_generic_description"], ensure_ascii=False
                )
                print(
                    f"{item['id']} | {item['label']} | "
                    f"{'sí' if item['enabled'] else 'no'} | "
                    f"{formula}"
                )
        if "hotkeys" in result:
            for key, identifier in result["hotkeys"].items():
                print(f"{key} → {identifier or 'sin asignación'}")
        if result.get("valid"):
            print(f"Configuración válida ({result['count']} tipos).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
