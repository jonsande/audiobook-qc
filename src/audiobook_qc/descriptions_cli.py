"""Consulta humana/JSON y validación explícita del catálogo global."""

import argparse
import json
import sys
from dataclasses import asdict

from audiobook_qc.description_config import catalog_path, load_catalog
from audiobook_qc.descriptions import CatalogError
from audiobook_qc.type_config import load_types


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    commands = parser.add_subparsers(dest="action", required=True)
    listing = commands.add_parser("list", parents=[common])
    listing.add_argument("type", nargs="?")
    commands.add_parser("validate", parents=[common])
    args = parser.parse_args(argv)
    try:
        path = catalog_path()
        types = load_types()
        catalog = load_catalog(path, types=types)
        result = {"catalog": str(path), "version": 1}
        if args.action == "list":
            code = types.get(args.type).id if args.type else None
            result["descriptions"] = [asdict(item) for item in catalog.list(code)]
        else:
            result.update(valid=True, count=len(catalog.descriptions))
    except (CatalogError, ValueError) as exc:
        print(f"Error de descripciones: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    elif args.action == "validate":
        print(f"Catálogo válido: {path} ({result['count']} descripciones).")
    else:
        print(f"Catálogo: {path}\nID | Texto | Tipos")
        for item in result["descriptions"]:
            print(
                f"{item['id']} | {json.dumps(item['text'], ensure_ascii=False)} | "
                + ", ".join(item["incident_types"])
            )
        if not result["descriptions"]:
            print("Sin descripciones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
