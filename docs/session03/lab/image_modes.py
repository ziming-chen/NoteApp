"""Compare AES-ECB pattern leakage with AES-GCM on raw RGB image bytes.

ECB is included only to demonstrate its weakness. Keys exist only in memory.
"""

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image

BLOCK_BYTES = 16
TAG_BYTES = 16


def encrypt_ecb(data: bytes, key: bytes) -> bytes:
    """Lab demonstration only: pad then encrypt independent AES blocks."""
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def decrypt_ecb(ciphertext: bytes, key: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def encrypt_gcm(data: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Return a fresh 12-byte nonce and ciphertext with its 16-byte tag."""
    nonce = os.urandom(12)
    return nonce, AESGCM(key).encrypt(nonce, data, None)


def decrypt_gcm(nonce: bytes, ciphertext_and_tag: bytes, key: bytes) -> bytes:
    """Authenticate before returning plaintext; InvalidTag means rejection."""
    return AESGCM(key).decrypt(nonce, ciphertext_and_tag, None)


def block_statistics(data: bytes) -> dict:
    """Count aligned full 16-byte blocks; omit a trailing partial block."""
    blocks = [
        data[i : i + BLOCK_BYTES]
        for i in range(0, len(data) - BLOCK_BYTES + 1, BLOCK_BYTES)
    ]
    counts = Counter(blocks)
    total = len(blocks)
    unique = len(counts)
    return {
        "total": total,
        "unique": unique,
        "repeated_occurrences": total - unique,
        "repeated_fraction": (total - unique) / total if total else 0.0,
    }


def rejects_gcm(nonce: bytes, ciphertext: bytes, key: bytes) -> bool:
    try:
        decrypt_gcm(nonce, ciphertext, key)
    except InvalidTag:
        return True
    return False


def run_image_lab(input_path: Path, output_dir: Path) -> dict:
    """Encrypt real pixels, render ciphertext, and check decryption and tampering."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as source:
        original = source.convert("RGB")
    pixels = original.tobytes()
    ecb_key = AESGCM.generate_key(bit_length=256)
    gcm_key = AESGCM.generate_key(bit_length=256)
    ecb_ciphertext = encrypt_ecb(pixels, ecb_key)
    nonce, gcm_ciphertext = encrypt_gcm(pixels, gcm_key)
    ecb_plaintext = decrypt_ecb(ecb_ciphertext, ecb_key)
    gcm_plaintext = decrypt_gcm(nonce, gcm_ciphertext, gcm_key)

    # Keep the original dimensions for viewing; padding and tag are not pixels.
    ecb_view = ecb_ciphertext[: len(pixels)]
    gcm_view = gcm_ciphertext[:-TAG_BYTES]
    views = {
        "original": pixels,
        "ecb_view": ecb_view,
        "gcm_view": gcm_view,
        "ecb_decrypted": ecb_plaintext,
        "gcm_decrypted": gcm_plaintext,
    }
    for name, content in views.items():
        Image.frombytes("RGB", original.size, content).save(output_dir / f"{name}.png")
    (output_dir / "ecb_ciphertext.bin").write_bytes(ecb_ciphertext)
    (output_dir / "gcm_ciphertext_and_tag.bin").write_bytes(gcm_ciphertext)
    (output_dir / "gcm_nonce.hex").write_text(nonce.hex() + "\n", encoding="ascii")

    changed_gcm = bytes([gcm_ciphertext[0] ^ 1]) + gcm_ciphertext[1:]
    changed_tag = gcm_ciphertext[:-1] + bytes([gcm_ciphertext[-1] ^ 1])
    changed_nonce = bytes([nonce[0] ^ 1]) + nonce[1:]
    changed_key = bytes([gcm_key[0] ^ 1]) + gcm_key[1:]

    # Flip a content byte, leaving the final padding block alone when possible.
    ecb_tampered_decrypted = None
    if len(pixels) >= BLOCK_BYTES:
        changed_ecb = bytes([ecb_ciphertext[0] ^ 1]) + ecb_ciphertext[1:]
        ecb_tampered_decrypted = decrypt_ecb(changed_ecb, ecb_key) != pixels

    metrics = {
        "width": original.width,
        "height": original.height,
        "mode": "RGB",
        "pixel_bytes": len(pixels),
        "aes_key_bits": 256,
        "aes_block_bytes": BLOCK_BYTES,
        "ecb_ciphertext_bytes": len(ecb_ciphertext),
        "gcm_ciphertext_and_tag_bytes": len(gcm_ciphertext),
        "gcm_nonce_bytes": len(nonce),
        "gcm_tag_bytes": TAG_BYTES,
        "gcm_nonce_hex": nonce.hex(),
        "original_sha256": hashlib.sha256(pixels).hexdigest(),
        "ecb_decrypted_sha256": hashlib.sha256(ecb_plaintext).hexdigest(),
        "gcm_decrypted_sha256": hashlib.sha256(gcm_plaintext).hexdigest(),
        "ecb_round_trip": ecb_plaintext == pixels,
        "gcm_round_trip": gcm_plaintext == pixels,
        "ecb_modified_content_decrypted_without_authentication": ecb_tampered_decrypted,
        "gcm_tampered_ciphertext_rejected": rejects_gcm(nonce, changed_gcm, gcm_key),
        "gcm_tampered_tag_rejected": rejects_gcm(nonce, changed_tag, gcm_key),
        "gcm_wrong_nonce_rejected": rejects_gcm(changed_nonce, gcm_ciphertext, gcm_key),
        "gcm_wrong_key_rejected": rejects_gcm(nonce, gcm_ciphertext, changed_key),
        "original_blocks": block_statistics(pixels),
        "ecb_blocks": block_statistics(ecb_view),
        "gcm_blocks": block_statistics(gcm_view),
        "key_storage": "Fresh independent keys per mode; memory only; not saved.",
        "view_format": "Ciphertext bytes rendered as RGB with known image dimensions.",
    }
    (output_dir / "image_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/custom_image"))
    args = parser.parse_args()
    print(json.dumps(run_image_lab(args.image, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
