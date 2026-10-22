"""Run Session 03's two classroom experiments and save measured evidence."""

import argparse
import csv
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from string import ascii_uppercase

import matplotlib
import numpy as np
from PIL import Image

from caesar import (
    ENGLISH_FREQUENCIES,
    letter_counts,
    most_common_guess,
    rank_candidates,
)
from image_modes import run_image_lab

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402 -- select a noninteractive backend first.

ROOT = Path(__file__).resolve().parent


def save_frequency_plot(ciphertext: str, recovered: str, output_path: Path) -> None:
    total = sum(letter_counts(ciphertext).values())
    cipher_counts = letter_counts(ciphertext)
    recovered_counts = letter_counts(recovered)
    positions = np.arange(26)
    top_frequency = max(cipher_counts.values()) * 100 / total
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.8), layout="constrained")
    axes[0].bar(
        positions,
        [cipher_counts[letter] * 100 / total for letter in ascii_uppercase],
        color="#C66B32",
    )
    axes[0].set_title("Ciphertext letter frequencies: L is most common")
    axes[1].bar(
        positions - 0.18,
        [recovered_counts[letter] * 100 / total for letter in ascii_uppercase],
        width=0.36,
        label="Recovered text",
        color="#167D8D",
    )
    axes[1].bar(
        positions + 0.18,
        list(ENGLISH_FREQUENCIES.values()),
        width=0.36,
        label="Approximate English model",
        color="#A7BDCE",
    )
    axes[1].set_title("After shift 7 is reversed: compare the whole alphabet")
    axes[1].legend(frameon=False, loc="upper right")
    for axis in axes:
        axis.set_xticks(positions, list(ascii_uppercase))
        axis.set_ylabel("English letters (%)")
        axis.set_ylim(0, max(17, top_frequency * 1.15))
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=0.15)
        axis.set_axisbelow(True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def save_image_comparison(output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), layout="constrained")
    panels = (
        ("original.png", "Original", "Flat colours create repeated blocks"),
        ("ecb_view.png", "AES-256-ECB", "Repeated blocks preserve the outline"),
        ("gcm_view.png", "AES-256-GCM", "The outline is no longer visible"),
    )
    for axis, (filename, title, caption) in zip(axes, panels, strict=True):
        with Image.open(output_dir / filename) as image:
            axis.imshow(np.asarray(image), interpolation="nearest")
        axis.set_title(title, fontsize=15, pad=10)
        axis.set_xlabel(caption, fontsize=10, labelpad=10)
        axis.set_xticks([])
        axis.set_yticks([])
        axis.spines[:].set_visible(False)
    fig.savefig(output_dir / "image_comparison.png", dpi=150)
    plt.close(fig)


def run_lab(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    ciphertext = (ROOT / "data/caesar_ciphertext.txt").read_text(encoding="utf-8")

    # The attack reads ciphertext only. The reference is opened AFTER ranking.
    candidates = rank_candidates(ciphertext)
    best = candidates[0]
    reference = (ROOT / "data/caesar_plaintext.txt").read_text(encoding="utf-8")
    counts = letter_counts(ciphertext)
    (output_dir / "caesar_recovered.txt").write_text(best.plaintext, encoding="utf-8")
    with (output_dir / "caesar_candidates.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(["rank", "shift", "chi_square", "plaintext_preview"])
        for rank, candidate in enumerate(candidates, 1):
            writer.writerow(
                [
                    rank,
                    candidate.shift,
                    f"{candidate.score:.6f}",
                    candidate.plaintext[:100],
                ]
            )
    with (output_dir / "caesar_frequencies.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["letter", "ciphertext_count", "recovered_count", "english_model_percent"]
        )
        recovered_counts = letter_counts(best.plaintext)
        for letter in ascii_uppercase:
            writer.writerow(
                [
                    letter,
                    counts[letter],
                    recovered_counts[letter],
                    ENGLISH_FREQUENCIES[letter],
                ]
            )
    save_frequency_plot(ciphertext, best.plaintext, output_dir / "caesar_frequency.png")
    caesar_metrics = {
        "input_source": "Self-authored English fixture; not a teacher-provided ciphertext.",
        "ascii_letter_count": sum(counts.values()),
        "most_common_ciphertext_letter": counts.most_common(1)[0][0],
        "most_common_letter_count": counts.most_common(1)[0][1],
        "most_common_e_guess": most_common_guess(ciphertext),
        "recovered_shift": best.shift,
        "best_chi_square": best.score,
        "second_best_shift": candidates[1].shift,
        "second_best_chi_square": candidates[1].score,
        "plaintext_matches_reference": best.plaintext == reference,
        "attack_inputs": "Ciphertext and an approximate English frequency model only.",
    }
    image_metrics = run_image_lab(ROOT / "data/penguin.png", output_dir)
    save_image_comparison(output_dir)
    metrics = {
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            **{
                package: importlib.metadata.version(package)
                for package in ("cryptography", "Pillow", "matplotlib", "numpy")
            },
        },
        "caesar": caesar_metrics,
        "image": image_metrics,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    checks = [
        f"Caesar recovered shift: {best.shift}",
        f"Caesar matches original: {caesar_metrics['plaintext_matches_reference']}",
        f"ECB round trip: {image_metrics['ecb_round_trip']}",
        f"GCM round trip: {image_metrics['gcm_round_trip']}",
        f"GCM rejects modified ciphertext: {image_metrics['gcm_tampered_ciphertext_rejected']}",
        f"GCM rejects modified tag: {image_metrics['gcm_tampered_tag_rejected']}",
        f"GCM rejects wrong nonce: {image_metrics['gcm_wrong_nonce_rejected']}",
        f"GCM rejects wrong key: {image_metrics['gcm_wrong_key_rejected']}",
        f"ECB unique/total blocks: {image_metrics['ecb_blocks']['unique']}/{image_metrics['ecb_blocks']['total']}",
        f"GCM unique/total blocks: {image_metrics['gcm_blocks']['unique']}/{image_metrics['gcm_blocks']['total']}",
    ]
    console = "\n".join(checks) + "\n"
    (output_dir / "run_log.txt").write_text(console, encoding="utf-8")
    print(console, end="")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    run_lab(args.output_dir)


if __name__ == "__main__":
    main()
