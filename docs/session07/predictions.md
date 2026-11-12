# Pre-test predictions

Recorded before editing or running the Class 7 experiment, 12 November 2026.
This is the experiment prediction for an individual run.

- Will the old unsigned teacher token work after both fixes? **No.** The verifier will require HS256 and a matching signature.
- Will the old teacher token signed with the cracked secret work? **No.** Its HMAC was computed with the old key.
- Will normal Alice login work? **Yes.** Login will sign new tokens with the same key that the verifier uses.
