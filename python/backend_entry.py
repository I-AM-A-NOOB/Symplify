"""The spawn target for the calculation worker (zero imports of its own).

``multiprocessing`` imports the target's module in the *parent* as well as the
child. Importing :mod:`python.backend_worker` there would load SymPy into the UI
process, so the parent imports this thin function instead; the real worker is
imported only inside the spawned child.
"""

from __future__ import annotations

from typing import Any


def worker_main(connection: Any) -> None:
    """Run the calculation worker in this (child) process."""
    from .backend_worker import worker_main as run

    run(connection)
