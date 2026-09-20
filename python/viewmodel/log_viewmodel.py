# coding: utf-8
"""Log viewmodel: one list of entries, rendered twice for the page.

Entries are formatted twice from the same list — a plain string for the Copy
button and the "is it empty" test, and a rich-text string the page renders, so a
level is visible at a glance. Both are rebuilt whenever the list changes; the
list is capped at :data:`MAX_ENTRIES`, which keeps that cheap and stops a chatty
Qt message from growing the page forever.

Consecutive identical entries collapse into one line with a count. RinUI emits
the same warning once per component instantiation, and without this the log was
mostly that one line.

**The colours are pushed in from QML** (``MainWindow.qml``, which owns the theme
wiring) rather than resolved here: they are RinUI theme roles, and QML is where
the theme lives. Entries that arrive before the window exists — Qt complains
during engine setup — render without colour and are re-rendered when the colours
land.

**Nothing here writes to the terminal.** The page is the destination for both
streams: Qt's messages are taken off the console by :mod:`python.log_capture`, so
echoing the app's own entries there would leave the two out of step rather than
in step.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from html import escape

from PySide6.QtCore import Property, QObject, Signal, Slot

#: How many entries are kept (and rendered). Older ones fall off the front.
MAX_ENTRIES = 1000


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


#: Levels whose message is tinted too, not just their level tag.
_LOUD = (LogLevel.WARNING, LogLevel.ERROR)


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: datetime
    level: LogLevel
    message: str
    source: str
    repeat: int = 1


class LogViewModel(QObject):
    """Collects and formats application logs for display."""

    formattedLogsChanged = Signal()
    richLogsChanged = Signal()
    colorsChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        """Initialize the log viewmodel."""
        super().__init__(parent)
        self._logs: deque[LogEntry] = deque(maxlen=MAX_ENTRIES)
        self._formatted = ""
        self._rich = ""
        self._colors: dict[str, str] = {}

    # -- properties --------------------------------------------------------

    def _get_formatted_logs(self) -> str:
        """The plain text, for copying and for the empty test."""
        return self._formatted

    formattedLogs = Property(str, _get_formatted_logs, notify=formattedLogsChanged)

    def _get_rich_logs(self) -> str:
        """The same entries with per-level colours, for display."""
        return self._rich

    richLogs = Property(str, _get_rich_logs, notify=richLogsChanged)

    def _get_colors(self) -> dict[str, str]:
        return dict(self._colors)

    def _set_colors(self, value: dict[str, str] | None) -> None:
        """Take the level colours from QML and re-render what is already here."""
        colors = {str(k): str(v) for k, v in dict(value or {}).items() if v}
        if colors == self._colors:
            return
        self._colors = colors
        self.colorsChanged.emit()
        self._render()

    colors = Property("QVariantMap", _get_colors, _set_colors, notify=colorsChanged)

    # -- writing -----------------------------------------------------------

    def add_log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        source: str = "System",
    ) -> None:
        """Add an entry, collapsing a repeat of the previous one.

        Args:
            message: The text to show.
            level: Which level it belongs to (the page colours by this).
            source: Where it came from, shown in brackets.
        """
        if self._logs:
            last = self._logs[-1]
            if (last.level, last.source, last.message) == (level, source, message):
                last.repeat += 1
                self._render()
                return

        self._logs.append(LogEntry(datetime.now(), level, message, source))
        self._render()

    def add_info(self, message: str, source: str = "System") -> None:
        """Add an info log entry."""
        self.add_log(message, LogLevel.INFO, source)

    def add_warning(self, message: str, source: str = "System") -> None:
        """Add a warning log entry."""
        self.add_log(message, LogLevel.WARNING, source)

    def add_error(self, message: str, source: str = "System") -> None:
        """Add an error log entry."""
        self.add_log(message, LogLevel.ERROR, source)

    @Slot()
    def clear(self) -> None:
        """Clear all log entries."""
        self._logs.clear()
        self._render()

    # -- rendering ---------------------------------------------------------

    def _format_plain(self, entry: LogEntry) -> str:
        """One line, as it reads on the terminal and in a copy."""
        repeat = f" (x{entry.repeat})" if entry.repeat > 1 else ""
        return (
            f"[{entry.timestamp:%H:%M:%S}] [{entry.level.name}] "
            f"[{entry.source}] {entry.message}{repeat}"
        )

    def _tint(self, text: str, color: str) -> str:
        """Wrap escaped text in a colour, or leave it plain when not set."""
        if not color:
            return escape(text)
        return f'<font color="{color}">{escape(text)}</font>'

    def _format_rich(self, entry: LogEntry) -> str:
        """One line of rich text: level tag tinted, message tinted when loud."""
        level = entry.level.name
        accent = self._colors.get(level.lower(), "")
        secondary = self._colors.get("secondary", "")
        body = accent if entry.level in _LOUD else self._colors.get("normal", "")
        repeat = f" (x{entry.repeat})" if entry.repeat > 1 else ""
        return " ".join(
            (
                self._tint(f"{entry.timestamp:%H:%M:%S}", secondary),
                self._tint(level, accent),
                self._tint(f"[{entry.source}]", secondary),
                self._tint(entry.message + repeat, body),
            )
        )

    def _render(self) -> None:
        """Rebuild both strings from the entry list."""
        self._formatted = "\n".join(self._format_plain(e) for e in self._logs)
        # Rich text collapses newlines, so the separators have to be markup.
        self._rich = "<br/>".join(self._format_rich(e) for e in self._logs)
        self.formattedLogsChanged.emit()
        self.richLogsChanged.emit()
