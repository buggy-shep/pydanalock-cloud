"""Parsed cloud API models and pure response parsers (spec 0002).

`DeviceKey` is the group contract type: field names and order are shared
with consumers (see specs 0002/0003). Key material is kept as opaque
bytes end-to-end; base64 is decoded once at this boundary.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SERIAL_PATTERN = re.compile(r"^[0-9a-f]{12}$")
BROADCAST_KEY_SIZE = 16


@dataclass(frozen=True)
class Permission:
    """A permission granted to the account on a device."""

    id: str
    name: str
    description: str


@dataclass(frozen=True)
class DeviceSummary:
    """A device listed for the account."""

    serial: str
    name: str | None = None
    device_type: str | None = None


@dataclass(frozen=True)
class DeviceKey:
    """Key material for one device (group contract, opaque bytes)."""

    serial: str
    login_blob: bytes
    broadcast_key: bytes
    valid_from: datetime | None
    valid_to: datetime | None
    permissions: tuple[Permission, ...]


@dataclass(frozen=True)
class FirmwareVersion:
    """Latest published firmware for one device (spec 0006).

    `url` is a short-lived signed download link; consumers must not
    persist it.
    """

    firmware_identifier: str
    maturity: str
    url: str
    version: str


def normalize_serial(raw: str) -> str:
    """Lowercase hex without separators; the canonical device identity.

    Raises ValueError when the result is not 12 lowercase hex characters.
    """
    normalized = raw.strip().replace(":", "").replace("-", "").lower()
    if not SERIAL_PATTERN.match(normalized):
        raise ValueError(f"serial {raw!r} is not 12 hex characters")
    return normalized


def serial_with_separators(normalized: str) -> str:
    """Wire serial format (lowercase hex, colon-separated) for URL paths.

    The API rejects the separator-free form on single-device endpoints
    (422 validation_failed); identity stays normalized (see normalize_serial).
    Precondition: `normalized` must be the 12-hex output of normalize_serial.
    """
    return ":".join(normalized[i : i + 2] for i in range(0, len(normalized), 2))


def decode_base64(value: Any, field: str) -> bytes:
    """Decode a strict base64 string field into bytes."""
    if not isinstance(value, str):
        raise ValueError(f"field {field!r} is not a base64 string")
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError(f"field {field!r} is not valid base64") from exc


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp; naive values are read as UTC."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("validity timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp {value!r}") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def parse_permissions(payload: Any) -> tuple[Permission, ...]:
    if not isinstance(payload, list):
        raise ValueError("permissions is not a list")
    permissions: list[Permission] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("permission entry is not an object")
        for field in ("id", "name", "description"):
            if not isinstance(entry.get(field), str):
                raise ValueError(f"permission field {field!r} is not a string")
        permissions.append(
            Permission(
                id=entry["id"],
                name=entry["name"],
                description=entry["description"],
            )
        )
    return tuple(permissions)


def parse_device_key(entry: Any) -> DeviceKey:
    """Parse one device login-token response object into a DeviceKey.

    Accepts both `serial_number` and `serialNumber` spellings; raises
    ValueError/KeyError/TypeError on malformed input (mapped to ApiError by
    the client with the HTTP status attached).
    """
    if not isinstance(entry, dict):
        raise ValueError("device entry is not an object")
    device = entry["device"]
    if not isinstance(device, dict):
        raise ValueError("device is not an object")
    raw_serial = device.get("serial_number")
    if raw_serial is None:
        raw_serial = device["serialNumber"]
    if not isinstance(raw_serial, str):
        raise ValueError("device serial is not a string")
    metadata = entry["metadata"]
    if not isinstance(metadata, dict):
        raise ValueError("metadata is not an object")
    name = device.get("name")
    if name is not None and not isinstance(name, str):
        raise ValueError("device name is not a string")
    broadcast_key = decode_base64(entry["broadcast_key"], "broadcast_key")
    if len(broadcast_key) != BROADCAST_KEY_SIZE:
        raise ValueError(
            f"broadcast_key is {len(broadcast_key)} bytes, expected {BROADCAST_KEY_SIZE}"
        )
    return DeviceKey(
        serial=normalize_serial(raw_serial),
        login_blob=decode_base64(entry["blob"], "blob"),
        broadcast_key=broadcast_key,
        valid_from=parse_datetime(metadata["valid_from"]),
        valid_to=parse_datetime(metadata["valid_to"]),
        permissions=parse_permissions(metadata["permissions"]),
    )


def key_expired(key: DeviceKey, now: datetime | None = None) -> bool:
    """True when the key's validity window has ended (None means open-ended)."""
    if key.valid_to is None:
        return False
    return key.valid_to < (now if now is not None else datetime.now(UTC))


def parse_device_name(entry: Any) -> str | None:
    """Extract the optional display name from a response object."""
    device = entry["device"] if isinstance(entry, dict) else None
    if not isinstance(device, dict):
        return None
    name = device.get("name")
    return name if isinstance(name, str) else None


def parse_device_type(entry: Any) -> str | None:
    """Extract the optional device product type from a response object.

    Accepts both `device_type` and `deviceType` spellings; absent or
    non-string values summarize as `None`.
    """
    device = entry["device"] if isinstance(entry, dict) else None
    if not isinstance(device, dict):
        return None
    device_type = device.get("device_type")
    if device_type is None:
        device_type = device.get("deviceType")
    return device_type if isinstance(device_type, str) else None


def parse_firmware_version(payload: Any) -> FirmwareVersion:
    """Parse one firmware-latest response object into a FirmwareVersion.

    Strict: every field (`firmware_identifier`, `maturity`, `url`,
    `version`) must be a present string. Raises ValueError on malformed
    input (mapped to ApiError by the client with the HTTP status
    attached).
    """
    if not isinstance(payload, dict):
        raise ValueError("firmware version entry is not an object")
    fields: dict[str, str] = {}
    for field in ("firmware_identifier", "maturity", "url", "version"):
        value = payload.get(field)
        if not isinstance(value, str):
            raise ValueError(f"firmware field {field!r} is not a string")
        fields[field] = value
    return FirmwareVersion(**fields)
