"""CLI de observación de PRIMARY o CLIPBOARD sin copiar texto ni detectar foco."""

import argparse
import sys

from audiobook_qc.integrations.selection import (
    Selection,
    SelectionError,
    SelectionUnavailableError,
    read_selection,
)


def format_selection(selection: Selection) -> str:
    state = "texto disponible" if selection.text else "vacía"
    return "\n".join(
        (
            f"Selección X11: {selection.name.upper()}",
            f"Estado: {state}",
            f"Caracteres: {len(selection.text)}",
            "Texto:",
            f"«{selection.text}»",
            f"Representación exacta: {selection.text!r}",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lee una selección de texto global X11."
    )
    parser.add_argument(
        "--selection", choices=("primary", "clipboard"), default="primary"
    )
    args = parser.parse_args(argv)
    try:
        selection = read_selection(args.selection)
    except SelectionUnavailableError as exc:
        print(f"Selección no disponible: {exc}", file=sys.stderr)
        return 2
    except SelectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(format_selection(selection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
