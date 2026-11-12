# Class 8 — Read anyone's grade

**Chen Ziming (陈子明) · CHU student ID 2023905333**

**12 November 2026 · Local NotesApp clone with course seed data**

## Proof of access before the fix

I signed in as Alice and kept her session cookie. Changing the requested note
from 1 to 3 returned Bob's Mathematics grade, **12.6**, and the comment
**“Solid work, keep it up.”** The response was HTTP 200 and identified
`student: bob`, `student_id: 7`. With the same Alice session, notes 1 and 2
belonged to Alice and notes 3 through 10 belonged to other seeded students.
All ten requests returned 200 before the fix.
[Pre-test prediction](prediction.md) · [Before-fix HTTP responses](evidence/before.json)

## Fix and proof

The original `api_notes` authenticated the caller and queried a note by ID.
The query had no ownership restriction. The fixed handler compares the note's
`student_id` with the authenticated caller's `user_id`. The `teacher` and
`admin` roles may read any note under the course policy. The guard runs
before comment decryption and JSON serialization. [Code patch](fix-idor.patch)

```python
    if (
        note["student_id"] != ident.get("user_id")
        and ident.get("role") not in ("teacher", "admin")
    ):
        return jsonify({"error": "not found"}), 404
```

I chose **404 Not Found**. An existing note outside the caller's permissions
and an absent note have the same status and JSON body, so these responses
give the caller no explicit indication that a blocked note exists.

| Caller and request | Before | After |
| --- | --- | --- |
| Alice, cookie, `GET /api/notes/3` | 200, Bob's 12.6 and comment | 404, `{"error":"not found"}` |
| Alice, cookie, `GET /api/notes/1` | 200, Alice's 16.2 | 200, Alice's 16.2 |
| Alice, bearer, `GET /api/notes/3` | 200, Bob's 12.6 and comment | 404, `{"error":"not found"}` |
| Alice, cookie, `GET /api/notes/99999` | 404, `{"error":"not found"}` | 404, `{"error":"not found"}` |
| Bob, cookie, `GET /api/notes/3` | — | 200, Bob's 12.6 |
| prof.turing, cookie, `GET /api/notes/3` | — | 200, Bob's 12.6 |
| admin, cookie, `GET /api/notes/3` | — | 200, Bob's 12.6 |
| Anonymous, `GET /api/notes/3` | 401, `{"error":"unauthorized"}` | 401, `{"error":"unauthorized"}` |

The teacher's `/teacher` page returned 200 and displayed Bob's seeded
comment. Alice's dashboard and bearer-only request for note 1 still worked.
An invalid bearer credential returned 401 even when Alice's cookie was present.
[After-fix HTTP responses](evidence/after.json) · [98 passing application tests](evidence/pytest.txt)

The verified scope is the note-detail endpoint with authenticated identities
and seeded accounts. The development Flask session signing key remains a
separate risk because session claims are trusted by the ownership check.

## Reproduce on Windows

From the NotesApp root, use the Class 7 baseline `3520711` for the before run.
Set `JWT_SECRET` to a long random value in the shell or Git-ignored `.env`
and initialize the local comment and export keys. The commands use an
independent Compose project and a loopback HTTP binding.

```powershell
if (-not (Test-Path .env)) {
    python -c "from pathlib import Path; import secrets; Path('.env').open('x').write('JWT_SECRET=' + secrets.token_urlsafe(32) + chr(10))"
}
powershell -NoProfile -ExecutionPolicy Bypass -File Initialize-CommentKey.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File Initialize-ExportKey.ps1
docker compose -p noteapp-session08 -f docker-compose.yml -f compose.windows.yml up -d --build --wait
```

Use the extracted verifier path when running the before test from the
baseline. Apply `fix-idor.patch` from the same extracted folder to the baseline
checkout, then rebuild. A checkout with the Class 8 commit already contains
the fix, so start at the rebuild and run the after test.

```powershell
# Baseline, with $lab set to the extracted lab folder.
python "$lab/verify_live.py" before before-recheck.json
git apply "$lab/fix-idor.patch"
docker compose -p noteapp-session08 -f docker-compose.yml -f compose.windows.yml up -d --build --wait
python "$lab/verify_live.py" after after-recheck.json
docker compose -p noteapp-session08 -f docker-compose.yml -f compose.windows.yml down
```

[EPITA Class 8 lab instructions](https://kristenpire.github.io/epita-security-labs/class8/read-anyones-grade/)
