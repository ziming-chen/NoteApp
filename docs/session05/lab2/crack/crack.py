"""Measure a dictionary attack against the local course-generated MD5 file."""

import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    dump_path = directory / "leaked_users.txt"
    wordlist_path = directory / "wordlist.txt"
    if not dump_path.exists():
        raise SystemExit("First run: python crack/make_dump.py")
    accounts = {}
    for line in dump_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            username, digest = line.strip().split(":")
            accounts[username] = digest
    candidates = [
        line.strip()
        for line in wordlist_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]

    # Match the course algorithm: hash each candidate once, compare to all accounts.
    # File loading and result writing are excluded from the measured interval.
    start = time.perf_counter_ns()
    cracked = {}
    for candidate in candidates:
        candidate_digest = hashlib.md5(candidate.encode("utf-8")).hexdigest()
        for username, digest in accounts.items():
            if username not in cracked and digest == candidate_digest:
                cracked[username] = candidate
    elapsed_ns = time.perf_counter_ns() - start

    result = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "Six simulated course accounts; no connection to NotesApp or other targets",
        "algorithm": "MD5 without salt",
        "wordlist_candidates": len(candidates),
        "wordlist_sha256": hashlib.sha256(wordlist_path.read_bytes()).hexdigest(),
        "dump_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
        "total_accounts": len(accounts),
        "cracked_accounts": len(cracked),
        "cracked": cracked,
        "held_out": [username for username in accounts if username not in cracked],
        "elapsed_ns": elapsed_ns,
        "elapsed_ms": elapsed_ns / 1_000_000,
        "timer": "time.perf_counter_ns; matching loop only",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }
    output = [
        f"Public wordlist: {len(candidates)} candidates",
        f"cracked {len(cracked)} / {len(accounts)} in {result['elapsed_ms']:.3f} ms",
    ]
    output.extend(f"  {username} : {password}" for username, password in cracked.items())
    output.append("Held out: " + ", ".join(result["held_out"]))
    results = directory.parent / "results"
    history = results / "md5-runs"
    history.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    encoded = json.dumps(result, indent=2) + "\n"
    (history / f"{stamp}.json").write_text(encoded, encoding="utf-8")
    (results / "md5-run.json").write_text(encoded, encoding="utf-8")
    (results / "md5-run.txt").write_text("\n".join(output) + "\n", encoding="utf-8")
    print("\n".join(output))
    print("Results saved in results/md5-run.json and results/md5-run.txt")


if __name__ == "__main__":
    main()
