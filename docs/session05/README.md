# Class 5 - NotesApp Security Audit

**Full name:** 陈子明 Chen Ziming

**CHU student ID:** 2023905333

**Lab partner (full name):** 吴彦澜 Wu Yanlan

**Lab partner CHU student ID:** 2023905420

**Date:** 22 October 2026

[Combined formal report](NotesApp_Class5_Combined_Report.pdf)

## Scope

Lab 1 audits login traffic on our own local NotesApp; Lab 2 tests six generated course MD5 accounts and upgrades the real application's legacy login storage. Captures are loopback-only. No third-party targets were tested.

## Lab 1 - Traffic in transit

**Finding 1: HTTP login exposure.** POST /login on port 8080 transmitted `username=alice&password=alicepw` in readable form (packet 348, TCP stream 9; response 350 was HTTP 302). An observer who can intercept that connection could recover the credentials. **Severity: High**, because they could be used to log in.

**Fix and verification.** nginx now serves HTTPS; the direct Flask port 8080 is no longer published. HTTP / and /login redirect with 301 to HTTPS. The re-capture contains 75 packets, TLS 1.3, TCP stream 6. Searches of all reassembled TCP streams found no plaintext login credentials; no TLS keys were supplied. Successful HTTPS login is supported by the dashboard and access records. See [capture and evidence details](lab1/results/audit-evidence.json), [HTTP capture](lab1/results/login-http.pcapng), [HTTPS capture](lab1/results/login-https.pcapng).

**Finding 2: Certificate trust.** GitHub's observed issuer was Sectigo Public Server Authentication CA DV E36, chained to Sectigo Public Server Authentication Root E46. The local certificate's subject and issuer are localhost; its chain contains only localhost. Edge reported `NET::ERR_CERT_AUTHORITY_INVALID`. **Verdict:** encryption protects content, but trusted server identity additionally requires certificate validation; a self-signed lab certificate is not automatically browser-trusted.

Optional redirect check passed. Optional wrong-domain test and cleanup back to plain HTTP were not performed.

## Lab 2 - Password storage

**Finding 1: Unsalted MD5.** The original prediction was 6/6 in 10 ms. The original interactive result was **4/6 in 0.1607 ms**, with 170 public-wordlist candidates. Recovered: liwei/123456, aisha/password1, tomk/qwerty123, sofia/iloveyou. marie/mariepw and raj/Gv7#pLm2!xQ were absent from the list. The attack hashes guesses and compares digests, rather than reversing MD5. **Severity: High:** offline guesses avoid online login controls. **Fix:** salted Argon2id hashes and upgrade on successful legacy login.

The actual app had plaintext legacy storage. The six-account MD5 dump was a separate course model. See [original MD5 result](lab2/results/md5-run.json).

**Finding 2: The fix, measured.** The predicted slowdown was about 10 times.

| Hash | Estimated guesses/second | Estimated guesses/day |
| --- | ---: | ---: |
| MD5 | 3,336,597 | 288,282,016,688 |
| Argon2id | 27.105 | 2,341,905 |

Argon2 took 36.893 ms for one fresh hash, about 123,097 times slower per operation. Both algorithms were measured in the same Python 3.11.17 web container: 100,000 MD5 hexdigests then one fresh Argon2 hash. Argon2id used 64 MiB, time cost 3, parallelism 4, a random 16-byte salt and 32-byte output.

Daily figures multiply rates by 86,400; they are estimates, not measured 24-hour attacks. The hash-generation benchmark is a guess-cost proxy, not optimized cracking or universal GPU speed. Five subsequent fresh hashes had a median of 32.051 ms; five existing-hash verifications had a median of 31.058 ms. **Verdict:** Argon2 increases each guess's cost substantially, but common passwords may still be recovered. See [raw benchmark](lab2/results/hash-benchmark.json).

**Migration verified.** The prediction was that alice would store a hash. A successful login replaced alicepw with an encoded value beginning `$argon2id$v=19$m=65536,t=3,p=4$`. Wrong passwords were rejected before and after migration. Logout and second correct login succeeded without changing the stored hash. Only alice.password changed; 34 other users and all non-user table digests were unchanged. See [actual SQL output](lab2/results/alice-storage.txt), [live verification](lab2/results/live-migration.json), [preservation](lab2/results/database-preservation.json).

**Final state:** HTTPS and Argon2id login are enabled. Alice is migrated; 34 of 35 accounts await successful login. New-account creation and other teaching flaws are outside this change. The course-required username SQL concatenation remains.

**Optional extension:** adding six `<username>pw` guesses yielded 5/6 in 0.1728 ms, additionally recovering marie. Raj remained unmatched in these 176 candidates. This does not replace the 4/6 baseline. See [rule result](lab2/results/rule-run.json).

## Evidence and checks

- [HTTP stream](lab1/evidence/01_http_plaintext.jpg), [TLS packets](lab1/evidence/09_tls_packets.jpg), [encrypted stream](lab1/evidence/02_https_ciphertext.jpg).
- [GitHub certificate](lab1/evidence/03_github_certificate.jpg), [local certificate](lab1/evidence/06_localhost_certificate.jpg), [browser warning](lab1/evidence/05_localhost_warning.jpg).
- [Original MD5 terminal screenshot](lab2/evidence/01_md5_dictionary_attack.jpg), [first login](lab2/evidence/02_alice_first_login.png), [wrong password](lab2/evidence/03_wrong_password_denied.png), [second login](lab2/evidence/04_alice_second_login.png).
- 15 password checks and 75 existing comment/HMAC checks passed; the password helper has 100% statement and branch coverage. [Implementation records](lab2/results/implementation-checks.json), [patch](lab2/implementation/password-storage.patch).

PDF image excerpts are clipped views of original screenshots; source bytes are preserved. Interactive captures and the initial dictionary run are distinguished from automated local Edge/benchmark checks. The automation accepted the local self-signed certificate only; it did not validate a public CA chain.

[Source inventory](source-manifest.json) records the source archives and copied file digests. No measurements were rerun for this combined edition. Private keys and private backups are excluded.

## Course sources

[Lab 1 - Traffic-in-transit audit](https://kristenpire.github.io/epita-security-labs/class5/https-lab/); [Lab 2 - Password storage audit](https://kristenpire.github.io/epita-security-labs/class5/password-audit/).

## Run the submitted application

The root `web/`, `tests/`, `nginx/nginx.conf` and `docker-compose.https.yml` contain
the current implementation. The `lab1/` and `lab2/` directories preserve the
measured evidence. The public certificate in `lab1/configuration/` is historical
evidence; its private key is not supplied.

Prerequisites: Docker Desktop with Compose support for `!reset`, Python, and
OpenSSL on PATH. From the repository root on Windows, initialize the existing
comment and HMAC keys, then generate a new local TLS identity:

```powershell
.\Initialize-CommentKey.ps1
.\Initialize-ExportKey.ps1
New-Item -ItemType Directory -Force nginx/certs | Out-Null
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certs/notesapp.key -out nginx/certs/notesapp.crt -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
docker compose -p noteapp -f docker-compose.yml -f compose.windows.yml -f docker-compose.https.yml up -d --build --wait --wait-timeout 180
```

Generate the TLS pair once per clone, not on every restart. If OpenSSL uses an
installation-specific configuration, set `OPENSSL_CONF` to that installation's
configuration file. The runtime certificate and key are Git-ignored.

Open `https://localhost/login`; the fresh self-signed lab certificate produces a
browser trust warning. On a fresh course database, `alice` / `alicepw` migrates
on its first successful login. On an existing database, successful login verifies
the stored hash if already migrated. Do not reset the database to reproduce a
historical first-login screenshot. The existing plain-HTTP Windows launcher does
not select the HTTPS overlay.

Install `requirements-dev.txt` in a development environment and run from the root:

```powershell
python -m pytest -q --cov=export_hmac --cov=comment_crypto --cov=comment_migration --cov=password_storage --cov-branch --cov-report=term-missing --cov-fail-under=95
```

PostgreSQL must be available on the local course port 15432. Tests create and
remove their own disposable databases. For script entry points in this repository
layout, see [Lab 2 reproduction](lab2/README.md).
