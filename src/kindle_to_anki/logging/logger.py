from abc import ABC, abstractmethod
from typing import Any

from kindle_to_anki.logging.log_level import LogLevel


class Logger(ABC):
    """Abstract base for all loggers."""

    def __init__(self, level: LogLevel = LogLevel.INFO):
        self._level = level

    @property
    def level(self) -> LogLevel:
        return self._level

    @level.setter
    def level(self, value: LogLevel):
        self._level = value

    def should_log(self, level: LogLevel) -> bool:
        return level <= self._level

    @abstractmethod
    def _write(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        """Write a log message. Implementations must override this."""
        pass

    def log(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        if self.should_log(level):
            self._write(level, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.ERROR, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.WARNING, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.INFO, message, **kwargs)

    def trace(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.TRACE, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.DEBUG, message, **kwargs)
