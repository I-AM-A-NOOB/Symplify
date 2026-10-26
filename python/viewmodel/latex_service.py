"""Asynchronous LaTeX -> SVG rendering in a disposable process.

Rendering is pure Python (ziamath) but it is not cheap, and doing it on the UI
thread delayed the result text. The service owns one renderer process and a
bounded cache:

* A result, variant row or history card is requested by token. The caller can
  apply the result text immediately and fill the artwork when ``rendered``
  arrives.
* A style change or a new result starts a new generation for that owner. Queued
  jobs from the old generation are skipped by the renderer, so a burst of
  calculations cannot leave stale work ahead of the current one.
* With no ``QCoreApplication`` (the headless model tests) requests render inline
  and emit synchronously. That keeps the viewmodel deterministic without a
  process or an event loop.
* The renderer is a process rather than a thread: ziamath is Python and its
  font caches are process-global, and a renderer crash must not take the UI
  process down. The pipe is the only boundary.
"""

import multiprocessing
import threading
import warnings
from collections import OrderedDict
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

from ..latex_render import LatexStyle, render_data_url
from ..latex_render_worker import render_worker_main

#: Two consumers share one renderer process. The order is the index used by
#: the shared generation array; never reorder without changing both sides.
OWNER_CALCULATOR = 0
OWNER_HISTORY = 1
_OWNER_INDEX = {"calculator": OWNER_CALCULATOR, "history": OWNER_HISTORY}

#: A full SVG data URL can be large (MAX_LATEX_CHARS caps one image, not the
#: number of results). Keep the hot entries; history items retain their own URL.
MAX_CACHE_ENTRIES = 32

_CacheValue = tuple[str, int, int]


class LatexRenderService(QObject):
    """One renderer process, a bounded cache, and tokenized completions."""

    rendered = Signal(str, str, int, int)  # token, data URL, width, height
    failed = Signal(str, str)              # token, message
    warning = Signal(str)                  # renderer warning, on the UI thread

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._cache: OrderedDict[tuple[str, LatexStyle], _CacheValue] = (
            OrderedDict()
        )
        #: token -> (cache key, owner index)
        self._pending: dict[str, tuple[tuple[str, LatexStyle], int]] = {}
        self._generations = {"calculator": 0, "history": 0}
        self._generation_lock = threading.Lock()
        self._context = multiprocessing.get_context("spawn")
        self._process: Any = None
        self._connection: Any = None
        self._shared_generations: Any = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2)
        self._poll_timer.timeout.connect(self._poll)

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    # -- public API --------------------------------------------------------

    def begin_generation(self, owner: str = "calculator") -> int:
        """Invalidate queued work for one owner without blocking on it.

        A result change or a style change means any queued render for that
        owner is obsolete. The renderer checks the shared generation before
        starting a job, so stale jobs are skipped instead of rendering behind
        the current one.
        """
        index = _OWNER_INDEX.get(owner, OWNER_CALCULATOR)
        with self._generation_lock:
            self._generations[owner] = self._generations.get(owner, 0) + 1
            value = self._generations[owner]
            if self._shared_generations is not None:
                self._shared_generations[index] = value
        for token, (_, pending_owner) in list(self._pending.items()):
            if pending_owner == index:
                self._pending.pop(token, None)
        if not self._pending:
            self._poll_timer.stop()
        return value

    def request(
        self,
        token: str,
        latex: str,
        style: LatexStyle,
        owner: str = "calculator",
    ) -> None:
        """Render ``latex`` and report it under ``token``.

        A cache hit is delivered before this method returns, on the calling
        thread. The caller registers the token before calling, so both the
        inline and the cache-hit paths are safe to handle synchronously.
        """
        key = (latex, style)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            self.rendered.emit(token, *cached)
            return

        if QCoreApplication.instance() is None:
            self._render_inline(token, key)
            return

        index = _OWNER_INDEX.get(owner, OWNER_CALCULATOR)
        with self._generation_lock:
            generation = self._generations.get(owner, 0)
        self._pending[token] = (key, index)
        try:
            self._ensure_worker()
            connection = self._connection
            if connection is None:
                raise RuntimeError("the LaTeX renderer is not running")
            connection.send((token, latex, style, index, generation))
        except Exception as exc:  # noqa: BLE001 - a renderer start/send failure
            self._pending.pop(token, None)
            self.failed.emit(token, f"{type(exc).__name__}: {exc}")
            return
        self._poll_timer.start()

    def warm_up(self) -> None:
        """Start the renderer before the first result, hiding its imports."""
        if QCoreApplication.instance() is None:
            return
        try:
            self._ensure_worker()
        except Exception:  # noqa: BLE001 - warm-up is optional
            self._terminate_worker()

    def shutdown(self) -> None:
        """Stop the renderer and drop pending work (application exit)."""
        self._poll_timer.stop()
        self._pending.clear()
        self._terminate_worker()

    # -- renderer process --------------------------------------------------

    def _ensure_worker(self) -> None:
        if (self._process is not None
                and self._process.is_alive()
                and self._connection is not None):
            return
        self._terminate_worker()
        parent, child = self._context.Pipe()
        shared = self._context.Array(
            "i", [self._generations["calculator"], self._generations["history"]]
        )
        process = self._context.Process(
            target=render_worker_main,
            args=(child, shared),
            daemon=True,
        )
        process.start()
        child.close()
        self._process = process
        self._connection = parent
        self._shared_generations = shared

    def _terminate_worker(self) -> None:
        """Stop and reap the child; safe to call when there is none."""
        connection, process = self._connection, self._process
        self._connection = None
        self._process = None
        self._shared_generations = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        if process is None:
            return
        if process.is_alive():
            process.terminate()
        process.join(0.3)
        if process.is_alive():
            process.kill()
            process.join(0.3)

    def _poll(self) -> None:
        """Read one renderer response, or notice that the child died."""
        if not self._pending:
            self._poll_timer.stop()
            return
        connection = self._connection
        if connection is None:
            self._renderer_stopped("the LaTeX renderer is not running")
            return
        try:
            if not connection.poll(0):
                return
            response = connection.recv()
        except (EOFError, OSError) as exc:
            self._renderer_stopped(f"the LaTeX renderer stopped ({exc})")
            return

        kind = response[0]
        token = response[1]
        if kind == "skipped":
            self._pending.pop(token, None)
        elif kind == "ok":
            _, token, url, width, height, messages = response
            pending = self._pending.pop(token, None)
            if pending is not None:
                key, _ = pending
                self._store(key, (url, width, height))
                for message in messages:
                    self.warning.emit(message)
                self.rendered.emit(token, url, width, height)
        elif kind == "error":
            _, token, message, messages = response
            pending = self._pending.pop(token, None)
            if pending is not None:
                for warning_message in messages:
                    self.warning.emit(warning_message)
                self.failed.emit(token, message)
        if not self._pending:
            self._poll_timer.stop()

    def _renderer_stopped(self, message: str) -> None:
        """Fail pending tokens once, then let the next request restart."""
        tokens = list(self._pending)
        self._pending.clear()
        self._poll_timer.stop()
        self.warning.emit(message)
        for token in tokens:
            self.failed.emit(token, message)
        self._terminate_worker()

    # -- inline fallback ---------------------------------------------------

    def _render_inline(
        self, token: str, key: tuple[str, LatexStyle]
    ) -> None:
        """Headless path: render now and notify synchronously."""
        messages = []
        result = None
        error = ""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                result = render_data_url(*key)
            except Exception as exc:  # noqa: BLE001 - a render failure is a signal
                error = f"{type(exc).__name__}: {exc}"
        for item in caught:
            messages.append(f"{item.category.__name__}: {item.message}")
        for message in messages:
            self.warning.emit(message)
        if result is None:
            self.failed.emit(token, error)
            return
        self._store(key, result)
        self.rendered.emit(token, *result)

    def _store(self, key: tuple[str, LatexStyle], value: _CacheValue) -> None:
        """Insert into a bounded LRU cache."""
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > MAX_CACHE_ENTRIES:
            self._cache.popitem(last=False)
