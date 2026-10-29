"""Exclusión local de activaciones de escritorio, independiente del dominio."""

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class ActivationBusy(Exception):
    """Otra activación del mismo archivo SQLite sigue en curso."""


@contextmanager
def activation_guard(database: str) -> Iterator[None]:
    """Rechaza solapamientos sin encolar una captura que leería contexto tardío.

    El archivo permanece al terminar: eliminarlo permitiría bloquear inodos
    distintos. El sistema libera flock incluso si el proceso muere.
    """
    path = Path(database).resolve()
    with path.with_name(path.name + ".capture.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ActivationBusy(
                "Captura en curso para esta base; esta activación se ha omitido."
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
