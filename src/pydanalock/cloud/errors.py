"""Typed errors raised by the Danalock cloud client (spec 0001 R6)."""

from __future__ import annotations


class DanalockCloudError(Exception):
    """Base class for all errors raised by pydanalock-cloud."""


class AuthError(DanalockCloudError):
    """Authentication failed: bad credentials, a rejected grant, or a failed
    token refresh."""


class ApiError(DanalockCloudError):
    """The API answered with an unexpected HTTP status or a malformed body.

    Carries the HTTP status of the response that triggered it.
    """

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.status = status


class DeviceNotFoundError(DanalockCloudError):
    """No device or key exists for the requested serial (spec 0002 R6)."""

    def __init__(self, serial: str) -> None:
        super().__init__(f"no device found for serial {serial!r}")
        self.serial = serial
