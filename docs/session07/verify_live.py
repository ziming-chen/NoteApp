"""Replay the Class 6 tokens against the local HTTPS stack and check Alice's login."""

import argparse
import hashlib
import http.cookiejar
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://localhost"


def request(client, path, *, token=None, data=None):
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
    try:
        response = client.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.geturl(), response.read().decode()


def check_note(client, path, expected, token=None):
    status, _, body = request(client, path, token=token)
    parsed = json.loads(body)
    assert status == expected, (path, status, expected)
    if status == 401:
        assert parsed == {"error": "unauthorized"}
        return {"status": status, "body": parsed}
    return {
        "status": status,
        "note_id": parsed["id"],
        "student": parsed["student"],
        "grade": parsed["grade"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("baseline", "hs256-only", "final"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tokens", type=Path, required=True)
    args = parser.parse_args()

    # Class 5 uses a self-signed certificate on this fixed loopback endpoint.
    tls = urllib.request.HTTPSHandler(context=ssl._create_unverified_context())
    direct = urllib.request.build_opener(tls)
    cookie_client = urllib.request.build_opener(
        tls, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    results = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "stage": args.stage,
        "base_url": BASE_URL,
        "forged_token_target": "/api/notes/3",
        "no_credentials": check_note(direct, "/api/notes/3", 401),
    }
    for label, filename, expected in (
        ("unsigned_teacher", "forged-token.txt", 200 if args.stage == "baseline" else 401),
        ("old_key_teacher", "signed-token.txt", 401 if args.stage == "final" else 200),
    ):
        token = (args.tokens / filename).read_text(encoding="utf-8-sig").strip()
        results[label] = check_note(direct, "/api/notes/3", expected, token)
        results[label]["token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        if expected == 200:
            assert results[label]["student"] == "bob"

    if args.stage == "final":
        data = urllib.parse.urlencode({"username": "alice", "password": "alicepw"}).encode()
        status, url, dashboard = request(cookie_client, "/login", data=data)
        assert (status, url) == (200, BASE_URL + "/dashboard") and "My grades" in dashboard
        token = json.loads(re.search(r"const TOKEN = (.+?);", dashboard).group(1))
        note_id = re.search(r'id="noteId"[^>]* value="(\d+)"', dashboard).group(1)
        own_note = f"/api/notes/{note_id}"
        results["alice_dashboard"] = {"status": status, "path": "/dashboard"}
        results["alice_new_bearer_only"] = check_note(direct, own_note, 200, token)
        assert results["alice_new_bearer_only"]["student"] == "alice"
        results["alice_cookie_only"] = check_note(cookie_client, own_note, 200)
        results["alice_cookie_with_invalid_bearer"] = check_note(
            cookie_client, own_note, 401, "invalid"
        )
        old_alice = (args.tokens / "alice-token.txt").read_text(encoding="utf-8-sig").strip()
        results["alice_pre_rotation_bearer"] = check_note(direct, own_note, 401, old_alice)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"{args.stage} checks passed: {args.output}")


if __name__ == "__main__":
    main()
