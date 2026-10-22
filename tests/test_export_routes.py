"""Use real PostgreSQL and teacher sessions for the export/verify workflow."""

import csv
import io
import re
from contextlib import closing

import pytest

from export_hmac import ExportAuthenticator


def login(client, role="teacher"):
    with client.session_transaction() as session:
        session.update(user_id=2, username="teacher.test", role=role)


def token(client):
    page = client.get("/verify-export")
    assert page.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def upload(client, content, csrf_token, filename="grades.csv"):
    return client.post(
        "/verify-export",
        data={"csrf_token": csrf_token, "file": (io.BytesIO(content), filename)},
    )


@pytest.mark.parametrize("url", ["/export.csv", "/export.csv?class_id=1"])
def test_authenticated_export_and_verification_do_not_change_database(web_app, database, url):
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM notes ORDER BY id")
        before = cur.fetchall()
    client = web_app.app.test_client()
    login(client)
    exported = client.get(url)
    assert exported.status_code == 200
    assert "attachment" in exported.headers["Content-Disposition"]
    payload = web_app.export_authenticator.verify(exported.data)
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    assert reader.fieldnames == ["student", "class", "grade", "comment"]
    assert len(list(reader)) == 3
    assert "中文评语" in payload.decode("utf-8")
    csrf_token = token(client)
    result = upload(client, exported.data, csrf_token)
    assert result.status_code == 200 and "Verification passed" in result.text
    edited = exported.data.replace(b"15.5", b"18.5")
    result = upload(client, edited, csrf_token)
    assert result.status_code == 400 and "Verification failed" in result.text
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM notes ORDER BY id")
        assert cur.fetchall() == before


@pytest.mark.parametrize("role", [None, "student", "admin"])
def test_verification_requires_teacher_session(web_app, role):
    client = web_app.app.test_client()
    if role:
        login(client, role)
    assert client.get("/verify-export").status_code == 302
    assert client.post("/verify-export").status_code == 302


def test_verification_rejects_missing_file_bad_token_and_oversized_upload(web_app):
    client = web_app.app.test_client()
    login(client)
    csrf_token = token(client)
    assert client.post("/verify-export", data={"csrf_token": csrf_token}).status_code == 400
    assert upload(client, b"unsigned", "wrong-token").status_code == 400
    assert upload(client, b"unsigned", "").status_code == 400
    assert upload(client, b"unsigned", "中文").status_code == 400
    assert upload(client, b"unsigned", csrf_token, "").status_code == 400
    assert upload(client, b"x" * (8 * 1024 * 1024), csrf_token).status_code == 413


def test_unsigned_wrong_key_and_untrusted_filename_are_rejected_safely(web_app):
    client = web_app.app.test_client()
    login(client)
    csrf_token = token(client)
    payload = b"student,class,grade,comment\r\nalice,Math,14,good\r\n"
    wrong_key = ExportAuthenticator(b"x" * 32).sign(payload)
    for content in [payload, wrong_key, b"not csv", b""]:
        result = upload(client, content, csrf_token, '<script>alert(1)</script>.csv')
        assert result.status_code == 400
        assert "Verification failed" in result.text
        assert "<script>" not in result.text
        assert "Traceback" not in result.text


def test_teacher_page_links_to_verification(web_app):
    client = web_app.app.test_client()
    login(client)
    response = client.get("/teacher")
    assert response.status_code == 200
    assert 'href="/verify-export"' in response.text


def test_empty_class_export_still_has_a_valid_hmac(web_app):
    client = web_app.app.test_client()
    login(client)
    response = client.get("/export.csv?class_id=999")
    assert response.status_code == 200
    payload = web_app.export_authenticator.verify(response.data)
    assert payload == b"student,class,grade,comment\r\n"
