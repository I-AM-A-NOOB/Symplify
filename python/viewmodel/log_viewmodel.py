# coding: utf-8
"""Log viewmodel for the QML Symplify app.

Collects log messages and exposes a QML-bindable ``formattedLogs``
property. The dead ``get_logs``/``get_log_count`` accessors of the
widgets app are not carried over.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import List

from PySide6.QtCore import Property, QObject, Signal


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: datetime
    level: LogLevel
    message: str
    source: str


class LogViewModel(QObject):
    """Collects and formats application logs for display."""

    formattedLogsChanged = Signal()

    def __init__(self, parent=None):
        """Initialize the log viewmodel."""
        super().__init__(parent)
        self._logs: List[LogEntry] = []
        self._formatted: str = ""

    def _format_entry(self, entry: LogEntry) -> str:
        """Format a single log entry as one line."""
        time_str = entry.timestamp.strftime("%H:%M:%S")
        level_str = entry.level.name
        return f"[{time_str}] [{level_str}] [{entry.source}] {entry.message}"

    def _get_formatted_logs(self) -> str:
        """Return the incrementally maintained formatted log string."""
        return self._formatted

    formattedLogs = Property(str, _get_formatted_logs, notify=formattedLogsChanged)

    def add_log(
        self, message: str, level: LogLevel = LogLevel.INFO, source: str = "System"
    ) -> None:
        """Add a log entry."""
        entry = LogEntry(
            timestamp=datetime.now(), level=level, message=message, source=source
        )
        self._logs.append(entry)
        line = self._format_entry(entry)
        self._formatted = line if not self._formatted else self._formatted + "\n" + line
        self.formattedLogsChanged.emit()

    def add_info(self, message: str, source: str = "System") -> None:
        """Add an info log entry."""
        self.add_log(message, LogLevel.INFO, source)

    def add_warning(self, message: str, source: str = "System") -> None:
        """Add a warning log entry."""
        self.add_log(message, LogLevel.WARNING, source)

    def add_error(self, message: str, source: str = "System") -> None:
        """Add an error log entry."""
        self.add_log(message, LogLevel.ERROR, source)

    def clear(self) -> None:
        """Clear all log entries."""
        self._logs.clear()
        self._formatted = ""
        self.formattedLogsChanged.emit()
