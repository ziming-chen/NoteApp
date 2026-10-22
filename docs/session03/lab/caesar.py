"""Caesar encryption and a ciphertext-only English frequency attack."""

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from string import ascii_uppercase

# Approximate English percentages, in A-Z order. A model, not a guarantee.
ENGLISH_FREQUENCIES = dict(
    zip(
        ascii_uppercase,
        (
            8.167,
            1.492,
            2.782,
            4.253,
            12.702,
            2.228,
            2.015,
            6.094,
            6.966,
            0.153,
            0.772,
            4.025,
            2.406,
            6.749,
            7.507,
            1.929,
            0.095,
            5.987,
            6.327,
            9.056,
            2.758,
            0.978,
            2.360,
            0.150,
            1.974,
            0.074,
        ),
        strict=True,
    )
)


@dataclass(frozen=True)
class Candidate:
    shift: int
    score: float
    plaintext: str


def encrypt(text: str, shift: int) -> str:
    """Shift ASCII letters; preserve case, spaces, punctuation, and other text."""
    result = []
    for char in text:
        if "A" <= char <= "Z":
            result.append(chr((ord(char) - ord("A") + shift) % 26 + ord("A")))
        elif "a" <= char <= "z":
            result.append(chr((ord(char) - ord("a") + shift) % 26 + ord("a")))
        else:
            result.append(char)
    return "".join(result)


def letter_counts(text: str) -> Counter:
    """Count only the 26 English letters, ignoring case."""
    return Counter(char.upper() for char in text if char.isascii() and char.isalpha())


def most_common_guess(ciphertext: str) -> int:
    """The lecture's first guess: assume the most frequent letter represents E."""
    counts = letter_counts(ciphertext)
    if not counts:
        raise ValueError("Frequency analysis needs ASCII letters.")
    most_common = counts.most_common(1)[0][0]
    return (ord(most_common) - ord("E")) % 26


def rank_candidates(ciphertext: str) -> list[Candidate]:
    """Rank shifts by chi-square distance from typical English letter counts.

    No original plaintext or encryption key is supplied to this attack.
    A smaller score is a closer fit; short or unusual text can mislead it.
    """
    total = sum(letter_counts(ciphertext).values())
    if total == 0:
        raise ValueError("Frequency analysis needs ASCII letters.")
    candidates = []
    for shift in range(26):
        plaintext = encrypt(ciphertext, -shift)
        observed = letter_counts(plaintext)
        score = 0.0
        for letter, percent in ENGLISH_FREQUENCIES.items():
            expected = total * percent / 100
            score += (observed[letter] - expected) ** 2 / expected
        candidates.append(Candidate(shift, score, plaintext))
    return sorted(candidates, key=lambda candidate: candidate.score)


def crack(ciphertext: str) -> Candidate:
    """Return the best frequency-based candidate, not a guaranteed answer."""
    return rank_candidates(ciphertext)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ciphertext",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "data/caesar_ciphertext.txt",
        help="UTF-8 ciphertext file (default: bundled example)",
    )
    parser.add_argument("--output", type=Path, help="Save the best candidate")
    args = parser.parse_args()
    ciphertext = args.ciphertext.read_text(encoding="utf-8")
    for candidate in rank_candidates(ciphertext)[:3]:
        print(f"shift={candidate.shift} chi-square={candidate.score:.3f}")
    best = crack(ciphertext)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(best.plaintext, encoding="utf-8")
    else:
        print(best.plaintext)


if __name__ == "__main__":
    main()
