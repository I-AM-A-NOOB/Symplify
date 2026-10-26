"""The LaTeX renderer's child process (zero Qt).

`LatexRenderService` starts this module with ``spawn`` and talks to it over a
pickled duplex pipe. Rendering runs here so ziamath's process-global font
caches are not shared with the UI, and so a renderer crash cannot take the
application down.

Protocol: (token, latex, style, owner_index, generation) in;
(("skipped", token) | ("ok", token, url, width, height, warnings)
 | ("error", token, message, warnings)) out. ``generation`` is read from the
shared array before each job so queued stale work is skipped.
"""

import warnings
from typing import Any

from .latex_render import render_data_url


def render_worker_main(connection: Any, generations: Any) -> None:
    """Serve render requests until the parent closes the pipe or sends None."""
    try:
        while True:
            try:
                request = connection.recv()
            except (EOFError, OSError):
                return
            if request is None:
                return

            token, latex, style, owner, generation = request
            if int(generations[owner]) != generation:
                try:
                    connection.send(("skipped", token))
                except (BrokenPipeError, EOFError, OSError):
                    return
                continue

            messages = []
            result = None
            error = ""
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    result = render_data_url(latex, style)
                except Exception as exc:  # noqa: BLE001 - report, never escape
                    error = f"{type(exc).__name__}: {exc}"
            for item in caught:
                messages.append(f"{item.category.__name__}: {item.message}")

            try:
                if result is None:
                    connection.send(("error", token, error, messages))
                else:
                    url, width, height = result
                    connection.send(
                        ("ok", token, url, width, height, messages)
                    )
            except (BrokenPipeError, EOFError, OSError):
                return
    finally:
        try:
            connection.close()
        except OSError:
            pass
