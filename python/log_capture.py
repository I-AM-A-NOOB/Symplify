# coding: utf-8
"""Routes what the interpreter and Qt say into the app's own log.

Qt's warnings and uncaught Python exceptions are invisible in a packaged build:
a windowed exe has no console at all (``--windows-console-mode=disable``), and
even in development they are the one stream the Log page never showed. That is
the stream that carries RinUI's own complaints — a QML ``ReferenceError`` per
component instantiation, type errors from dialogs — so the app looked healthy
while its console filled up.

This module hands that stream to the :class:`LogViewModel`, which is also where
the app's own entries (Calculator, Variables) go, and which keeps them to itself:
the page is the destination for both, and nothing is written to the terminal, so
the two cannot drift apart.

Two details the handlers have to get right:

* **Re-entrancy.** The Qt handler runs while Qt is printing, and it ends in a
  signal emission that can make Qt print again. A flag drops the nested call.
* **Repeats.** RinUI emits the same warning once per instantiation; left alone
  they bury everything else, so the viewmodel collapses consecutive identical
  entries into one line with a count.
"""

import sys
import traceback
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Optional, Type

from .viewmodel.log_viewmodel import LogLevel, LogViewModel

if TYPE_CHECKING:                      # Qt is imported for typing only
    from PySide6.QtCore import QMessageLogContext, QtMsgType

#: Guards the Qt handler against re-entering itself through a signal emission.
_in_handler = False


def install(sink: LogViewModel) -> None:
    """Send Qt messages and uncaught exceptions to ``sink``.

    Args:
        sink: The log viewmodel, which owns the entries from here on.
    """
    _install_message_handler(sink)
    _install_excepthook(sink)


def _install_message_handler(sink: LogViewModel) -> None:
    """Take over Qt's message output."""
    from PySide6.QtCore import qInstallMessageHandler

    def handler(
        msg_type: "QtMsgType",
        context: "QMessageLogContext",
        message: str,
    ) -> None:
        global _in_handler
        if _in_handler:
            return
        _in_handler = True
        try:
            where = ""
            file = getattr(context, "file", None)
            if file:
                where = f"{Path(file).name}:{context.line}: "
            sink.add_log(
                where + message.strip(),
                level=_level_for(msg_type),
                source="Qt",
            )
        finally:
            _in_handler = False

    # The previous handler is of no use to us: this app owns its output.
    _ = qInstallMessageHandler(handler)


def _level_for(msg_type: "QtMsgType") -> LogLevel:
    """Map a Qt message type onto a log level."""
    from PySide6.QtCore import QtMsgType

    if msg_type == QtMsgType.QtDebugMsg:
        return LogLevel.DEBUG
    if msg_type == QtMsgType.QtInfoMsg:
        return LogLevel.INFO
    if msg_type == QtMsgType.QtWarningMsg:
        return LogLevel.WARNING
    return LogLevel.ERROR          # QtCriticalMsg, QtFatalMsg


def _install_excepthook(sink: LogViewModel) -> None:
    """Report uncaught exceptions, keeping Python's own reporting intact."""
    previous = sys.excepthook

    def hook(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_tb: Optional[TracebackType],
    ) -> None:
        text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        ).rstrip()
        sink.add_log(text, level=LogLevel.ERROR, source="Python")
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook
