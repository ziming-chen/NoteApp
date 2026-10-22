"""Authenticate the exact UTF-8 CSV export, excluding its final HMAC line."""

import hashlib
import hmac
import re
from pathlib import Path

CONTEXT = b"notesapp:grades-export:v1\x00"
TRAILER_PREFIX = b"# HMAC: v1:sha256:"
TRAILER_SIZE = len(TRAILER_PREFIX) + 64 + 2
TRAILER_PATTERN = re.compile(rb"# HMAC: v1:sha256:([0-9a-f]{64})\r\n")


class ExportIntegrityError(ValueError):
    """The export has no valid authentication tag for the configured key."""


class ExportAuthenticator:
    def __init__(self, key: bytes):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("The export HMAC key must contain exactly 32 bytes.")
        self._key = key

    @classmethod
    def from_key_file(cls, path: str | Path):
        return cls(Path(path).read_bytes())

    def _tag(self, payload: bytes) -> bytes:
        return hmac.new(self._key, CONTEXT + payload, hashlib.sha256).hexdigest().encode("ascii")

    def sign(self, payload: bytes) -> bytes:
        """Append a versioned trailer without changing any CSV data bytes."""
        if not payload.endswith(b"\r\n"):
            raise ValueError("The CSV payload must end with a CRLF record separator.")
        return payload + TRAILER_PREFIX + self._tag(payload) + b"\r\n"

    def verify(self, signed_export: bytes) -> bytes:
        """Return the original CSV bytes only after successful authentication."""
        payload = signed_export[:-TRAILER_SIZE]
        trailer = signed_export[-TRAILER_SIZE:]
        match = TRAILER_PATTERN.fullmatch(trailer)
        if not payload.endswith(b"\r\n") or match is None:
            raise ExportIntegrityError("Export integrity verification failed.")
        if not hmac.compare_digest(self._tag(payload), match.group(1)):
            raise ExportIntegrityError("Export integrity verification failed.")
        return payload
