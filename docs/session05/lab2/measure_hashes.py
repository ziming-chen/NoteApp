"""Course benchmark: run inside the NotesApp web container, emit measured JSON.

The primary run matches the course workload: 100,000 MD5 hexdigests and
one fresh Argon2 hash. Five subsequent repetitions describe timing variability.
These are CPU hash-operation rates, not an optimized password-cracker benchmark.
"""

import hashlib
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from argon2 import PasswordHasher


def main():
    n = 100_000
    ph = PasswordHasher()
    runs = []
    encoded = None
    for index in range(6):
        start = time.perf_counter_ns()
        for _ in range(n):
            hashlib.md5(b"guess").hexdigest()
        md5_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        encoded = ph.hash("guess")
        argon_ns = time.perf_counter_ns() - start
        md5_rate = n * 1e9 / md5_ns
        argon_rate = 1e9 / argon_ns
        runs.append({
            "index": index, "md5_operations": n, "md5_elapsed_ns": md5_ns,
            "argon2_operations": 1, "argon2_elapsed_ns": argon_ns,
            "argon2_elapsed_ms": argon_ns / 1e6,
            "md5_per_second": md5_rate, "argon2_per_second": argon_rate,
            "md5_per_day": md5_rate * 86400, "argon2_per_day": argon_rate * 86400,
            "slowdown_ratio": md5_rate / argon_rate,
        })
    # Verification is closer to testing a stolen hash than generating a new salt.
    # Keep it explicitly supplementary to the course's required measurement.
    verify_ns = []
    for _ in range(5):
        start = time.perf_counter_ns()
        assert ph.verify(encoded, "guess")
        verify_ns.append(time.perf_counter_ns() - start)
    cpu = next((line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), "unknown")
    output = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "operator": "Assistant execution on the user's machine, authorized by user",
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "argon2_cffi": version("argon2-cffi"), "cpu": cpu,
                        "logical_cpus_visible": os.cpu_count()},
        "method": "time.perf_counter_ns; primary 100000 MD5 hexdigests then one fresh Argon2 hash; same container",
        "argon2_parameters": {"type": ph.type.name, "version": 19,
                              "memory_kib": ph.memory_cost, "time_cost": ph.time_cost,
                              "parallelism": ph.parallelism, "hash_len": ph.hash_len,
                              "salt_len": ph.salt_len},
        "primary": runs[0], "subsequent_runs": runs[1:],
        "subsequent_argon2_median_ms": statistics.median(r["argon2_elapsed_ms"] for r in runs[1:]),
        "supplementary_verify_ns": verify_ns,
        "supplementary_verify_median_ms": statistics.median(verify_ns) / 1e6,
        "limits": "Hash-generation cost proxy; daily figures are linear estimates assuming uninterrupted sequential work, not observed 24-hour attacks or GPU/parallel cracking rates."
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
