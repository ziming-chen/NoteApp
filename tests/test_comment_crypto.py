"""Storage encryption must preserve text and reject unauthenticated input."""

import base64
import os

import pytest

from comment_crypto import CommentCipher, CommentCryptoError


@pytest.fixture
def cipher():
    return CommentCipher(os.urandom(32))


@pytest.mark.parametrize("text", [None, "", "Good work", "中文评语 é 😀\nSecond line"])
def test_round_trip(cipher, text):
    stored = cipher.encrypt(text, 7)
    assert cipher.decrypt(stored, 7) == text
    if text is not None:
        assert stored.startswith("aesgcm:v1:")
        payload = base64.b64decode(stored.split(":", 2)[2], validate=True)
        assert len(payload) == 12 + len(text.encode()) + 16


def test_repeated_writes_use_different_nonces(cipher):
    first = cipher.encrypt("same comment", 1)
    second = cipher.encrypt("same comment", 1)
    assert first != second
    assert cipher.decrypt(first, 1) == cipher.decrypt(second, 1)


@pytest.mark.parametrize("offset", [0, 12, -1])
def test_nonce_ciphertext_and_tag_tampering_rejected(cipher, offset):
    stored = cipher.encrypt("long enough for ciphertext", 1)
    payload = bytearray(base64.b64decode(stored.split(":", 2)[2]))
    payload[offset] ^= 1
    modified = "aesgcm:v1:" + base64.b64encode(payload).decode()
    with pytest.raises(CommentCryptoError):
        cipher.decrypt(modified, 1)


def test_wrong_key_and_row_swap_rejected(cipher):
    stored = cipher.encrypt("private comment", 1)
    with pytest.raises(CommentCryptoError):
        CommentCipher(os.urandom(32)).decrypt(stored, 1)
    with pytest.raises(CommentCryptoError):
        cipher.decrypt(stored, 2)


@pytest.mark.parametrize(
    "stored", ["plain text", "aesgcm:v2:AAAA", "aesgcm:v1:!", "aesgcm:v1:AAAA"]
)
def test_malformed_or_plaintext_storage_rejected(cipher, stored):
    with pytest.raises(CommentCryptoError):
        cipher.decrypt(stored, 1)


@pytest.mark.parametrize("size", [0, 16, 24, 31, 33])
def test_only_256_bit_key_accepted(size):
    with pytest.raises(ValueError, match="32"):
        CommentCipher(bytes(size))


def test_persistent_key_file_and_missing_key(tmp_path):
    key_path = tmp_path / "comment.key"
    with pytest.raises(FileNotFoundError):
        CommentCipher.from_key_file(key_path)
    key_path.write_bytes(os.urandom(32))
    first = CommentCipher.from_key_file(key_path)
    stored = first.encrypt("survives restart", 8)
    assert (
        CommentCipher.from_key_file(key_path).decrypt(stored, 8) == "survives restart"
    )


def test_prefix_in_user_text_is_encrypted_as_text(cipher):
    text = "aesgcm:v1:this is literal user input"
    assert cipher.decrypt(cipher.encrypt(text, 4), 4) == text


@pytest.mark.parametrize("note_id", [0, -1, "7", True])
def test_invalid_aad_id_rejected(cipher, note_id):
    with pytest.raises(ValueError, match="positive integer"):
        cipher.encrypt("text", note_id)
