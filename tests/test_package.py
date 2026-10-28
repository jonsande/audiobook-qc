"""Comprobaciones mínimas de instalación e importación del paquete."""

from importlib.metadata import version

import audiobook_qc


def test_installed_package_version_matches_public_version() -> None:
    assert version("audiobook-qc") == audiobook_qc.__version__
