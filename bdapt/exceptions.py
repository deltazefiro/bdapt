"""Minimal set of custom exceptions for bdapt."""

from typing import Optional


class BdaptError(Exception):
    """Base exception for bdapt with optional exit code."""

    def __init__(self, message: str, *, exit_code: int = 1, displayed: bool = False):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.displayed = displayed

    def __str__(self) -> str:  # pragma: no cover - simple accessor
        return self.message


class ValidationError(BdaptError):
    """Raised when input validation fails."""


class StorageError(BdaptError):
    """Raised when storage operations fail."""


class CommandError(BdaptError):
    """Raised when external command execution fails."""

    def __init__(
        self,
        message: str,
        *,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        exit_code: int = 1,
        displayed: bool = False,
    ):
        super().__init__(message, exit_code=exit_code, displayed=displayed)
        self.stdout = stdout
        self.stderr = stderr


class UserAbortError(BdaptError):
    """Raised when an operation is cancelled or interrupted by the user."""

    def __init__(self, message: str = "Operation cancelled by user.", *, exit_code: int = 130, displayed: bool = False):
        super().__init__(message, exit_code=exit_code, displayed=displayed)
