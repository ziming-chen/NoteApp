"""Check the attacks, encryption guarantees, and complete command-line lab."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image

from caesar import crack, encrypt, letter_counts, most_common_guess, rank_candidates
from image_modes import (
    decrypt_ecb,
    decrypt_gcm,
    encrypt_ecb,
    encrypt_gcm,
    run_image_lab,
)

ROOT = Path(__file__).resolve().parents[1]


def test_caesar_known_example_and_nonletters():
    assert encrypt("Hello, World! 123 中文 é", 3) == "Khoor, Zruog! 123 中文 é"


@pytest.mark.parametrize("shift", range(26))
def test_frequency_attack_recovers_every_shift(shift):
    plaintext = (ROOT / "data/caesar_plaintext.txt").read_text(encoding="utf-8")
    candidate = crack(encrypt(plaintext, shift))
    assert (candidate.shift, candidate.plaintext) == (shift, plaintext)


def test_negative_shift_and_wraparound():
    assert encrypt("Abc Xyz", -3) == "Xyz Uvw"
    assert encrypt("Abc Xyz", 29) == "Def Abc"


def test_counts_ignore_non_english_letters():
    assert letter_counts("EeA! 123 中文 é") == {"E": 2, "A": 1}


def test_simple_frequency_guess():
    assert most_common_guess("LLLLLL AA") == 7


def test_ranked_attack_uses_full_alphabet():
    ciphertext = (ROOT / "data/caesar_ciphertext.txt").read_text(encoding="utf-8")
    candidates = rank_candidates(ciphertext)
    assert len(candidates) == 26
    assert candidates[0].score <= candidates[-1].score
    assert candidates[0].shift == 7


@pytest.mark.parametrize("ciphertext", ["", "123! 中文 é"])
def test_attack_rejects_text_without_ascii_letters(ciphertext):
    with pytest.raises(ValueError, match="letters"):
        crack(ciphertext)
    with pytest.raises(ValueError, match="letters"):
        most_common_guess(ciphertext)


@pytest.mark.parametrize("data", [b"", b"x", b"a" * 16, bytes(range(255))])
def test_ecb_round_trip_handles_padding(data):
    key = AESGCM.generate_key(bit_length=256)
    encrypted = encrypt_ecb(data, key)
    assert len(encrypted) % 16 == 0
    assert decrypt_ecb(encrypted, key) == data


def test_ecb_preserves_equal_blocks():
    key = AESGCM.generate_key(bit_length=256)
    encrypted = encrypt_ecb(b"A" * 16 + b"B" * 16 + b"A" * 16, key)
    assert encrypted[:16] == encrypted[32:48]
    assert encrypted[:16] != encrypted[16:32]


def test_ecb_does_not_authenticate_modified_content():
    key = AESGCM.generate_key(bit_length=256)
    original = b"A" * 64
    encrypted = encrypt_ecb(original, key)
    modified = bytes([encrypted[0] ^ 1]) + encrypted[1:]
    assert decrypt_ecb(modified, key) != original


@pytest.mark.parametrize("data", [b"", b"Good work", bytes(range(255))])
def test_gcm_round_trip_and_tag_size(data):
    key = AESGCM.generate_key(bit_length=256)
    nonce, encrypted = encrypt_gcm(data, key)
    assert len(nonce) == 12
    assert len(encrypted) == len(data) + 16
    assert decrypt_gcm(nonce, encrypted, key) == data


def test_gcm_uses_fresh_nonce_for_each_encryption():
    key = AESGCM.generate_key(bit_length=256)
    first = encrypt_gcm(b"same message", key)
    second = encrypt_gcm(b"same message", key)
    assert first[0] != second[0]
    assert first[1] != second[1]


@pytest.mark.parametrize("change", ["ciphertext", "tag", "nonce", "key"])
def test_gcm_rejects_tampering_and_wrong_inputs(change):
    key = AESGCM.generate_key(bit_length=256)
    nonce, encrypted = encrypt_gcm(b"a message with enough bytes", key)
    if change == "ciphertext":
        encrypted = bytes([encrypted[0] ^ 1]) + encrypted[1:]
    elif change == "tag":
        encrypted = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
    elif change == "nonce":
        nonce = bytes([nonce[0] ^ 1]) + nonce[1:]
    else:
        key = bytes([key[0] ^ 1]) + key[1:]
    with pytest.raises(InvalidTag):
        decrypt_gcm(nonce, encrypted, key)


def test_image_lab_handles_non_block_aligned_rgba_image(tmp_path):
    input_path = tmp_path / "small.png"
    Image.new("RGBA", (7, 5), (90, 160, 230, 128)).save(input_path)
    metrics = run_image_lab(input_path, tmp_path / "output")
    assert metrics["pixel_bytes"] == 105
    assert metrics["ecb_round_trip"] and metrics["gcm_round_trip"]
    assert metrics["gcm_tampered_ciphertext_rejected"]
    with Image.open(tmp_path / "output/ecb_view.png") as image:
        assert image.size == (7, 5)


def test_full_lab_command_from_another_working_directory(tmp_path):
    output = tmp_path / "results"
    process = subprocess.run(
        [sys.executable, str(ROOT / "run_lab.py"), "--output-dir", str(output)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert "Caesar recovered shift: 7" in process.stdout
    assert metrics["caesar"]["plaintext_matches_reference"]
    image = metrics["image"]
    assert image["ecb_round_trip"] and image["gcm_round_trip"]
    assert image["original_blocks"]["unique"] < image["original_blocks"]["total"]
    assert image["ecb_blocks"]["unique"] == image["original_blocks"]["unique"]
    assert image["gcm_blocks"]["unique"] == image["gcm_blocks"]["total"]
    assert (output / "image_comparison.png").is_file()
    assert (output / "caesar_frequency.png").is_file()
    with (
        Image.open(output / "ecb_decrypted.png") as ecb,
        Image.open(output / "gcm_decrypted.png") as gcm,
        Image.open(ROOT / "data/penguin.png") as original,
    ):
        assert ecb.tobytes() == gcm.tobytes() == original.tobytes()


def test_image_command_works_with_non_aligned_input(tmp_path):
    input_path = tmp_path / "small.png"
    Image.new("RGB", (7, 5), "white").save(input_path)
    output = tmp_path / "results"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "image_modes.py"),
            str(input_path),
            "--output-dir",
            str(output),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    metrics = json.loads(process.stdout)
    assert metrics["ecb_round_trip"] and metrics["gcm_round_trip"]


def test_caesar_command_reads_ciphertext_only(tmp_path):
    output = tmp_path / "recovered.txt"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "caesar.py"),
            str(ROOT / "data/caesar_ciphertext.txt"),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "shift=7" in process.stdout
    assert output.read_text(encoding="utf-8") == (
        ROOT / "data/caesar_plaintext.txt"
    ).read_text(encoding="utf-8")


def test_caesar_command_without_arguments_uses_bundled_ciphertext(tmp_path):
    process = subprocess.run(
        [sys.executable, str(ROOT / "caesar.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert "shift=7" in process.stdout
    assert (ROOT / "data/caesar_plaintext.txt").read_text(
        encoding="utf-8"
    ) in process.stdout
