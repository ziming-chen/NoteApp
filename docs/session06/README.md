# NotesApp JWT Forgery — Class 6 Lab ("Forge a token")

**Full name:** 陈子明 Chen Ziming  
**CHU student ID:** 2023905333  
**Date of run:** 29 October 2026  
**Scope:** my own NotesApp clone at `https://localhost` (Docker: `noteapp-web-1`, `noteapp-db-1`, `noteapp-nginx-1`). No other host or account was touched.  
**Work mode:** the exercise is designed for pairs; this run was executed and recorded individually on my own clone.  

## Finding

```text
FORGED-TOKEN FINDING — NotesApp flaw #4 (auth)
  What I read:   bob's grade (12.6) and comment ("Solid work, keep it up."), via /api/notes/3
  Break 1:       a JWT with "alg":"none" and no signature; role set to "teacher"
  Break 2:       cracked the HS256 secret (s3cr3t) from a wordlist; signed a real teacher token
  Why it worked: the server let the TOKEN choose how to verify, AND its secret was guessable
```

## What the exercise asked

The Class 6 lab has two parts, about 25 minutes in total:

| Part | Task |
| --- | --- |
| 1 | Forge a JWT with `"alg": "none"` and no signature, set `role` to `teacher`, and read a grade that is not mine. |
| 2 | The lab poses this as a hypothesis — *suppose the server is fixed to reject `alg:none`* — and asks whether a teacher token can still be forged: guess the HS256 secret from the course wordlist, then sign a genuine teacher token. |

The deliverable is the four-line finding above — not a transcript of commands.

### Predictions (not recorded)

The lab asks for a written yes/no prediction, with a reason, before each part. **No prediction record was found for either part:** the shell history around the 27 October attempt contains only endpoint probes, the base64 helper and the `curl` — no prediction line — and this folder has no note written before the 29 October run. Both prediction records are therefore missing from the materials reviewed, and this report does not reconstruct them after the fact — a prediction written afterwards would not be a prediction.

The lab's "What you hand in" section lists only the finding, so the missing prediction does not remove part of the deliverable; it does mean the exercise was not followed exactly as written.

## Method and results

### Setup

`alice` / `alicepw` (student, `user_id` 6) logs in through `https://localhost`; the dashboard renders its JWT into the page (`const TOKEN = ...`), which gives a real, correctly signed token to work from.

The lab's own instructions start the base stack with `docker compose up -d` and use `http://localhost:8080`. This clone already carries the Class 5 HTTPS overlay (nginx 1.27 + self-signed certificate), so the same Flask app, routes, database and token format are reached at `https://localhost` on 443, with `-k` accepting the self-signed certificate. The material differences from the lab text are that TLS overlay and the PowerShell shell.

### Part 1 — no signature at all

```powershell
$header  = To-Base64Url '{"alg":"none","typ":"JWT"}'
$payload = To-Base64Url '{"user_id":9999,"username":"attacker","role":"teacher"}'
$forged  = "$header.$payload."          # note the trailing dot: empty signature
curl.exe -k -H "Authorization: Bearer $forged" https://localhost/api/notes/3
```

| Request | Status | Body |
| --- | --- | --- |
| `GET /api/notes/3` with the unsigned forged token | **200 OK** | `id 3`, `student bob`, `class Mathematics`, `grade 12.6`, `comment "Solid work, keep it up."` |

The same endpoint answered `401` on 27 October without any token (`08:38:52 UTC`), and an empty `Bearer` value also returned `401` during the 29 October run (`13:34:20`). The `200` above therefore comes from the token, not from an open endpoint.

### Part 2 — real signature, guessed secret

The course wordlist (`class6/assets/jwt-secrets.txt`, 15 candidates) is tried against alice's real token: for each candidate, HMAC-SHA-256 over `header.payload` must reproduce the token's signature.

| Measurement | Value |
| --- | --- |
| Secret found | `s3cr3t` |
| Candidate position | 8 of 15 |
| Candidates tried | 8 |
| Time | 53 microseconds (~150,000 guesses/second in pure Python) |

With the secret, a new HS256 token claiming `"role": "teacher"` is signed and replayed:

| Request | Status | Body |
| --- | --- | --- |
| `GET /api/notes/3` with the signed forged token | **200 OK** | identical record: bob, 12.6, "Solid work, keep it up." |

On a server that rejected **only** `alg:none` — the hypothesis the lab states for Part 2 — this second token would still pass: its signature is genuine, only the identity inside it is invented. That is an inference from how HS256 verification works, **not a measurement**: the running app has no `none` rejection, so no "reject none" server was tested here.

## Why it worked

1. **The token chooses the verification rule.** `verify_jwt()` in `web/app.py` reads `alg` from the token's own header; `"none"` returns the payload without any signature check. The attacker writes the instruction that tells the server whether to check.
2. **The secret is a word.** `JWT_SECRET` is `s3cr3t`, six characters in leetspeak and present in a public list. A signature is only as strong as the key behind it. The lab page notes that pure brute force on six lowercase/digit characters is roughly two hours on a laptop — still nothing for an attacker; a random 256-bit key would not be reachable this way.
3. **The API also does not check ownership** (flaw #7, IDOR): any authenticated caller can read any note id. That is a separate defect, not fixed here.

## Evidence

| File | Content |
| --- | --- |
| [finding](finding.txt) | the four-line deliverable |
| [evidence/forged-token.txt](evidence/forged-token.txt) | Part 1 token; signature slot empty |
| [evidence/part1-headers.txt](evidence/part1-headers.txt), [evidence/part1-body.json](evidence/part1-body.json) | Part 1 response: 200, 158 bytes, bob's record |
| [evidence/alice-token.txt](evidence/alice-token.txt), [evidence/alice-token-decoded.txt](evidence/alice-token-decoded.txt) | the real student token used for the crack |
| [evidence/crack-result.json](evidence/crack-result.json) | secret, candidate index, timing, decoded header/payload |
| [evidence/signed-token.txt](evidence/signed-token.txt) | Part 2 token with a genuine HS256 signature |
| [evidence/part2-headers.txt](evidence/part2-headers.txt), [evidence/part2-body.json](evidence/part2-body.json) | Part 2 response: 200, 158 bytes, same record |
| [evidence/run-server-evidence.txt](evidence/run-server-evidence.txt) | Flask and nginx logs for both requests (UTC) |
| [evidence/previous-attempt-20261027.txt](evidence/previous-attempt-20261027.txt) | server log of my in-class attempt on 27 October |
| [evidence/compose-up.txt](evidence/compose-up.txt) | stack start-up output |
| [evidence/run.log](evidence/run.log) | step-by-step console log of this run |
| [scripts/crack.py](scripts/crack.py), [scripts/sign.py](scripts/sign.py) | the two helpers, with no hard-coded secret |
| [verification.json](verification.json) | 15 automated checks and SHA-256 of every evidence file |

## Verification

| Check | Result |
| --- | --- |
| Automated checks (`verification.json`) | 15 / 15 passed |
| Part 1 / Part 2 status codes | 200 / 200, both `Content-Length: 158` |
| Server log cross-check | nginx records both requests as 200 with 158 bytes |
| Cracked secret verifies alice's original signature | yes |
| Signed token signature verifies with the cracked secret | yes |
| Database row counts | read-only `psql` query during the run (the query output was not archived as a separate file): 35 users, 4 classes, 60 notes, 60 enrollments, matching the 22 October baseline; note 3 is still `student_id 7`, `grade 12.6` |
| Requests during the run | login and `GET /api/notes/3` are recorded (see [evidence/run.log](evidence/run.log)); the recorded row counts do not prove byte-for-byte database identity |
| alice password storage | prefix still `$argon2id$`; the pre-run hash value was not captured, so this shows the row was not replaced by a legacy value, not a byte-for-byte identity check |

## Note on the earlier attempt (27 October)

My shell history ends with the forged `alg:none` `curl`, and that history file was last written at `09:39:23` local time on 27 October. The server logged a `200` with a `158`-byte body at `08:39:23 UTC` — the same second — after a `401` at `09:38:52` local for a request without a token. The application and nginx logs do **not** record the `Authorization` header, so the log alone cannot prove which token was sent; the timestamp match with the forged-token command, plus the `158`-byte length being the same as the note JSON captured on 29 October, make it very likely that Part 1 succeeded. The response body was not saved, Part 2 was not run, and nothing was handed in. The two log lines are preserved in [evidence/previous-attempt-20261027.txt](evidence/previous-attempt-20261027.txt); the complete run above was made on 29 October 2026.

## Limits

- Only `note id 3` was requested, as the lab specifies; the "try one more" extension (reading other ids) was not run.
- No fix was applied. The three fixes (reject `none`, pin `HS256`, long random secret) belong to the next class; `verify_jwt()` still returns the payload for `alg:none`, `web/app.py` is unchanged, and `NoteApp` has no commit after 22 October.
- The lab page names no submission channel (no Moodle, email or Git step); teacher receipt and grading have not been verified.
- The lab asks to bring the forged token to the next class so that each fix can reject it; [evidence/forged-token.txt](evidence/forged-token.txt) is kept for that.
- **Deviations from the lab text:** HTTPS on 443 through the Class 5 overlay (the lab uses HTTP/8080); executed solo rather than in a pair; the wordlist is stored in `evidence/jwt-secrets.txt` instead of next to the clone; the cleanup step (`docker compose down`) was not run after the recorded run, so the containers were simply left up and the database volume was never dropped.
- No prediction record was found for either part; see [Predictions](#predictions-not-recorded). It is reported as missing, not reconstructed.
- The result says nothing about the real service behind the course website; only this local clone was tested.
