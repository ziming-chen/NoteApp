"""Class 10 - stored XSS: a grade comment is data, never markup.

Flaw #10 was `{% autoescape false %}{{ n.comment }}{% endautoescape %}` in
`dashboard.html` and `teacher.html`. These tests assert the rendered pages carry the
comment as text and never as live code, and that an ordinary comment keeps its `<`
and `&` characters instead of having them mangled or turned into markup.
"""

from pathlib import Path

PAYLOAD = "<script>alert('XSS by Eve')</script>"
PAYLOAD_AS_TEXT = "&lt;script&gt;alert(&#39;XSS by Eve&#39;)&lt;/script&gt;"
NORMAL = "score < 10 on part 1 & 2, see me"
NORMAL_AS_TEXT = "score &lt; 10 on part 1 &amp; 2, see me"


def login(client, role):
    with client.session_transaction() as session:
        session.update(
            user_id=1 if role == "student" else 2, role=role, username="test"
        )


def store_comment(client, comment, note_id="1"):
    response = client.post(
        "/grades",
        data={"note_id": note_id, "grade": "16.2", "comment": comment},
    )
    assert response.status_code == 302


def test_student_dashboard_shows_a_stored_script_as_text(web_app):
    client = web_app.app.test_client()
    login(client, "teacher")
    store_comment(client, PAYLOAD)

    login(client, "student")
    page = client.get("/dashboard").text
    assert "<script>alert" not in page  # no live script element reaches the browser
    assert PAYLOAD_AS_TEXT in page  # the reader sees the characters instead


def test_teacher_page_shows_a_stored_script_as_text(web_app):
    client = web_app.app.test_client()
    login(client, "teacher")
    store_comment(client, PAYLOAD)

    page = client.get("/teacher").text
    assert "<script>alert" not in page
    assert PAYLOAD_AS_TEXT in page


def test_normal_comment_keeps_its_less_than_and_ampersand(web_app):
    client = web_app.app.test_client()
    login(client, "teacher")
    store_comment(client, NORMAL)

    login(client, "student")
    page = client.get("/dashboard").text
    assert NORMAL_AS_TEXT in page  # displayed as written, not broken
    assert "score < 10" not in page  # a raw "<" would have started a tag


def test_no_template_turns_autoescaping_off(web_app):
    """Guard the fix: a template that disables autoescaping fails this test."""
    offenders = []
    for directory in web_app.app.jinja_loader.searchpath:
        for path in Path(directory).glob("*.html"):
            if "autoescape false" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
    assert offenders == []
