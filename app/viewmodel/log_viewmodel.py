# coding: utf-8
"""Log ViewModel for the Symplify application.

This module provides the ViewModel for managing application logs,
collecting log messages from various components.

Example:
    >>> from app.viewmodel import LogViewModel
    >>> vm = LogViewModel()
    >>> vm.add_log("Calculation started")
"""
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal


class LogLevel(Enum):
    """Log level enumeration.

    Attributes:
        DEBUG: Debug level.
        INFO: Info level.
        WARNING: Warning level.
        ERROR: Error level.
    """

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class LogEntry:
    """A single log entry.

    Attributes:
        timestamp: When the log was created.
        level: The log level.
        message: The log message.
        source: The source component.
    """

    timestamp: datetime
    level: LogLevel
    message: str
    source: str


class LogViewModel(QObject):
    """ViewModel for application logs.

    Collects and manages log messages from various components,
    providing a centralized logging system.

    Signals:
        log_updated: Emitted when a new log entry is added.
            Args:
                entry: The new log entry.
        log_cleared: Emitted when logs are cleared.

    Attributes:
        _logs: Internal list of log entries.

    Example:
        >>> vm = LogViewModel()
        >>> vm.log_updated.connect(view.append_log)
        >>> vm.add_log("Calculation complete", LogLevel.INFO, "Calculator")
    """

    log_updated = Signal(LogEntry)
    log_cleared = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the log ViewModel.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._logs: List[LogEntry] = []

    def add_log(
        self, message: str, level: LogLevel = LogLevel.INFO, source: str = "System"
    ) -> None:
        """Add a log entry.

        Args:
            message: The log message.
            level: The log level. Defaults to INFO.
            source: The source component. Defaults to "System".
        """
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            source=source,
        )
        self._logs.append(entry)
        self.log_updated.emit(entry)

    def add_info(self, message: str, source: str = "System") -> None:
        """Add an info log.

        Args:
            message: The log message.
            source: The source component.
        """
        self.add_log(message, LogLevel.INFO, source)

    def add_warning(self, message: str, source: str = "System") -> None:
        """Add a warning log.

        Args:
            message: The log message.
            source: The source component.
        """
        self.add_log(message, LogLevel.WARNING, source)

    def add_error(self, message: str, source: str = "System") -> None:
        """Add an error log.

        Args:
            message: The log message.
            source: The source component.
        """
        self.add_log(message, LogLevel.ERROR, source)

    def get_logs(self) -> List[LogEntry]:
        """Get all log entries.

        Returns:
            List of log entries.
        """
        return self._logs.copy()

    def get_formatted_logs(self) -> str:
        """Get logs as formatted string.

        Returns:
            Formatted log content.
        """
        lines = []
        for entry in self._logs:
            time_str = entry.timestamp.strftime("%H:%M:%S")
            level_str = entry.level.name
            lines.append(f"[{time_str}] [{level_str}] [{entry.source}] {entry.message}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all logs."""
        self._logs.clear()
        self.log_cleared.emit()

    def get_log_count(self) -> int:
        """Get the number of log entries.

        Returns:
            The count of log entries.
        """
        return len(self._logs)
