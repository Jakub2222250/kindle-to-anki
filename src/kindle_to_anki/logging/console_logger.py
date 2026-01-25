from datetime import datetime
from typing import Any

from kindle_to_anki.logging.log_level import LogLevel
from kindle_to_anki.logging.logger import Logger


class ConsoleLogger(Logger):
    """Logger that prints to console with optional timestamps and level prefixes."""

    LEVEL_COLORS = {
        LogLevel.ERROR: "\033[91m",    # Red
        LogLevel.WARNING: "\033[93m",  # Yellow
        LogLevel.INFO: "\033[0m",      # Default
        LogLevel.TRACE: "\033[96m",    # Cyan
        LogLevel.DEBUG: "\033[90m",    # Gray
    }
    RESET = "\033[0m"

    def __init__(
        self,
        level: LogLevel = LogLevel.INFO,
        show_timestamp: bool = False,
        show_level: bool = True,
        use_colors: bool = True
    ):
        super().__init__(level)
        self.show_timestamp = show_timestamp
        self.show_level = show_level
        self.use_colors = use_colors

    def _write(self, level: LogLevel, message: str, **kwargs: Any) -> None:
        parts = []

        if self.show_timestamp:
            parts.append(datetime.now().strftime("[%H:%M:%S]"))

        if self.show_level:
            parts.append(f"[{level.name}]")

        parts.append(message)
        output = " ".join(parts)

        if self.use_colors:
            color = self.LEVEL_COLORS.get(level, self.RESET)
            output = f"{color}{output}{self.RESET}"

        print(output)
