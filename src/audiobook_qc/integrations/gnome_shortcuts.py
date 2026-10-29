"""Lectura de atajos y escritura exclusiva de binding mediante GSettings."""

import ast
import re
import shlex
import subprocess
from dataclasses import dataclass, replace

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = SCHEMA + ".custom-keybinding:"
PATH_PATTERN = re.compile(
    r"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/[A-Za-z0-9_-]+/"
)


class ShortcutError(Exception):
    """No se puede sincronizar de forma segura la configuración de atajos."""


@dataclass(frozen=True)
class Shortcut:
    path: str
    name: str
    command: str
    binding: str

    @property
    def owned(self) -> bool:
        try:
            arguments = shlex.split(self.command)
        except ValueError:
            return False
        return (
            len(arguments) >= 4
            and re.fullmatch(r"python[0-9.]*", arguments[0].rsplit("/", 1)[-1])
            is not None
            and arguments[1:3] == ["-m", "audiobook_qc.capture_save_probe"]
            and "--desktop" in arguments[3:]
        )


class GSettingsShortcuts:
    def _run(self, *arguments: str) -> str:
        try:
            result = subprocess.run(
                ["gsettings", *arguments],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
            raise ShortcutError(f"No se pudo ejecutar GSettings: {exc}") from exc
        if result.returncode or result.stderr.strip():
            raise ShortcutError(
                f"GSettings falló: {result.stderr.strip() or result.returncode}"
            )
        return result.stdout.strip()

    def _get(self, schema: str, key: str):
        text = self._run("get", schema, key).removeprefix("@as ")
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise ShortcutError("Respuesta GSettings no reconocida.") from exc

    def paths(self) -> list[str]:
        paths = self._get(SCHEMA, "custom-keybindings")
        if (
            not isinstance(paths, list)
            or any(
                not isinstance(path, str) or not PATH_PATTERN.fullmatch(path)
                for path in paths
            )
            or len(set(paths)) != len(paths)
        ):
            raise ShortcutError("Lista de atajos inválida o ambigua.")
        return paths

    def read(self, path: str) -> Shortcut:
        if not PATH_PATTERN.fullmatch(path):
            raise ShortcutError("Ruta de atajo no reconocida.")
        values = [
            self._get(CUSTOM_SCHEMA + path, key)
            for key in ("name", "command", "binding")
        ]
        if any(not isinstance(value, str) for value in values):
            raise ShortcutError("Propiedades de atajo inválidas.")
        return Shortcut(path, *values)

    def write_binding(self, expected: Shortcut, binding: str) -> None:
        if (
            not expected.owned
            or expected.path not in self.paths()
            or self.read(expected.path) != expected
        ):
            raise ShortcutError(
                "El atajo cambió o dejó de pertenecer al proyecto; no se sobrescribe."
            )
        # Solo se modifica binding: nunca command, name ni custom-keybindings.
        self._run("set", CUSTOM_SCHEMA + expected.path, "binding", repr(binding))
        if self.read(expected.path) != replace(expected, binding=binding):
            raise ShortcutError("No se pudo confirmar la escritura de binding.")
