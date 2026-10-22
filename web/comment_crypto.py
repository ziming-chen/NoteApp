"""Versioned AES-256-GCM envelopes for the notes.comment TEXT column."""

import base64
import binascii
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "aesgcm:v1:"


class CommentCryptoError(ValueError):
    """Stored data could not be authenticated; no plaintext is returned."""


class CommentCipher:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError(
                "The comment encryption key must contain exactly 32 bytes."
            )
        self._aes = AESGCM(key)

    @classmethod
    def from_key_file(cls, path):
        return cls(Path(path).read_bytes())

    @staticmethod
    def _aad(note_id: int) -> bytes:
        if not isinstance(note_id, int) or isinstance(note_id, bool) or note_id <= 0:
            raise ValueError("A positive integer note ID is required.")
        return f"notesapp:notes:{note_id}:comment:v1".encode("ascii")

    def encrypt(self, plaintext: str | None, note_id: int) -> str | None:
        if plaintext is None:
            return None
        nonce = os.urandom(12)
        ciphertext_and_tag = self._aes.encrypt(
            nonce, plaintext.encode("utf-8"), self._aad(note_id)
        )
        return PREFIX + base64.b64encode(nonce + ciphertext_and_tag).decode("ascii")

    def decrypt(self, stored: str | None, note_id: int) -> str | None:
        if stored is None:
            return None
        if not stored.startswith(PREFIX):
            raise CommentCryptoError("Unsupported comment encryption format.")
        try:
            payload = base64.b64decode(stored[len(PREFIX) :], validate=True)
            if len(payload) < 28:
                raise CommentCryptoError("Incomplete encrypted comment.")
            plaintext = self._aes.decrypt(
                payload[:12], payload[12:], self._aad(note_id)
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, binascii.Error, UnicodeError) as exc:
            raise CommentCryptoError("Comment authentication failed.") from exc
