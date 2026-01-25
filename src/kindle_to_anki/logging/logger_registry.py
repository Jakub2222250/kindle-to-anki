from typing import Optional

from kindle_to_anki.logging.log_level import LogLevel
from kindle_to_anki.logging.logger import Logger
from kindle_to_anki.logging.console_logger import ConsoleLogger


class LoggerRegistry:
    """Global registry for the active logger instance."""

    _instance: Optional[Logger] = None

    @classmethod
    def get(cls) -> Logger:
        """Get the current logger, creating a default ConsoleLogger if none set."""
        if cls._instance is None:
            cls._instance = ConsoleLogger(level=LogLevel.INFO)
        return cls._instance

    @classmethod
    def set(cls, logger: Logger) -> None:
        """Set the global logger instance."""
        cls._instance = logger

    @classmethod
    def reset(cls) -> None:
        """Reset to no logger (next get() will create default)."""
        cls._instance = None


def get_logger() -> Logger:
    """Convenience function to get the current logger."""
    return LoggerRegistry.get()
