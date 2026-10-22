"""Optional course extension: add <username>pw guesses to the same local dump."""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    accounts = dict(line.split(":", 1) for line in (here / "leaked_users.txt").read_text().splitlines() if line)
    words = [w.strip() for w in (here / "wordlist.txt").read_text(encoding="utf-8-sig").splitlines() if w.strip()]
    rules = [username + "pw" for username in accounts]
    candidates = words + rules
    start = time.perf_counter_ns()
    cracked = {}
    for candidate in candidates:
        digest = hashlib.md5(candidate.encode()).hexdigest()
        for username, stored in accounts.items():
            if username not in cracked and digest == stored:
                cracked[username] = candidate
    elapsed_ns = time.perf_counter_ns() - start
    result = {"measured_at_utc": datetime.now(timezone.utc).isoformat(),
              "operator": "Assistant execution, authorized by user",
              "scope": "Six simulated course accounts only; no network requests",
              "public_wordlist_candidates": len(words), "rule_candidates": rules,
              "total_candidates": len(candidates), "cracked_accounts": len(cracked),
              "total_accounts": len(accounts), "cracked": cracked,
              "held_out": [u for u in accounts if u not in cracked],
              "elapsed_ns": elapsed_ns, "elapsed_ms": elapsed_ns / 1e6,
              "method": "MD5 each candidate once; compare to six unsalted digests; loop only"}
    results = here.parent / "results"
    (results / "rule-run.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    text = (f"Optional rule attack: {len(words)} public entries + {len(rules)} username-pw guesses\n"
            f"Recovered {len(cracked)}/{len(accounts)} in {elapsed_ns / 1e6:.4f} ms\n"
            f"Additional account: marie (mariepw)\nHeld out: {', '.join(result['held_out'])}\n")
    (results / "rule-run.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
