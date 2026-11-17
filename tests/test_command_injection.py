"""Class 9: the admin ping box must treat its input as data, never shell syntax.

Flaw #9 (command injection) is closed by calling subprocess.run with an argument
list and no shell=True, so ; | & $() inside the host value cannot start a second
command. These tests drive the real /admin/ping route with an admin session.
"""


def login_admin(client):
    with client.session_transaction() as session:
        session.update(user_id=1, username="admin", role="admin")


def ping(client, host):
    response = client.post("/admin/ping", data={"host": host})
    assert response.status_code == 200
    return response.text


def test_command_injection_payload_runs_no_second_command(web_app):
    client = web_app.app.test_client()
    login_admin(client)
    body = ping(client, "127.0.0.1; id; head -2 /etc/passwd")
    # The whole string was one hostname, so `id` never ran and /etc/passwd never
    # leaked. On the list form there is no shell to read the semicolons.
    assert "uid=" not in body
    assert "root:x:0:0" not in body


def test_command_injection_backticks_and_dollar_are_inert(web_app):
    client = web_app.app.test_client()
    login_admin(client)
    assert "uid=" not in ping(client, "127.0.0.1$(id)")
    assert "uid=" not in ping(client, "127.0.0.1`id`")


def test_ping_requires_admin_session(web_app):
    client = web_app.app.test_client()
    assert client.post("/admin/ping", data={"host": "127.0.0.1"}).status_code == 302
