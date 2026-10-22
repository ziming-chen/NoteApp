# Lab 2 - Password storage

**Full name:** 陈子明 Chen Ziming - **CHU student ID:** 2023905333

**Lab partner:** 吴彦澜 Wu Yanlan - **CHU student ID:** 2023905420

The [combined findings sheet](../README.md#lab-2---password-storage) records the
original prediction, 4/6 dictionary result, Argon2id upgrade and measured cost.

From the repository root, reproduce the course-generated dump and guesses:

```powershell
python docs/session05/lab2/crack/make_dump.py
python docs/session05/lab2/crack/crack.py
python docs/session05/lab2/crack/rule_attack.py
```

The scripts use their own directory for data and save a new result. The original
timestamped dictionary run remains in `results/md5-runs/`. The optional rule run
is separate from the original four-account baseline.

To measure both hash algorithms inside the running web container, from the root:

```powershell
Get-Content -Raw docs/session05/lab2/measure_hashes.py | docker compose -p noteapp -f docker-compose.yml -f compose.windows.yml -f docker-compose.https.yml exec -T web python -
```

The output contains the primary run and supplementary samples. It measures hash
operation cost; the daily rates are estimates. `run_benchmark.py` and
`verify_live.py` are the original archived workspace helpers, whose original
workspace layout and database state are described in the combined report. Use
the command above for this repository layout; do not reset alice to repeat the
one-time migration. The root `tests/test_password_login.py` instead checks the
legacy-to-Argon2 transition in disposable databases.

`implementation/` preserves the tested implementation snapshot and patch.
The running implementation is in the repository's root `web/` and `tests/`.
