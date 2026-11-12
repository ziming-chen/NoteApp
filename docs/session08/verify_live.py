"""Exercise the Class 8 API through HTTP against the local seeded NotesApp."""

import argparse
import json
import re
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = "http://127.0.0.1:8080"
NOT_FOUND = {"error": "not found"}
UNAUTHORIZED = {"error": "unauthorized"}


def request(client, path, *, form=None, token=None, landing_page=None):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    data = urlencode(form).encode("ascii") if form else None
    try:
        response = client.open(Request(BASE + path, data, headers), timeout=10)
    except HTTPError as error:
        response = error
    with response:
        if landing_page is not None:
            assert response.url == BASE + landing_page, f"Unexpected login redirect: {response.url}"
        return response.status, response.read()


def sign_in(username, password, landing_page, marker):
    cookies = CookieJar()
    client = build_opener(HTTPCookieProcessor(cookies))
    status, body = request(
        client,
        "/login",
        form={"username": username, "password": password},
        landing_page=landing_page,
    )
    assert status == 200 and marker in body, f"{username} login failed"
    assert any(cookie.name == "session" for cookie in cookies)
    return client, body, {"username": username, "landing_page": landing_page, "status": status}


def read_note(results, client, caller, credential, note_id, *, token=None):
    path = f"/api/notes/{note_id}"
    status, body = request(client, path, token=token)
    payload = json.loads(body)
    results.append(
        {"caller": caller, "credential": credential, "path": path, "status": status, "body": payload}
    )
    return status, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("before", "after"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    alice, dashboard, alice_login = sign_in("alice", "alicepw", "/dashboard", b"My grades")
    match = re.search(rb'const TOKEN = "([^"]+)"', dashboard)
    assert match, "Alice's dashboard did not render a bearer credential"
    token = match[1].decode("ascii")
    anonymous = build_opener()
    results = []
    logins = [alice_login]

    for note_id in range(1, 11):
        status, payload = read_note(results, alice, "alice", "cookie", note_id)
        if args.stage == "before" or note_id <= 2:
            assert status == 200 and payload["id"] == note_id
            assert (payload["student"] == "alice") == (note_id <= 2)
        else:
            assert (status, payload) == (404, NOT_FOUND)
    status, own = read_note(results, anonymous, "alice", "bearer", 1, token=token)
    assert status == 200 and own == results[0]["body"]
    cross = read_note(results, anonymous, "alice", "bearer", 3, token=token)
    if args.stage == "before":
        assert cross == (200, results[2]["body"])
        assert cross[1]["student"] == "bob"
    else:
        assert cross == (404, NOT_FOUND)

    assert read_note(results, alice, "alice", "cookie", 99999) == (404, NOT_FOUND)
    assert read_note(results, anonymous, "anonymous", "none", 3) == (401, UNAUTHORIZED)
    assert read_note(
        results, alice, "alice", "invalid bearer + cookie", 3, token="invalid"
    ) == (401, UNAUTHORIZED)

    if args.stage == "after":
        for username, password, landing_page, marker, note_id, owner in (
            ("bob", "bobpw", "/dashboard", b"My grades", 3, "bob"),
            ("prof.turing", "teach123", "/teacher", b"Solid work, keep it up.", 3, "bob"),
            ("admin", "admin123", "/admin", b"<h1>Users</h1>", 3, "bob"),
        ):
            client, _, login = sign_in(username, password, landing_page, marker)
            logins.append(login)
            status, payload = read_note(results, client, username, "cookie", note_id)
            assert status == 200 and payload["student"] == owner and payload["id"] == note_id
            if username == "bob":
                assert read_note(results, client, username, "cookie", 1) == (404, NOT_FOUND)

    record = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "stage": args.stage,
        "logins": logins,
        "requests": results,
    }
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{args.stage}: {len(results)} API checks passed")


if __name__ == "__main__":
    main()
