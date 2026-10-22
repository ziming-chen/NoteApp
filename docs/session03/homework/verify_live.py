"""Back up and verify the local NotesApp without changing its records."""

import argparse
import collections
import csv
import hashlib
import http.cookiejar
import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

APP_ROOT = Path(__file__).resolve().parents[3]
COURSE_ROOT = APP_ROOT.parent
sys.path.insert(0, str(APP_ROOT / "web"))
from comment_crypto import CommentCipher  # noqa: E402
from export_hmac import ExportAuthenticator  # noqa: E402

PRIVATE = COURSE_ROOT / ".secrets/backups"
RESULTS = Path(__file__).resolve().parent / "results"
BASELINE = PRIVATE / "session03-baseline.json.aesgcm"
TABLES = ("users", "classes", "enrollments", "notes")
KEY_PATH = COURSE_ROOT / ".secrets/notesapp-comment.key"


def canonical(value):
    return json.dumps(value, default=str, sort_keys=True).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def connect():
    return psycopg2.connect(
        host="127.0.0.1",
        port=15432,
        dbname="notesapp",
        user="notesapp",
        password="notesapp_pg_pw_2024",
        connect_timeout=5,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def snapshot():
    data = {}
    with closing(connect()) as conn, conn.cursor() as cur:
        for table in TABLES:
            cur.execute(f"SELECT * FROM {table} ORDER BY id")
            data[table] = cur.fetchall()
        cur.execute("SHOW server_version")
        version = next(iter(cur.fetchone().values()))
    return json.loads(canonical(data)), version


def write_private(path, plaintext, key, aad):
    nonce = os.urandom(12)
    envelope = b"NAHW1" + nonce + AESGCM(key).encrypt(nonce, plaintext, aad)
    with path.open("xb") as stream:
        stream.write(envelope)
    assert read_private(path, key, aad) == plaintext


def read_private(path, key, aad):
    envelope = path.read_bytes()
    if envelope[:5] != b"NAHW1":
        raise ValueError("Unsupported backup format.")
    return AESGCM(key).decrypt(envelope[5:17], envelope[17:], aad)


def save_result(name, result):
    RESULTS.mkdir(parents=True, exist_ok=True)
    result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    (RESULTS / name).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def prepare(key):
    if BASELINE.exists():
        raise FileExistsError(
            "The original baseline is already saved; it will not be overwritten."
        )
    data, version = snapshot()
    assert len(data["notes"]) == 60, "Unexpected data set; inspect before migrating."
    PRIVATE.mkdir(parents=True, exist_ok=True)
    dump = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "noteapp",
            "-f",
            str(APP_ROOT / "docker-compose.yml"),
            "-f",
            str(APP_ROOT / "compose.windows.yml"),
            "exec",
            "-T",
            "db",
            "pg_dump",
            "--no-owner",
            "--no-privileges",
            "-U",
            "notesapp",
            "notesapp",
        ],
        check=True,
        capture_output=True,
    ).stdout
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = PRIVATE / f"session03-before-{stamp}.sql.aesgcm"
    write_private(backup_path, dump, key, b"notesapp:database-backup:v1")
    write_private(BASELINE, canonical(data), key, b"notesapp:homework-baseline:v1")
    save_result(
        "before_migration.json",
        {
            "database_environment": "original Docker database",
            "server_version": version,
            "counts": {table: len(data[table]) for table in TABLES},
            "encrypted_comments_before": sum(
                (row["comment"] or "").startswith("aesgcm:v1:") for row in data["notes"]
            ),
            "original_table_sha256": {table: digest(data[table]) for table in TABLES},
            "encrypted_backup": backup_path.name,
            "backup_decryption_verified": True,
        },
    )


def check(key, after_restart=False):
    baseline = json.loads(read_private(BASELINE, key, b"notesapp:homework-baseline:v1"))
    stored, version = snapshot()
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM notesapp_crypto_state WHERE feature = %s",
            ("notes.comment",),
        )
        assert cur.fetchone()["version"] == 1
    ciphertext_sha256 = digest(stored["notes"])
    assert all((r["comment"] or "").startswith("aesgcm:v1:") for r in stored["notes"])
    cipher = CommentCipher(key)
    recovered = {
        **stored,
        "notes": [
            {**row, "comment": cipher.decrypt(row["comment"], row["id"])}
            for row in stored["notes"]
        ],
    }
    assert recovered == baseline, "Existing data changed or could not be recovered."
    teacher = next(r for r in baseline["users"] if r["role"] == "teacher")
    student = next(r for r in baseline["users"] if r["role"] == "student")
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def get(path):
        with opener.open("http://127.0.0.1:8080" + path, timeout=10) as response:
            assert response.status == 200
            return response.read().decode("utf-8")

    export_authenticator = ExportAuthenticator.from_key_file(
        COURSE_ROOT / ".secrets/notesapp-export-hmac.key"
    )

    def get_export(path):
        return export_authenticator.verify(get(path).encode("utf-8")).decode("utf-8")

    def login(user):
        form = urllib.parse.urlencode(
            {"username": user["username"], "password": user["password"]}
        )
        with opener.open(
            "http://127.0.0.1:8080/login", data=form.encode(), timeout=10
        ) as response:
            assert response.status == 200 and not response.url.endswith("/login")

    assert get("/healthz").strip() == "ok"
    login(teacher)
    teacher_page = get("/teacher")
    assert baseline["notes"][0]["comment"] in teacher_page
    assert "aesgcm:v1:" not in teacher_page
    for row in baseline["notes"]:
        response = json.loads(get(f"/api/notes/{row['id']}"))
        assert response["comment"] == row["comment"]
    users = {r["id"]: r["username"] for r in baseline["users"]}
    classes = {r["id"]: r["name"] for r in baseline["classes"]}
    expected_csv = collections.Counter(
        (users[r["student_id"]], classes[r["class_id"]], r["grade"], r["comment"])
        for r in baseline["notes"]
    )
    export = list(csv.DictReader(io.StringIO(get_export("/export.csv"))))
    assert (
        collections.Counter(
            tuple(r[k] for k in ("student", "class", "grade", "comment"))
            for r in export
        )
        == expected_csv
    )
    class_export_rows = 0
    for class_id in classes:
        class_rows = list(
            csv.DictReader(io.StringIO(get_export(f"/export.csv?class_id={class_id}")))
        )
        assert collections.Counter(
            tuple(r[k] for k in ("student", "class", "grade", "comment"))
            for r in class_rows
        ) == collections.Counter(
            (users[r["student_id"]], classes[class_id], r["grade"], r["comment"])
            for r in baseline["notes"]
            if r["class_id"] == class_id
        )
        class_export_rows += len(class_rows)
    get("/logout")
    login(student)
    student_page = get("/dashboard")
    student_note = next(
        r for r in baseline["notes"] if r["student_id"] == student["id"]
    )
    assert student_note["comment"] in student_page and "aesgcm:v1:" not in student_page
    if after_restart:
        previous = json.loads((RESULTS / "live_verification.json").read_text())
        assert previous["stored_notes_sha256"] == ciphertext_sha256
    save_result(
        "restart_verification.json" if after_restart else "live_verification.json",
        {
            "database_environment": "original Docker database",
            "server_version": version,
            "request_transport": "HTTP at 127.0.0.1:8080",
            "counts": {table: len(stored[table]) for table in TABLES},
            "encrypted_comments": len(stored["notes"]),
            "migration_completion_marker_version": 1,
            "all_original_comments_recovered_exactly": True,
            "other_columns_and_tables_unchanged": True,
            "teacher_and_student_pages_checked": True,
            "authenticated_api_reads_checked": len(stored["notes"]),
            "full_csv_matches_original_data": True,
            "four_class_exports_total_rows": class_export_rows,
            "stored_notes_sha256": ciphertext_sha256,
            "checked_after_container_restart": after_restart,
            "ciphertexts_unchanged_after_restart": True if after_restart else None,
        },
    )


def main():
    global RESULTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "check", "restart"))
    parser.add_argument("--results-dir", type=Path, help="Write new evidence separately from historical checks.")
    args = parser.parse_args()
    if args.results_dir:
        RESULTS = args.results_dir.resolve()
    key = KEY_PATH.read_bytes()
    CommentCipher(key)  # Validate key length before touching the database.
    if args.mode == "prepare":
        prepare(key)
    else:
        check(key, after_restart=args.mode == "restart")


if __name__ == "__main__":
    main()
