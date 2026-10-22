"""Show authentic and modified CSV checks with a temporary in-memory key."""

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT / "web"))
from export_hmac import ExportAuthenticator, ExportIntegrityError  # noqa: E402


def main():
    authenticator = ExportAuthenticator(os.urandom(32))
    original = b"student,class,grade,comment\r\nalice,Math,14,good work\r\n"
    exported = authenticator.sign(original)
    assert authenticator.verify(exported) == original
    print("Original CSV: verification passed")
    modified = exported.replace(b",14,", b",18,", 1)
    try:
        authenticator.verify(modified)
    except ExportIntegrityError:
        print("Grade changed from 14 to 18: verification failed as expected")
    else:
        raise AssertionError("A modified grade was unexpectedly accepted.")
    print("The temporary key was not printed or saved. No database was used.")


if __name__ == "__main__":
    main()
