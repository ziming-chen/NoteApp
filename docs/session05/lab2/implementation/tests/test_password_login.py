"""Verify login migration against an isolated PostgreSQL database."""

from contextlib import closing

from argon2 import PasswordHasher


def password_for(database, username="student.test"):
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT password FROM users WHERE username=%s", (username,))
        return cur.fetchone()["password"]


def store_password(database, value):
    with closing(database()) as conn, conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET password=%s WHERE username='student.test'", (value,))


def test_correct_legacy_login_upgrades_only_that_user_and_can_login_again(web_app, database):
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM notes ORDER BY id")
        notes_before = cur.fetchall()
    teacher_before = password_for(database, "teacher.test")
    client = web_app.app.test_client()
    response = client.post("/login", data={"username": "student.test", "password": "demo"})
    assert response.status_code == 302
    upgraded = password_for(database)
    assert upgraded.startswith("$argon2id$")
    assert PasswordHasher().verify(upgraded, "demo")
    assert password_for(database, "teacher.test") == teacher_before
    with client.session_transaction() as session:
        assert session["username"] == "student.test"
        assert session["role"] == "student"
    client.get("/logout")
    assert client.post("/login", data={"username": "student.test", "password": "demo"}).status_code == 302
    assert password_for(database) == upgraded
    with closing(database()) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM notes ORDER BY id")
        assert cur.fetchall() == notes_before


def test_wrong_legacy_password_does_not_change_storage_or_create_session(web_app, database):
    client = web_app.app.test_client()
    response = client.post("/login", data={"username": "student.test", "password": "incorrect"})
    assert response.status_code == 200
    assert "Invalid credentials" in response.text
    assert password_for(database) == "demo"
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_wrong_hash_password_does_not_create_session_or_change_hash(web_app, database):
    stored = PasswordHasher().hash("demo")
    store_password(database, stored)
    client = web_app.app.test_client()
    response = client.post("/login", data={"username": "student.test", "password": "incorrect"})
    assert response.status_code == 200
    assert "Invalid credentials" in response.text
    assert password_for(database) == stored
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_malformed_hash_returns_normal_login_failure(web_app, database):
    store_password(database, "$argon2id$broken")
    client = web_app.app.test_client()
    response = client.post("/login", data={"username": "student.test", "password": "$argon2id$broken"})
    assert response.status_code == 200
    assert "Invalid credentials" in response.text
    assert "Traceback" not in response.text
    assert password_for(database) == "$argon2id$broken"


def test_unknown_account_is_rejected(web_app):
    client = web_app.app.test_client()
    response = client.post("/login", data={"username": "missing-user", "password": "demo"})
    assert response.status_code == 200
    assert "Invalid credentials" in response.text
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_existing_course_username_query_error_still_denies_login(web_app):
    client = web_app.app.test_client()
    response = client.post("/login", data={"username": "'", "password": "demo"})
    assert response.status_code == 200
    assert "Query error" in response.text
    with client.session_transaction() as session:
        assert "user_id" not in session
