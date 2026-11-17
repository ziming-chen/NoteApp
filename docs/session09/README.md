# Class 9 — Injection: SQL injection and command injection

**App:** local NotesApp clone, HTTP on `127.0.0.1:8080`
**Author:** Chen Ziming (CHU 2023905333) — individual execution
**Date:** 2026-11-17
**Commit:** `420132e`

The lab closes two bugs that share one root cause: user text is glued into a command
string that an interpreter then obeys — the database (SQL) or the shell (OS command).
The fix is the same shape in both places: **pass data as data, never as part of the
command.**

> **Deviation from the lab baseline (read first).** The lab's Part 1 assumes
> `WHERE username = '...' AND password = '...'`. This build no longer does: the
> Class 5 password lab moved password verification into Python (`check_password`,
> Argon2 + legacy fallback), and I did not undo that hardening. So the slide's
> `admin' --` cannot bypass login here — there is no SQL password clause to comment
> out. The injection point was still real before the fix; the no-password admin
> proof is the UNION below.

## Finding (hand-in)

See [`audit.txt`](audit.txt). Summary: flaws #8 (SQL injection on login) and #9
(command injection on the admin ping box) are closed; the UNION and ping payloads
are now inert; real logins and real pings still work; 102 tests pass.

## Part 1 — SQL injection on the login

Before the fix, the login built
`SELECT id, username, role, password FROM users WHERE username = '<input>'`.

- **The proof: a UNION that fabricates an admin row logs in as administrator
  without the real admin password.**

  ```
  username: zzz' UNION SELECT 1,'admin','admin','pwned' --
  password: pwned
  ```

  Result before the fix: login POST **302**, admin page **200** — full admin access.
  Evidence:
  [`evidence/before/part1b_union_admin_login.txt`](evidence/before/part1b_union_admin_login.txt).

- **The lab's classic payload is blocked on this build, and this is a tested
  observation, not a claim from the slides.** `username = admin' -- ` with any
  *wrong* password returns to the login page (login POST 200, admin page 302). The
  SQL only looks up the row by name; the password is checked separately, so there
  is no `AND password = ...` to comment out. Evidence:
  [`evidence/before/part1_dashdash_blocked.txt`](evidence/before/part1_dashdash_blocked.txt).
  After the fix it is still blocked (200 / 302) — the same outcome, for the same
  reason.

## Part 2 — Un-glue the query: the fix

```python
query = "SELECT id, username, role, password FROM users WHERE username = %s"
cur.execute(query, (username,))
```

The `%s` is a driver placeholder, not string formatting. The input travels in a
separate envelope marked "data", so quotes, `--` and `UNION` are just characters in
a username. After the fix the same UNION username returns login POST 200 / admin
page 302 — login fails. Evidence:
[`evidence/after/part1b_union_blocked.txt`](evidence/after/part1b_union_blocked.txt).

The old test that asserted the SQL `Query error` symptom was replaced: keeping that
assertion would have meant keeping the bug. The replacement checks that a lone quote
is literal data, that no raw SQL error leaks for that input, and that the UNION
payload cannot forge an admin login.

## Part 3 — command injection on the admin ping box

`admin_ping()` built `"ping -c 1 " + host` and ran it with `shell=True`, so `;` starts
a second command.

- Payload `host = 127.0.0.1; id; head -2 /etc/passwd` returned, before the fix,
  `uid=0(root) gid=0(root) groups=0(root)` and the first lines of `/etc/passwd`.
  Evidence:
  [`evidence/before/part3_cmdinjection_output.txt`](evidence/before/part3_cmdinjection_output.txt).

### Fix

```python
result = subprocess.run(
    ["ping", "-c", "1", host],
    capture_output=True, text=True, timeout=10,
)
```

An argument list with no shell. `host` is a single argument from start to finish, so
`;` `|` `&` `$()` `` ` `` cannot start anything. After the fix the same payload
returns `ping: 127.0.0.1; id; head -2 /etc/passwd: Name or service not known` — one
unresolvable hostname, no `id`, no `/etc/passwd`. Evidence:
[`evidence/after/part3_cmdinjection_blocked.txt`](evidence/after/part3_cmdinjection_blocked.txt).

## Part 4 — real features still work

`alice` / `alicepw` logs in (302 → dashboard 200); a plain `127.0.0.1` ping still
returns its normal output. Evidence:
[`evidence/after/part4_normal_features.txt`](evidence/after/part4_normal_features.txt).

## Data integrity / lesson

The UNION demo used `id = 1`, so the fabricated legacy row's successful login wrote
its upgrade hash to the real admin row. I reset the password to `admin123` and
verified a fresh admin login; the stored hash is now Argon2id, not the original seed
plaintext. A non-destructive demo uses a non-existent id (e.g. `999`). No
notes/classes/enrollments were modified.

## Tests

`pytest -q` → **102 passed** ([`evidence/after/pytest.txt`](evidence/after/pytest.txt)),
coverage: `password_storage.py` 100%, `app.py` 84%, total 88% (uncovered lines are
mostly other routes/flaws kept for later classes).

- `tests/test_command_injection.py` (new): `;`, `$()` and backtick payloads run no
  second command; `/admin/ping` requires an admin session.
- `tests/test_password_login.py`: the obsolete test that asserted the old SQL
  `Query error` symptom was replaced — a lone quote is now literal data and no error
  leaks; a new test confirms the UNION payload cannot forge an admin login.

The command-injection tests are negative controls (no `uid=`, no `/etc/passwd`); the
positive control for a normal ping is the Part 4 evidence above.

## Scope and honesty

Only flaws #8 and #9 were changed. Other intentional teaching flaws (e.g. #11 no CSRF
on the ping box, #13 the container runs as root and mounts the Docker socket) remain.
The raw `Query error:` text is still echoed on unexpected database failures; that is
a separate information-disclosure flaw, not the injection point. Predictions and
reasoning for each part are in [`prediction.md`](prediction.md). The `pwned` password
and `admin123` are seed/demo values, not real secrets.

## Reproduce

```bash
docker compose -f docker-compose.yml -f compose.windows.yml up -d --build
# app on http://localhost:8080 ; admin/admin123, alice/alicepw
python -m pip install -r requirements-dev.txt
pytest -q
```

The fixed code is commit `420132e`.
