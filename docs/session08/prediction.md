# Prediction before the baseline request

Alice's login should succeed, and note 1 should return her own grade. I expect
changing the path to note 3 with the same session to return Bob's seeded grade.
The Class 7 handler authenticates the request and selects the row by note ID.
Its source has no condition that compares the row owner with the caller.
