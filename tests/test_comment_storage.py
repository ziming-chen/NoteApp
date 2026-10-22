"""Exercise migrations and every comment route against real PostgreSQL."""

import csv
import io
import os
from contextlib import closing

import pytest

from comment_crypto import CommentCipher, CommentCryptoError
from comment_migration import migrate_comments


def rows(database):
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM notes ORDER BY id")
        return cur.fetchall()


def test_migration_preserves_data_and_is_idempotent(database):
    before = rows(database)
    cipher = CommentCipher(os.urandom(32))
    with closing(database()) as conn:
        assert migrate_comments(conn, cipher) == {"migrated": 2, "verified": 0}
    after = rows(database)
    for original, stored in zip(before, after, strict=True):
        assert {k: v for k, v in original.items() if k != "comment"} == {
            k: v for k, v in stored.items() if k != "comment"
        }
        assert cipher.decrypt(stored["comment"], stored["id"]) == original["comment"]
    with closing(database()) as conn:
        assert migrate_comments(conn, cipher) == {"migrated": 0, "verified": 2}
    assert rows(database) == after


@pytest.mark.parametrize("invalid", ["aesgcm:v1:broken", "aesgcm:v2:AAAA"])
def test_migration_failure_rolls_back_earlier_updates(database, invalid):
    with closing(database()) as conn, conn, conn.cursor() as cur:
        cur.execute("UPDATE notes SET comment = %s WHERE id = 2", (invalid,))
    before = rows(database)
    with closing(database()) as conn:
        with pytest.raises(CommentCryptoError):
            migrate_comments(conn, CommentCipher(os.urandom(32)))
    assert rows(database) == before


def test_migration_wrong_key_does_not_reencrypt(database):
    with closing(database()) as conn:
        migrate_comments(conn, CommentCipher(os.urandom(32)))
    before = rows(database)
    with closing(database()) as conn:
        with pytest.raises(CommentCryptoError):
            migrate_comments(conn, CommentCipher(os.urandom(32)))
    assert rows(database) == before


def test_plaintext_tampering_after_initial_migration_rejected(database):
    cipher = CommentCipher(os.urandom(32))
    with closing(database()) as conn:
        migrate_comments(conn, cipher)
    with closing(database()) as conn, conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE notes SET comment = 'unauthenticated replacement' WHERE id = 1"
        )
    before = rows(database)
    with closing(database()) as conn, pytest.raises(CommentCryptoError):
        migrate_comments(conn, cipher)
    assert rows(database) == before


def test_unknown_migration_version_rejected(database):
    cipher = CommentCipher(os.urandom(32))
    with closing(database()) as conn:
        migrate_comments(conn, cipher)
    with closing(database()) as conn, conn, conn.cursor() as cur:
        cur.execute("UPDATE notesapp_crypto_state SET version = 2")
    with closing(database()) as conn, pytest.raises(CommentCryptoError):
        migrate_comments(conn, cipher)


def login(client, role):
    with client.session_transaction() as session:
        session.update(
            user_id=1 if role == "student" else 2, role=role, username="test"
        )


def test_all_read_routes_decrypt_and_export_keeps_schema(web_app):
    client = web_app.app.test_client()
    login(client, "student")
    response = client.get("/dashboard")
    assert response.status_code == 200 and "Good work" in response.text
    assert "aesgcm:v1:" not in response.text
    assert client.get("/api/notes/2").json["comment"] == "中文评语"
    assert client.get("/api/notes/3").json["comment"] is None
    assert client.get("/api/notes/999").status_code == 404
    login(client, "teacher")
    response = client.get("/teacher")
    assert response.status_code == 200 and "中文评语" in response.text
    for url in ["/export.csv", "/export.csv?class_id=1"]:
        response = client.get(url)
        payload = web_app.export_authenticator.verify(response.data).decode("utf-8")
        reader = csv.DictReader(io.StringIO(payload))
        assert reader.fieldnames == ["student", "class", "grade", "comment"]
        assert {row["comment"] for row in reader} == {"Good work", "中文评语", ""}
        assert "aesgcm:v1:" not in response.text


def test_create_update_never_store_plaintext_and_use_fresh_nonce(web_app, database):
    client = web_app.app.test_client()
    login(client, "teacher")
    text = "新的评语 😀"
    assert (
        client.post(
            "/grades",
            data={"student_id": "1", "class_id": "1", "grade": "18", "comment": text},
        ).status_code
        == 302
    )
    stored = rows(database)[-1]
    note_id = stored["id"]
    assert stored["comment"] != text
    assert client.get(f"/api/notes/{note_id}").json["comment"] == text
    update = {"note_id": str(note_id), "grade": "19", "comment": text}
    assert client.post("/grades", data=update).status_code == 302
    assert rows(database)[-1]["comment"] != stored["comment"]
    assert client.get(f"/api/notes/{note_id}").json["comment"] == text
    assert client.post("/grades", data={**update, "comment": ""}).status_code == 302
    assert client.get(f"/api/notes/{note_id}").json["comment"] == ""


@pytest.mark.parametrize(
    "url", ["/dashboard", "/teacher", "/api/notes/1", "/export.csv"]
)
def test_tampered_storage_returns_generic_error_without_plaintext(
    web_app, database, url
):
    with closing(database()) as conn, conn, conn.cursor() as cur:
        cur.execute("UPDATE notes SET comment = 'aesgcm:v1:broken' WHERE id = 1")
    client = web_app.app.test_client()
    login(client, "student" if url == "/dashboard" else "teacher")
    response = client.get(url)
    assert response.status_code == 500
    assert "Good work" not in response.text
    assert "broken" not in response.text
    assert "authentication" in response.text.lower()


def test_invalid_note_id_does_not_write(web_app, database):
    before = rows(database)
    client = web_app.app.test_client()
    login(client, "teacher")
    assert (
        client.post("/grades", data={"note_id": "bad", "comment": "text"}).status_code
        == 400
    )
    assert rows(database) == before


def test_unauthenticated_routes_still_require_login(web_app):
    client = web_app.app.test_client()
    for url in ["/dashboard", "/teacher", "/export.csv"]:
        assert client.get(url).status_code == 302
    assert client.get("/api/notes/1").status_code == 401
    assert client.post("/grades", data={"comment": "text"}).status_code == 302
