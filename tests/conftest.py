"""Use a separate PostgreSQL database; never reset the application's database."""

import importlib
import os
import uuid
from contextlib import closing

import psycopg2
import psycopg2.extras
import pytest
from psycopg2 import sql


@pytest.fixture
def database():
    """Each integration test owns a disposable database on the local lab server."""
    connection_args = {
        "host": os.environ.get("TEST_DB_HOST", "127.0.0.1"),
        "port": os.environ.get("TEST_DB_PORT", "15432"),
        "user": "notesapp",
        "password": "notesapp_pg_pw_2024",
        "connect_timeout": 5,
        "cursor_factory": psycopg2.extras.RealDictCursor,
    }
    admin = psycopg2.connect(dbname="postgres", **connection_args)
    admin.autocommit = True
    db_name = "notesapp_hw_test_" + uuid.uuid4().hex
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    try:

        def connect():
            return psycopg2.connect(dbname=db_name, **connection_args)

        with closing(connect()) as conn, conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE users (
                        id SERIAL PRIMARY KEY, username TEXT, password TEXT, role TEXT,
                        teacher_id INT
                    );
                    CREATE TABLE classes (
                        id SERIAL PRIMARY KEY, name TEXT, teacher_id INT
                    );
                    CREATE TABLE notes (
                        id SERIAL PRIMARY KEY, student_id INT REFERENCES users(id),
                        class_id INT REFERENCES classes(id), grade NUMERIC(4,1), comment TEXT
                    );
                    INSERT INTO users (username, password, role) VALUES
                        ('student.test', 'demo', 'student'), ('teacher.test', 'demo', 'teacher');
                    INSERT INTO classes (name, teacher_id) VALUES ('Test class', 2);
                    INSERT INTO notes (student_id, class_id, grade, comment) VALUES
                        (1, 1, 15.5, 'Good work'), (1, 1, 16.0, '中文评语'),
                        (1, 1, 17.0, NULL);
                """)
        yield connect
    finally:
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name))
            )
        admin.close()


@pytest.fixture
def web_app(database, tmp_path, monkeypatch):
    key_file = tmp_path / "comments.key"
    key_file.write_bytes(os.urandom(32))
    monkeypatch.setenv("NOTESAPP_COMMENT_KEY_FILE", str(key_file))
    export_key_file = tmp_path / "export.key"
    export_key_file.write_bytes(os.urandom(32))
    monkeypatch.setenv("NOTESAPP_EXPORT_HMAC_KEY_FILE", str(export_key_file))
    module = importlib.import_module("app")
    from comment_crypto import CommentCipher
    from export_hmac import ExportAuthenticator

    cipher = CommentCipher.from_key_file(key_file)
    monkeypatch.setattr(module, "comment_cipher", cipher)
    monkeypatch.setattr(
        module, "export_authenticator", ExportAuthenticator.from_key_file(export_key_file)
    )
    monkeypatch.setattr(module, "get_db", database)
    monkeypatch.setattr(module, "LOG_FILE", str(tmp_path / "app.log"))
    module.app.config.update(TESTING=True)
    module.initialize_comments()
    return module
