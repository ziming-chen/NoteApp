"""Run and save the container benchmark without installing packages on the host."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    command = ["docker", "compose", "-p", "noteapp", "-f", "docker-compose.yml",
               "-f", "compose.windows.yml", "-f", "docker-compose.https.yml",
               "exec", "-T", "web", "python", "-"]
    result = subprocess.run(command, cwd=ROOT / "NoteApp",
                            input=(HERE / "measure_hashes.py").read_bytes(),
                            capture_output=True, check=True)
    data = json.loads(result.stdout)
    dest = HERE / "results"
    history = dest / "benchmark-runs"
    history.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    encoded = json.dumps(data, indent=2) + "\n"
    (history / (stamp + ".json")).write_text(encoded, encoding="utf-8")
    (dest / "hash-benchmark.json").write_text(encoded, encoding="utf-8")
    run = data["primary"]
    output = [
        "Course hash-cost benchmark (assistant executed on the local machine)",
        f"Measured UTC: {data['measured_at_utc']}",
        f"MD5: {run['md5_per_second']:,.0f} operations/second; {run['md5_per_day']:,.0f} / day (estimated)",
        f"Argon2: {run['argon2_elapsed_ms']:.3f} ms / operation; {run['argon2_per_second']:.3f} / second; {run['argon2_per_day']:,.0f} / day (estimated)",
        f"Argon2 slowdown: {run['slowdown_ratio']:,.0f} times per operation",
        f"Argon2 parameters: {data['argon2_parameters']}",
        f"Five subsequent Argon2 runs median: {data['subsequent_argon2_median_ms']:.3f} ms",
        f"Five supplementary verification runs median: {data['supplementary_verify_median_ms']:.3f} ms",
        data["limits"],
    ]
    (dest / "hash-benchmark.txt").write_text("\n".join(output) + "\n", encoding="utf-8")
    print("\n".join(output))


if __name__ == "__main__":
    main()
