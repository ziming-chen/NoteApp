# Class 7 — Fix the Login

**Chen Ziming (陈子明) · CHU student ID 2023905333**

**12 November 2026 · Individual run on my local NotesApp clone**

The submission consists of the fixed `verify_jwt` in `web/app.py`, its secret configuration in `docker-compose.yml`, and the [audit](audit.txt). The standalone submission archive includes a Git patch against `04b3e01`.

## Audit

| Live test on `https://localhost` | Original | HS256 pinned, old key | HS256 pinned, new key |
| --- | --- | --- | --- |
| Original Class 6 unsigned teacher token on `GET /api/notes/3` | 200, Bob's note | 401, unauthorized | 401, unauthorized |
| Original Class 6 `s3cr3t`-signed teacher token on the same route | 200, Bob's note | 200, Bob's note | 401, unauthorized |
| Fresh Alice login followed by her dashboard and a bearer-only request for note 2 | — | — | 200 dashboard, 200 Alice's note |

The two final 401 responses each contained `{"error":"unauthorized"}`. The bearer-only request used the token rendered by Alice's dashboard and a separate client without the session cookie. A cookie-only request for Alice's note also returned 200. An invalid Bearer credential returned 401 even with Alice's valid cookie. Alice's saved pre-rotation bearer token returned 401.

See the [pre-test predictions](predictions.md) and the [original](evidence/baseline.json), [HS256-only](evidence/hs256-only.json) and [final](evidence/final.json) response records. The token digests identify the same Class 6 inputs across all three stages.

## Implementation

- `verify_jwt` requires the exact `HS256` algorithm identifier. It computes HMAC-SHA-256 over the encoded header and payload, uses `hmac.compare_digest`, and returns the claims only after verification.
- `make_jwt` and `verify_jwt` share the required `JWT_SECRET` environment value. I generated the value with Python's `secrets.token_urlsafe(32)`. Compose reads it from the shell or a Git-ignored local `.env`. The [startup checks](evidence/startup-checks.txt) show that the app refuses to load without a key and rejects the old six-character value. Production deployments should inject the key from a secrets store.
- The grade API uses the cookie session when there is no Bearer credential. An invalid Bearer credential fails authentication. Re-login after rotation to replace the JWT cached in an existing browser session.

The run used the Class 5 HTTPS overlay and the existing PostgreSQL volume. The [before](evidence/database-before.txt) and [after](evidence/database-after.txt) snapshots contain matching row counts and digests for all five application tables. [Regression test output](evidence/pytest.txt) covers the JWT changes and earlier coursework. The grade API's missing per-note ownership check and the development Flask session key are separate teaching flaws.

## Reproduce

From the NotesApp repository root, initialize the local keys and start the Windows HTTPS stack. For a fresh checkout, the first command creates `.env` only if it is absent. The HTTPS overlay uses the local certificate and key described in `nginx/certs/README.md`.

```powershell
if (-not (Test-Path .env)) {
    python -c "from pathlib import Path; import secrets; Path('.env').open('x').write('JWT_SECRET=' + secrets.token_urlsafe(32) + chr(10))"
}
powershell -NoProfile -ExecutionPolicy Bypass -File Initialize-CommentKey.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File Initialize-ExportKey.ps1
docker compose -p noteapp -f docker-compose.yml -f compose.windows.yml -f docker-compose.https.yml up -d --build --wait
python docs/session07/verify_live.py final session07-recheck.json --tokens docs/session06/evidence
```

If using the standalone archive, run `git apply <path-to>/fix-the-login.patch` in the base checkout. In the final command above, replace `docs/session07/verify_live.py` with the path of the extracted script.

Source for the experiment and audit requirements. [EPITA Class 7 lab](https://kristenpire.github.io/epita-security-labs/class7/fix-the-login/)
