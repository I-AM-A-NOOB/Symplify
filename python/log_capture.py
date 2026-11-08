"""Routes Qt, Python ``logging`` and the interpreter's warnings into the log page.

Three streams feed one sink (the log viewmodel):

* **Python ``logging``** — the standard channel, and since RinUI 0.5 the one RinUI
  itself uses (``RinUI.core.logger``; silent until a handler is attached). A
  handler on the root logger forwards records to the page. This is also the
  channel for anything else in the process that logs: ziamath, fontTools, SymPy.
* **Qt's message handler** — QML warnings and Qt's own complaints are re-emitted
  as records on the ``Qt`` logger, so both streams share one formatting and one
  destination. The ``Qt`` logger is pinned to DEBUG: Qt decides what is worth
  reporting, and its info/debug messages were shown before this bridge existed.
* **``sys.excepthook`` and ``warnings``** — an uncaught exception is an ``ERROR``
  record on the ``Python`` logger; ``warnings`` go through
  ``logging.captureWarnings``, which is what reaches deep library warnings in a
  windowed build (it has no console).

**One duplicate has to be filtered.** RinUI logs each QML warning on its own
logger as ``QML: …``; the same warning also arrives through Qt's message handler.
The bridge drops the RinUI copy, so one warning is one line rather than two.

**Entries are queued onto the sink's thread.** A record can be emitted from any
thread (Qt calls its message handler from the QML compilation thread too), while
the viewmodel is a QObject owned by the GUI thread. ``QMetaObject.invokeMethod``
with ``Qt.QueuedConnection`` is the hand-off; it also keeps the handler free of
the viewmodel's own signals, which is what made a re-entering Qt handler
possible before.

**Nothing here may raise**, and nothing may keep running during teardown. Qt
keeps printing while the interpreter tears its modules down; the sink is destroyed
in the same sweep. The bridge detaches on ``aboutToQuit`` — it removes the logging
handler, restores Qt's own handler, stops warning capture and puts the previous
excepthook back — and every entry point checks the shutdown flag.
"""

import logging
import sys
import traceback
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

from .viewmodel.log_viewmodel import LogLevel, LogViewModel

if TYPE_CHECKING:                      # Qt is imported for typing only
    from PySide6.QtCore import QMessageLogContext, QtMsgType

#: The handler installed on the root logger, so teardown can remove it again.
_handler: "logging.Handler | None" = None

#: The excepthook this module replaced, restored on quit.
_previous_excepthook = sys.excepthook

#: Set once the application is quitting. Qt prints during teardown, after the
#: viewmodels the sink belongs to have been destroyed.
_shutting_down = False

#: Guards the Qt handler against re-entering itself if Qt complains while it runs.
_in_qt_handler = False


def install(sink: LogViewModel) -> None:
    """Send Qt, ``logging`` and the interpreter's messages to ``sink``.

    Args:
        sink: The log viewmodel, which owns the entries from here on.
    """
    global _handler, _shutting_down
    if _handler is not None:
        return
    _shutting_down = False
    sink.entryAdded.connect(_mirror_to_terminal)

    _handler = _ViewModelHandler(sink)
    logging.getLogger().addHandler(_handler)
    #: Qt's own debug/info messages were visible before this bridge; keep them.
    logging.getLogger("Qt").setLevel(logging.DEBUG)

    _install_message_handler()
    _install_excepthook()
    logging.captureWarnings(True)
    _detach_at_quit()


class _ViewModelHandler(logging.Handler):
    """Forward records into the log viewmodel on its own thread."""

    def __init__(self, sink: LogViewModel):
        super().__init__(logging.DEBUG)
        self._sink: LogViewModel = sink

    def emit(self, record: logging.LogRecord) -> None:
        """Hand one record to the viewmodel, or drop it at teardown."""
        if _shutting_down:
            return
        try:
            message = record.getMessage()
            #: RinUI logs every QML warning itself; the same warning already
            #: came through Qt. See the module docstring.
            if record.name == "RinUI" and message.startswith("QML: "):
                return
            if record.exc_info:
                message = (message + "\n" + "".join(
                    traceback.format_exception(*record.exc_info)
                )).strip()

            from PySide6.QtCore import Q_ARG, QMetaObject, Qt

            QMetaObject.invokeMethod(
                self._sink,
                "add_record",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, message),
                Q_ARG(int, _level_for_record(record.levelno).value),
                Q_ARG(str, _source_for(record)),
            )
        except Exception:
            # Teardown, or a record from a thread the sink cannot reach: a log
            # line must never take the process with it.
            self.handleError(record)


def _level_for_record(levelno: int) -> LogLevel:
    """Map a Python logging level onto the page's four levels."""
    if levelno >= logging.ERROR:
        return LogLevel.ERROR
    if levelno >= logging.WARNING:
        return LogLevel.WARNING
    if levelno >= logging.INFO:
        return LogLevel.INFO
    return LogLevel.DEBUG


def _source_for(record: logging.LogRecord) -> str:
    """The tag the page shows in brackets: short, and never a dotted path."""
    if record.name == "py.warnings":
        return "Warnings"
    return record.name.rsplit(".", 1)[-1]


def _detach_at_quit() -> None:
    """Stop routing once the application is quitting.

    Qt's output and the interpreter's teardown overlap: RinUI's event filter keeps
    running while modules are being destroyed, and the log viewmodel is one of
    them. Anything routed then would reach a deleted QObject and raise inside Qt,
    which prints that as a nest of "Error calling Python override" frames.
    Detaching first turns all of it back into ordinary output.
    """
    def detach() -> None:
        global _shutting_down, _handler
        _shutting_down = True
        try:
            from PySide6.QtCore import qInstallMessageHandler

            qInstallMessageHandler(None)
        except Exception:              # Qt already gone: nothing left to restore
            pass
        try:
            logging.captureWarnings(False)
        except Exception:
            pass
        if _handler is not None:
            logging.getLogger().removeHandler(_handler)
            _handler.close()
            _handler = None
        sys.excepthook = _previous_excepthook

    try:
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(detach)
    except Exception:                  # no Qt (tests importing the model layer)
        pass


def _mirror_to_terminal(level: str, source: str, message: str) -> None:
    """Print one entry to the process's own streams, as the page shows it.

    Written through ``sys.__stdout__``/``sys.__stderr__`` — the streams the
    interpreter started with — and flushed, because a redirected stream is
    block-buffered and a developer watching a file wants the line now.
    """
    stream = sys.__stderr__ if level in ("WARNING", "ERROR") else sys.__stdout__
    if stream is None:                 # a windowed build may have none
        return
    try:
        print(f"[{level}] {source}: {message}", file=stream, flush=True)
    except Exception:                  # never let logging break the app
        pass


def _install_message_handler() -> None:
    """Turn Qt's message output into ``Qt`` logger records."""
    from PySide6.QtCore import qInstallMessageHandler

    def handler(
        msg_type: "QtMsgType",
        context: "QMessageLogContext",
        message: str,
    ) -> None:
        global _in_qt_handler
        if _in_qt_handler or _shutting_down:
            return
        _in_qt_handler = True
        try:
            where = ""
            file = getattr(context, "file", None)
            if file:
                where = f"{Path(file).name}:{getattr(context, 'line', 0)}: "
            logging.getLogger("Qt").log(
                _python_level_for(msg_type), where + message.strip()
            )
        except Exception:
            # The sink is gone or Qt is mid-teardown: a message must never raise
            # out of the handler, least of all into Qt's own printing.
            pass
        finally:
            _in_qt_handler = False

    # The previous handler is of no use to us: this app owns its output.
    _ = qInstallMessageHandler(handler)


def _python_level_for(msg_type: "QtMsgType") -> int:
    """Map a Qt message type onto a Python logging level."""
    from PySide6.QtCore import QtMsgType

    if msg_type == QtMsgType.QtDebugMsg:
        return logging.DEBUG
    if msg_type == QtMsgType.QtInfoMsg:
        return logging.INFO
    if msg_type == QtMsgType.QtWarningMsg:
        return logging.WARNING
    return logging.ERROR          # QtCriticalMsg, QtFatalMsg


def _install_excepthook() -> None:
    """Report uncaught exceptions on the ``Python`` logger."""
    global _previous_excepthook
    _previous_excepthook = sys.excepthook

    def hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        if _shutting_down:
            return
        text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        ).rstrip()
        # No `previous(...)`: the entry itself is mirrored to stderr now, so
        # calling the default hook would print the same traceback twice.
        try:
            logging.getLogger("Python").error(text)
        except Exception:              # as in the Qt handler: teardown is not ours
            pass

    sys.excepthook = hook
