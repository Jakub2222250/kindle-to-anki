from enum import IntEnum


class LogLevel(IntEnum):
    """Log levels ordered by severity (lower = more severe)."""
    ERROR = 0
    WARNING = 1
    INFO = 2
    TRACE = 3
    DEBUG = 4
