# Lab 1 - Traffic in transit

**Full name:** 陈子明 Chen Ziming - **CHU student ID:** 2023905333

**Lab partner:** 吴彦澜 Wu Yanlan - **CHU student ID:** 2023905420

The [combined findings sheet](../README.md#lab-1---traffic-in-transit) and
[formal PDF](../NotesApp_Class5_Combined_Report.pdf) cover the plaintext login,
HTTPS re-capture and certificate comparison.

- [HTTP capture](results/login-http.pcapng): packet 348, TCP stream 9;
  `username=alice&password=alicepw` is readable.
- [HTTPS capture](results/login-https.pcapng): 75 packets, TLS 1.3, TCP stream 6;
  no readable login credentials were found without TLS session keys.
- [Audit evidence](results/audit-evidence.json) records the packet references,
  issuer observations, redirects and database preservation checks.
- `configuration/` contains the public configuration and certificate observed
  during the audit; the private key is excluded.

The original screenshot bytes are preserved under `evidence/`.
