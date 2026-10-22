"""Verify only the course alice account through the running HTTPS application.

This script performs real logins. Screenshots are from an automated Edge session.
The self-signed localhost certificate is accepted only for this local lab origin.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from psycopg2 import sql
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = HERE / "results"
EVIDENCE = HERE / "evidence"


def connect():
    return psycopg2.connect(
        host="127.0.0.1", port=15432, dbname="notesapp", user="notesapp",
        password="notesapp_pg_pw_2024", connect_timeout=5,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def snapshot():
    summary = {}
    conn = connect()
    try:
        with conn.cursor() as cursor:
            for table in ("users", "classes", "enrollments", "notes", "notesapp_crypto_state"):
                cursor.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
                rows = cursor.fetchall()
                rows.sort(key=lambda row: json.dumps(row, default=str, sort_keys=True))
                encoded = json.dumps(rows, default=str, sort_keys=True, ensure_ascii=False).encode("utf-8")
                summary[table] = {"rows": len(rows), "sha256": hashlib.sha256(encoded).hexdigest()}
    finally:
        conn.close()
    return summary


def users():
    conn = connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, password FROM users ORDER BY id")
            return cursor.fetchall()
    finally:
        conn.close()


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    target = RESULTS / "live-migration.json"
    if target.exists():
        raise SystemExit("Evidence already exists; refusing to overwrite the first migration.")
    before = users()
    alice = next(row for row in before if row["username"] == "alice")
    assert alice["password"] == "alicepw", "Expected an unmigrated course account."
    baseline = json.loads((RESULTS / "before-remediation.json").read_text(encoding="utf-8"))
    assert snapshot() == baseline["tables"], "Live DB changed since the pre-lab baseline."
    observed = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
                "origin": "https://localhost", "operator": "Assistant automated Edge session, authorized by user",
                "certificate_handling": "ignore_https_errors for the local self-signed lab certificate only",
                "alice_was_plaintext": True}
    EVIDENCE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1200, "height": 850})
        page = context.new_page()

        def login(password):
            page.goto("https://localhost/logout", wait_until="networkidle")
            page.get_by_label("Username").fill("alice")
            page.locator('input[type="password"]').fill(password)
            page.get_by_role("button", name="Log in", exact=True).click()
            page.wait_for_load_state("networkidle")

        login("incorrect-lab-check")
        observed["legacy_wrong_password_denied"] = page.get_by_text("Invalid credentials.", exact=True).is_visible()
        observed["legacy_wrong_password_did_not_migrate"] = users() == before
        assert observed["legacy_wrong_password_denied"] and observed["legacy_wrong_password_did_not_migrate"]
        login("alicepw")
        assert page.url.endswith("/dashboard")
        assert page.get_by_role("heading", name="My grades").is_visible()
        page.screenshot(path=str(EVIDENCE / "02_alice_first_login.png"), full_page=True)
        after_first = users()
        first = next(row for row in after_first if row["username"] == "alice")
        assert first["password"].startswith("$argon2id$")
        observed["first_login_dashboard"] = page.url
        observed["alice_stored_hash"] = first["password"]
        observed["first_hash_sha256"] = sha(first["password"])
        observed["only_alice_password_changed"] = [
            a["username"] for a, b in zip(before, after_first, strict=True) if a != b
        ] == ["alice"]
        assert observed["only_alice_password_changed"]

        login("incorrect-lab-check")
        observed["argon2_wrong_password_denied"] = page.get_by_text("Invalid credentials.", exact=True).is_visible()
        observed["argon2_wrong_password_preserved_hash"] = users() == after_first
        page.screenshot(path=str(EVIDENCE / "03_wrong_password_denied.png"), full_page=True)
        assert observed["argon2_wrong_password_denied"] and observed["argon2_wrong_password_preserved_hash"]
        login("alicepw")
        assert page.url.endswith("/dashboard")
        observed["second_login_dashboard"] = page.url
        observed["second_login_preserved_hash"] = users() == after_first
        assert observed["second_login_preserved_hash"]
        page.screenshot(path=str(EVIDENCE / "04_alice_second_login.png"), full_page=True)
        browser.close()

    after = snapshot()
    observed["tables_after"] = after
    observed["non_user_tables_unchanged"] = all(
        value == baseline["tables"][name] for name, value in after.items() if name != "users"
    )
    assert observed["non_user_tables_unchanged"]
    observed["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    target.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    lines = [f"{key}: {value}" for key, value in observed.items() if key != "tables_after"]
    (RESULTS / "live-migration.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in observed.items() if k not in ("alice_stored_hash", "tables_after")}, indent=2))


if __name__ == "__main__":
    main()
