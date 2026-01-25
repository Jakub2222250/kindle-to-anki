from typing import Any, Callable, Optional

from kindle_to_anki.logging.log_level import LogLevel
from kindle_to_anki.logging.logger import Logger


class UILogger(Logger):
    """Logger that delegates to a UI callback for display."""

    def __init__(
        self,
        level: LogLevel = LogLevel.INFO,
        callback: Optional[Callable[[LogLevel, str], None]] = None
    ):
        super().__init__(level)
        self._callback = callback

    def set_callback(self, callback: Callable[[LogLevel, str], None]) -> None:
        """Set or update the UI callback."""
        self._callback = callback

    def _write(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        if self._callback:
            self._callback(level, message)
