"""Cancellation support for long-running operations."""

from typing import Callable, Optional


class CancellationToken:
    """Token to check for and request cancellation of operations."""

    def __init__(self, is_cancelled_fn: Optional[Callable[[], bool]] = None):
        """
        Args:
            is_cancelled_fn: Optional callback that returns True if cancellation requested.
                           If None, cancellation is never triggered.
        """
        self._is_cancelled_fn = is_cancelled_fn or (lambda: False)

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._is_cancelled_fn()

    def raise_if_cancelled(self):
        """Raise CancelledException if cancellation requested."""
        if self.is_cancelled:
            raise CancelledException("Operation was cancelled")


class CancelledException(Exception):
    """Raised when an operation is cancelled."""
    pass


# Default token that never cancels (for backwards compatibility)
NONE_TOKEN = CancellationToken()
