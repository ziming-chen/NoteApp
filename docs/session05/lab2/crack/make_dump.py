"""Create the six-account, unsalted-MD5 dataset specified by the course lab."""

import hashlib
from pathlib import Path


ACCOUNTS = {
    "liwei": "123456",
    "sofia": "iloveyou",
    "tomk": "qwerty123",
    "aisha": "password1",
    "marie": "mariepw",
    "raj": "Gv7#pLm2!xQ",
}


def main():
    destination = Path(__file__).resolve().parent / "leaked_users.txt"
    lines = [
        f"{username}:{hashlib.md5(password.encode('utf-8')).hexdigest()}"
        for username, password in ACCOUNTS.items()
    ]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {len(ACCOUNTS)} simulated course accounts: {destination}")


if __name__ == "__main__":
    main()
