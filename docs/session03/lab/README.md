# Session 03: Symmetric Encryption Lab

**Full name:** 陈子明 Chen Ziming

**CHU Student ID:** 2023905333

This lab implements the two classroom tasks on slide 30: recover a Caesar-encrypted message by frequency analysis, then compare AES-ECB and AES-GCM on an image. Both experiments use self-authored inputs because the slides do not supply a ciphertext or an image file. The NotesApp comment-column homework and Project 1 are separate tasks.

## Run

Python 3.12 was used. From this directory, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_lab.py
```

On the prepared Windows workstation, double-click `Run-Lab.cmd`, or run the last command above. Virtual-environment activation is not required. The included inputs are ready to use; `make_inputs.py` recreates them if needed.

Running `python caesar.py` or using VS Code's Run Python File button uses the bundled ciphertext. To attack another file, use `python caesar.py path/to/ciphertext.txt`. The default input is located relative to the script, so it also works from another working directory.

## 1. Recovering Caesar without the key

`caesar.py` shifts English letters while preserving case, punctuation, and spaces. The sample in `data/caesar_ciphertext.txt` was encrypted with shift 7. The attack receives only that ciphertext and an approximate English frequency model. It does not read the encryption key or the reference plaintext.

The lecture's first method assumes that the most common ciphertext letter represents E. Here that letter is L, so the proposed shift is `(L - E) mod 26 = 7`. A second method decrypts with each of the 26 possible shifts and ranks the results by chi-square distance from the expected English letter counts:

```text
score = sum((observed_count - expected_count)^2 / expected_count)
expected_count = number_of_letters * expected_percentage / 100
```

The lowest score is the closest frequency match. The reference plaintext is opened only after the attack, to check the recovered result.

| Measurement | Observed result |
| --- | --- |
| English letters in the sample | 1,067 |
| Most common ciphertext letter | L, 214 occurrences |
| Most-common-letter guess | Shift 7 |
| Best full-alphabet candidate | Shift 7; chi-square 136.498 |
| Second candidate | Shift 18; chi-square 2,778.014 |
| Recovered text equals reference | Yes, including case and punctuation |

![Ciphertext and recovered letter frequencies](results/caesar_frequency.png)

The upper plot shows the shifted frequency pattern. The lower plot compares the recovered text with the English model. A sample need not match the model exactly. Frequency analysis can rank the wrong candidate for short messages, other languages, or unusual prose; it is not a guaranteed language detector. Caesar also has only 25 nonidentity shifts, so every candidate can easily be inspected.

The recovered message and all candidate scores are saved in `results/caesar_recovered.txt` and `results/caesar_candidates.csv`.

## 2. AES-ECB and AES-GCM on an image

`make_inputs.py` draws a 512 by 384 pixel penguin with flat colours. `image_modes.py` reads its RGB pixels with Pillow and encrypts the same 589,824-byte payload using both modes. Each mode uses its own fresh random 256-bit AES key.

The experiment encrypts raw pixel bytes, not the compressed PNG file. Known dimensions are retained so the ciphertext can be displayed as an image. ECB uses PKCS#7 padding; the display excludes the padding bytes. GCM uses a fresh 12-byte nonce; the display excludes its 16-byte authentication tag. Full ciphertexts, including padding or tag, are saved separately for evidence.

![Original image, ECB, and GCM](results/image_comparison.png)

ECB still shows the penguin's outline and background regions. Equal aligned plaintext blocks produce equal ciphertext blocks under the same key. GCM's ciphertext view appears as noise, without the visible outline.

| Measurement | Original RGB | AES-256-ECB view | AES-256-GCM view |
| --- | ---: | ---: | ---: |
| Full aligned 16-byte blocks | 36,864 | 36,864 | 36,864 |
| Unique blocks | 205 | 205 | 36,864 |
| Occurrences beyond the first of each distinct block | 36,659 | 36,659 | 0 |
| Repeated occurrences / total | 99.44% | 99.44% | 0.00% |

Both decryptions recovered the original pixel bytes exactly. The pixel SHA-256 values in `results/metrics.json` agree for the original, ECB recovery, and GCM recovery.

| Additional check | Observed result |
| --- | --- |
| ECB ciphertext size, including padding | 589,840 bytes |
| GCM ciphertext size, including tag | 589,840 bytes |
| GCM nonce / tag | 12 / 16 bytes |
| Flip one bit in GCM ciphertext | Rejected with `InvalidTag` |
| Flip one bit in GCM tag | Rejected with `InvalidTag` |
| Change nonce or key | Both rejected with `InvalidTag` |
| Flip one bit in ECB's first content block | Decryption returned altered pixels; no authentication failure |

The ECB mutation leaves its final padding block intact. Padding errors can reject some malformed ECB ciphertexts, but padding is not an authentication check. No repeated GCM blocks were observed in this sample; that observation is not a proof of security for every input. Image dimensions and ciphertext length remain visible in this demonstration.

## Key and nonce handling

AES keys are generated using `AESGCM.generate_key` and kept only in process memory. No key is written to the source, results, or report. The GCM nonce is stored in `results/gcm_nonce.hex`; a nonce is not secret. A new nonce must be used for every encryption under the same GCM key. In a long-running application, nonce uniqueness and key lifecycle need their own design.

The decryption checks happen during the run. The saved ciphertext cannot be decrypted later without the discarded keys. Rerunning the lab generates new keys, ciphertext colours, and a new GCM nonce; the recovered plaintext, outline leakage, and round-trip checks remain reproducible.

## Files and verification

| File | Purpose |
| --- | --- |
| `caesar.py` | Caesar cipher, letter counts, ciphertext-only attack |
| `image_modes.py` | ECB and GCM encryption, decryption, and tampering checks |
| `make_inputs.py` | Recreate the two self-authored inputs |
| `run_lab.py` | Run both experiments, produce plots, and record measurements |
| `data/` | Input plaintext, ciphertext, and original image |
| `results/` | Figures, recovered files, ciphertexts, CSV tables, and JSON measurements |
| `tests/test_lab.py` | Cipher examples, attacks, padding, tampering, image handling, and CLI workflows |
| `README_STUDY.zh-CN.md` | Chinese lecture notes and reproduction guide |

Run the automated checks with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest --cov=. --cov-report=term-missing --cov-fail-under=80
```

All 52 checks passed. Combined statement and branch coverage of the three experiment modules was 98.85%, including command-line subprocesses. The input-generation helper is outside this coverage measure. Details are recorded in `results/verification.txt`. Checks cover known Caesar examples, recovery for all 26 shifts, exact AES round trips, rejection of modified GCM inputs, a non-block-aligned image, and the full command-line workflow. Figures were also opened to check the visible comparison.

To analyse another ciphertext or image:

```powershell
.\.venv\Scripts\python.exe caesar.py data/caesar_ciphertext.txt --output results/caesar_recovered.txt
.\.venv\Scripts\python.exe image_modes.py data/penguin.png --output-dir results/custom_image
```

## References

- Kristen Pire, *Session 03: Symmetric Encryption*, slides 11-18 and 22-30. The original slide deck is preserved in `../../Materials/Session03_Symmetric_Encryption.pdf`.
- [NIST FIPS 197: AES](https://csrc.nist.gov/pubs/fips/197/final): AES key sizes and its 128-bit block size.
- [cryptography 46.0.7: symmetric encryption](https://cryptography.io/en/46.0.7/hazmat/primitives/symmetric-encryption/): ECB block behaviour and padding.
- [cryptography 46.0.7: authenticated encryption](https://cryptography.io/en/46.0.7/hazmat/primitives/aead/): AESGCM nonce handling, appended tag, and `InvalidTag`.
