"""One consumer's side of the shared LaTeX renderer.

A consumer of the renderer hands over a *target* (its own row, or a kind) and
gets the target back with the artwork; it never sees a token string. The token
counter, the pending map and the generation handshake are identical for every
consumer, so they live here instead of once in the calculator and once in the
history.

Generation policy is the caller's: :meth:`reset` invalidates every queued render
for this owner, which is what a new result or a style change needs.
"""

from typing import Any

from PySide6.QtCore import QObject, Signal

from ..latex_render import LatexStyle
from .latex_service import LatexRenderService


class LatexJobs(QObject):
    """Tokenized render requests for one owner.

    Signals:
        rendered: A target's artwork is ready (target, data URL, width, height).
        failed: A target's render failed (target, message).
    """

    rendered = Signal(object, str, int, int)
    failed = Signal(object, str)

    def __init__(
        self,
        service: LatexRenderService,
        owner: str,
        parent: QObject | None = None,
    ) -> None:
        """Attach to ``service`` and start collecting for ``owner``."""
        super().__init__(parent)
        self._service = service
        self._owner = owner
        #: token -> the consumer's target (a row's item, or a kind tuple).
        self._pending: dict[str, Any] = {}
        self._seq = 0
        service.rendered.connect(self._on_rendered)
        service.failed.connect(self._on_failed)

    @property
    def owner(self) -> str:
        """The generation channel this bookkeeping invalidates."""
        return self._owner

    def reset(self) -> None:
        """Forget every pending target and invalidate queued work for the owner."""
        self._service.begin_generation(self._owner)
        self._pending.clear()

    def request(self, target: Any, latex: str, style: LatexStyle) -> None:
        """Ask for ``latex`` and report it back as ``target``."""
        self._seq += 1
        token = f"{self._seq}:{self._owner}"
        self._pending[token] = target
        self._service.request(token, latex, style, owner=self._owner)

    def _on_rendered(self, token: str, url: str, width: int, height: int) -> None:
        target = self._pending.pop(token, None)
        if target is not None:
            self.rendered.emit(target, url, width, height)

    def _on_failed(self, token: str, message: str) -> None:
        target = self._pending.pop(token, None)
        if target is not None:
            self.failed.emit(target, message)
