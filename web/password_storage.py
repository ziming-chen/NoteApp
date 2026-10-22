"""Check Argon2 passwords and upgrade successful legacy logins."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ph = PasswordHasher()


def check_password(stored: str, submitted: str) -> tuple[bool, str | None]:
    """Return authentication status and an optional replacement legacy hash."""
    if stored.startswith("$argon2"):
        try:
            ph.verify(stored, submitted)
        except (InvalidHashError, VerificationError):
            return False, None
        return True, None

    # A successful legacy login is upgraded once; failed guesses never change it.
    if stored == submitted:
        return True, ph.hash(submitted)
    return False, None
