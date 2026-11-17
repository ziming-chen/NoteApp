# Class 9 — predictions (write before running)

The lab asks for a Yes/No guess with reasoning before each break-in.

## Part 1 — SQL injection on login (`admin' -- `)
- **Prediction: No, it will NOT log me in on this app.**
- Reasoning: this NotesApp was hardened in Class 5. The login SQL only looks up the
  user by name; the password is checked separately in Python (`check_password`,
  Argon2 with a legacy fallback). Commenting out the SQL `AND password = ...` does
  nothing here because there is no password clause in the SQL to comment out.
- Follow-up prediction: the injection point is still real, so a **UNION** that
  fabricates an admin row (with a password I choose) should log me in as admin.
  Prediction: **Yes**, UNION works.

## Part 3 — command injection on the ping box (`127.0.0.1; id`)
- **Prediction: Yes, it will run `id` and print `uid=0(root)`.**
- Reasoning: the host is glued into a shell string with `shell=True`, so `;` starts
  a second command.

## After the fixes
- Prediction: both payloads become inert. The UNION username matches no user; the
  ping payload becomes one unresolvable hostname. Real logins and plain pings keep
  working. **Yes.**

> Note: this file records the predictions made before the automated run-through.
> During the hands-on practice, write your own Yes/No next to each part as you go.
