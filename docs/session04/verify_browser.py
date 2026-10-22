"""Exercise teacher login, download, and verification in headless Chrome."""

import json
import os
from contextlib import closing
from pathlib import Path

from playwright.sync_api import sync_playwright
from verify_live import ORIGIN, RESULTS, connect, save, snapshot


def credentials(role):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute("SELECT username,password FROM users WHERE role=%s ORDER BY id LIMIT 1", (role,))
        return cur.fetchone()


def main():
    before = snapshot()
    teacher = credentials("teacher")
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    executable = next((path for path in candidates if path.is_file()), None)
    if executable is None:
        raise FileNotFoundError("Chrome or Edge is required for the optional browser check.")
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=str(executable), headless=True)
        context = browser.new_context(viewport={"width": 1100, "height": 850}, accept_downloads=True)
        page = context.new_page()
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(ORIGIN + "/verify-export")
        assert page.url.endswith("/login")
        page.get_by_label("Username").fill(teacher["username"])
        page.get_by_label("Password").fill(teacher["password"])
        page.get_by_role("button", name="Log in").click()
        page.wait_for_url("**/teacher")
        with page.expect_download() as download_info:
            page.get_by_role("link", name="Export all grades", exact=True).click()
        downloaded = RESULTS / "browser_download.csv"
        download_info.value.save_as(downloaded)
        assert downloaded.read_bytes() == (RESULTS / "grades_original.csv").read_bytes()
        page.get_by_role("link", name="Verify an exported CSV", exact=True).click()
        page.get_by_label("Exported CSV file").set_input_files(downloaded)
        page.get_by_role("button", name="Verify file", exact=True).click()
        page.get_by_role("status").wait_for()
        assert "Verification passed" in page.get_by_role("status").inner_text()
        page.screenshot(path=str(RESULTS / "verification_passed.png"), full_page=True)
        page.get_by_label("Exported CSV file").set_input_files(RESULTS / "grades_tampered.csv")
        page.get_by_role("button", name="Verify file", exact=True).click()
        page.get_by_role("alert").wait_for()
        assert "Verification failed" in page.get_by_role("alert").inner_text()
        page.screenshot(path=str(RESULTS / "verification_failed.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(RESULTS / "verification_mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not page_errors
        version = browser.version
        context.close()
        browser.close()
    assert snapshot() == before
    result = save("browser_verification.json", {
        "browser": "headless Chromium via the installed Chrome/Edge executable",
        "version": version, "teacher_login": True, "download_matches_http_export": True,
        "original_upload_passes": True, "changed_grade_upload_fails": True,
        "mobile_form_has_no_horizontal_overflow": True, "page_errors": page_errors,
        "database_unchanged": True,
    })
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
