"""Check the complete supplied seed in a disposable, isolated database."""

import csv
import hashlib
import io
import json
import os
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from comment_crypto import CommentCipher

ROOT = Path(__file__).resolve().parents[1]


def snapshot(database):
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM notes ORDER BY id")
        return cur.fetchall()


def test_complete_seed_migration_reads_exports_and_reload(
    web_app, database, monkeypatch
):
    with closing(database()) as conn, conn, conn.cursor() as cur:
        assert conn.get_dsn_parameters()["dbname"].startswith("notesapp_hw_test_")
        cur.execute("DROP TABLE IF EXISTS notesapp_crypto_state")
        cur.execute((ROOT / "db/init.sql").read_text(encoding="utf-8"))
        counts = {}
        for table in ["users", "classes", "enrollments", "notes"]:
            cur.execute(f"SELECT COUNT(*) AS count FROM {table}")
            counts[table] = cur.fetchone()["count"]
        cur.execute("SHOW server_version")
        server_version = next(iter(cur.fetchone().values()))
        cur.execute(
            "SELECT username, password FROM users WHERE role = 'teacher' ORDER BY id LIMIT 1"
        )
        teacher = cur.fetchone()
        cur.execute(
            "SELECT username, password FROM users WHERE role = 'student' ORDER BY id LIMIT 1"
        )
        student = cur.fetchone()

    before = snapshot(database)
    assert counts["users"] == 35 and counts["classes"] == 4 and counts["notes"] == 60
    assert web_app.initialize_comments() == {"migrated": 60, "verified": 0}
    encrypted = snapshot(database)
    decoded = [
        {**row, "comment": web_app.comment_cipher.decrypt(row["comment"], row["id"])}
        for row in encrypted
    ]
    assert decoded == before
    assert all(row["comment"].startswith("aesgcm:v1:") for row in encrypted)

    client = web_app.app.test_client()
    assert client.post("/login", data=teacher).status_code == 302
    assert client.get("/teacher").status_code == 200
    for row in before:
        response = client.get(f"/api/notes/{row['id']}")
        assert response.status_code == 200
        assert response.json["comment"] == row["comment"]
    export = client.get("/export.csv")
    payload = web_app.export_authenticator.verify(export.data).decode("utf-8")
    assert len(list(csv.DictReader(io.StringIO(payload)))) == 60
    assert "aesgcm:v1:" not in export.text
    exported_by_class = 0
    for class_id in range(1, 5):
        export = client.get(f"/export.csv?class_id={class_id}")
        payload = web_app.export_authenticator.verify(export.data).decode("utf-8")
        exported_by_class += len(list(csv.DictReader(io.StringIO(payload))))
        assert "aesgcm:v1:" not in export.text
    assert exported_by_class == 60
    client.get("/logout")
    assert client.post("/login", data=student).status_code == 302
    assert client.get("/dashboard").status_code == 200

    reloaded_cipher = CommentCipher.from_key_file(
        os.environ["NOTESAPP_COMMENT_KEY_FILE"]
    )
    monkeypatch.setattr(web_app, "comment_cipher", reloaded_cipher)
    assert web_app.initialize_comments() == {"migrated": 0, "verified": 60}
    assert snapshot(database) == encrypted
    assert [reloaded_cipher.decrypt(r["comment"], r["id"]) for r in encrypted] == [
        r["comment"] for r in before
    ]

    evidence_directory = os.environ.get("HOMEWORK_EVIDENCE_DIR")
    if evidence_directory:
        output = Path(evidence_directory)
        output.mkdir(parents=True, exist_ok=True)
        summary = {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "database_environment": "isolated Windows PostgreSQL; disposable database",
            "server_version": server_version,
            "input": "supplied db/init.sql seed; not the existing Docker database",
            "request_transport": "Flask test client",
            "counts": counts,
            "migrated_comments": 60,
            "all_non_comment_columns_preserved": True,
            "all_comments_recovered_exactly": True,
            "authenticated_api_reads_checked": 60,
            "teacher_and_student_pages_checked": True,
            "full_csv_rows": 60,
            "four_class_exports_total_rows": exported_by_class,
            "key_file_reload_and_idempotent_migration": True,
            "stored_ciphertexts_unchanged_on_reload": True,
            "original_notes_sha256": hashlib.sha256(
                json.dumps(before, default=str, sort_keys=True).encode()
            ).hexdigest(),
            "existing_docker_database_migrated": False,
        }
        (output / "seeded_verification.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
