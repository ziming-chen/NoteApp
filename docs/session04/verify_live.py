"""Verify live exports and uploads without writing any database records."""

import argparse
import csv
import hashlib
import http.cookiejar
import io
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from psycopg2 import sql

APP_ROOT = Path(__file__).resolve().parents[2]
ROOT = APP_ROOT.parent
sys.path.insert(0, str(APP_ROOT / "web"))
from comment_crypto import CommentCipher  # noqa: E402
from export_hmac import ExportAuthenticator  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
ORIGIN = "http://127.0.0.1:8080"
TABLES = ("users", "classes", "enrollments", "notes", "notesapp_crypto_state")


def digest(value):
    encoded = json.dumps(value, default=str, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def connect():
    return psycopg2.connect(
        host="127.0.0.1", port=15432, dbname="notesapp", user="notesapp",
        password="notesapp_pg_pw_2024", connect_timeout=5,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def snapshot():
    summary = {}
    with closing(connect()) as conn, conn.cursor() as cur:
        for table in TABLES:
            cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
            rows = cur.fetchall()
            rows.sort(key=lambda row: json.dumps(row, default=str, sort_keys=True))
            summary[table] = {"rows": len(rows), "sha256": digest(rows)}
    return summary


def save(name, value, exclusive=False):
    RESULTS.mkdir(parents=True, exist_ok=True)
    value = {**value, "checked_at_utc": datetime.now(timezone.utc).isoformat()}
    with (RESULTS / name).open("x" if exclusive else "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return value


def prepare():
    result = save("before.json", {"tables": snapshot()}, exclusive=True)
    print(json.dumps(result, indent=2))


def expected_records(class_id=None):
    cipher = CommentCipher.from_key_file(ROOT / ".secrets/notesapp-comment.key")
    with closing(connect()) as conn, conn.cursor() as cur:
        query = (
            "SELECT n.id, u.username AS student, c.name AS class, n.grade, n.comment "
            "FROM notes n JOIN users u ON u.id=n.student_id "
            "JOIN classes c ON c.id=n.class_id "
        )
        if class_id is not None:
            cur.execute(query + "WHERE c.id=%s ORDER BY u.username", (class_id,))
        else:
            cur.execute(query + "ORDER BY c.name,u.username")
        return [
            {"student": row["student"], "class": row["class"],
             "grade": str(row["grade"]) if row["grade"] is not None else "",
             "comment": cipher.decrypt(row["comment"], row["id"]) or ""}
            for row in cur.fetchall()
        ]


def request(opener, path, data=None, content_type=None):
    headers = {"Content-Type": content_type} if content_type else {}
    req = urllib.request.Request(ORIGIN + path, data=data, headers=headers)
    try:
        with opener.open(req, timeout=20) as response:
            return response.status, response.read(), response.url
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.url


def login(opener, role):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute("SELECT username,password FROM users WHERE role=%s ORDER BY id LIMIT 1", (role,))
        credentials = cur.fetchone()
    status, _, _ = request(
        opener, "/login", urllib.parse.urlencode(credentials).encode("utf-8"),
        "application/x-www-form-urlencoded",
    )
    assert status == 200


def upload(opener, content, csrf_token, filename="grades.csv"):
    boundary = "NotesAppCheck" + secrets.token_hex(16)
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="csrf_token"\r\n\r\n'
        f'{csrf_token}\r\n--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        'Content-Type: text/csv\r\n\r\n'
    ).encode("utf-8") + content + f'\r\n--{boundary}--\r\n'.encode("ascii")
    return request(opener, "/verify-export", body, "multipart/form-data; boundary=" + boundary)


def verify(after_restart=False):
    baseline = json.loads((RESULTS / "before.json").read_text(encoding="utf-8"))
    assert snapshot() == baseline["tables"], "Database differs from the pre-change baseline."
    auth = ExportAuthenticator.from_key_file(ROOT / ".secrets/notesapp-export-hmac.key")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    assert request(opener, "/healthz")[1] == b"ok"
    assert request(opener, "/verify-export")[2].endswith("/login")
    login(opener, "teacher")
    status, page, _ = request(opener, "/teacher")
    assert status == 200 and b'href="/verify-export"' in page
    status, page, _ = request(opener, "/verify-export")
    csrf_token = re.search(rb'name="csrf_token" value="([^"]+)"', page).group(1).decode("ascii")
    status, original, _ = request(opener, "/export.csv")
    assert status == 200
    original_csv = auth.verify(original)
    records = list(csv.DictReader(io.StringIO(original_csv.decode("utf-8"))))
    assert records == expected_records()
    class_counts = {}
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM classes ORDER BY id")
        class_ids = [row["id"] for row in cur.fetchall()]
    for class_id in class_ids:
        status, content, _ = request(opener, f"/export.csv?class_id={class_id}")
        rows = list(csv.DictReader(io.StringIO(auth.verify(content).decode("utf-8"))))
        assert status == 200 and rows == expected_records(class_id)
        class_counts[str(class_id)] = len(rows)
    assert sum(class_counts.values()) == len(records)

    if not after_restart:
        (RESULTS / "grades_original.csv").write_bytes(original)
        edited = [dict(row) for row in records]
        edited[0]["grade"] = str(float(edited[0]["grade"]) + 1)
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=["student", "class", "grade", "comment"])
        writer.writeheader()
        writer.writerows(edited)
        tampered = buffer.getvalue().encode("utf-8") + original[len(original_csv):]
        (RESULTS / "grades_tampered.csv").write_bytes(tampered)
        (RESULTS / "grades_unsigned.csv").write_bytes(original_csv)
    saved_original = (RESULTS / "grades_original.csv").read_bytes()
    assert auth.verify(saved_original) == original_csv
    checks = {}
    cases = {
        "original": (saved_original, 200),
        "changed_grade": ((RESULTS / "grades_tampered.csv").read_bytes(), 400),
        "missing_hmac": ((RESULTS / "grades_unsigned.csv").read_bytes(), 400),
        "trailing_data": (original + b"extra\r\n", 400),
        "wrong_key": (ExportAuthenticator(b"x" * 32).sign(original_csv), 400),
    }
    for name, (content, expected_status) in cases.items():
        status, page, _ = upload(opener, content, csrf_token)
        assert status == expected_status
        assert (b"Verification passed" if status == 200 else b"Verification failed") in page
        checks[name] = status
    assert upload(opener, original, "invalid")[0] == 400
    request(opener, "/logout")
    login(opener, "student")
    assert request(opener, "/verify-export")[2].endswith("/login")
    assert request(opener, "/dashboard")[0] == 200
    after = snapshot()
    assert after == baseline["tables"]
    result = save(
        "restart_verification.json" if after_restart else "live_verification.json",
        {"transport": "HTTP to the running Docker application", "origin": ORIGIN,
         "after_container_restart": after_restart, "tables_unchanged": True,
         "tables": after, "full_export_rows": len(records), "class_export_rows": class_counts,
         "export_records_match_database": True, "verification_http_status": checks,
         "csrf_invalid_rejected": True, "anonymous_and_student_rejected": True,
         "teacher_and_student_pages_work": True, "saved_export_still_verifies": True},
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "verify", "restart"])
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    else:
        verify(after_restart=args.action == "restart")
