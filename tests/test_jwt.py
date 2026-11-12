"""Regression tests for the Class 7 JWT verifier."""

import hashlib
import hmac
import json

import pytest

CLAIMS = {"user_id": 1, "username": "student.test", "role": "student"}


def signed_token(app, header, payload, secret):
    header_b64 = app._b64url(json.dumps(header).encode())
    payload_b64 = app._b64url(json.dumps(payload).encode())
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return f"{message}.{app._b64url(signature)}"


@pytest.mark.parametrize("algorithm", ["none", "hs256", "HS512", None, ["HS256"]])
def test_rejects_other_algorithms_even_with_a_matching_hmac(web_app, algorithm):
    token = signed_token(web_app, {"alg": algorithm}, CLAIMS, web_app.JWT_SECRET)
    assert web_app.verify_jwt(token) is None


def test_rejects_wrong_key_and_modified_claims(web_app):
    old_token = signed_token(web_app, {"alg": "HS256"}, CLAIMS, "s3cr3t")
    assert web_app.verify_jwt(old_token) is None

    genuine = web_app.make_jwt(CLAIMS)
    assert web_app.verify_jwt(genuine) == CLAIMS
    header, _, signature = genuine.split(".")
    modified = web_app._b64url(json.dumps({**CLAIMS, "role": "teacher"}).encode())
    assert web_app.verify_jwt(f"{header}.{modified}.{signature}") is None


def test_rejects_malformed_tokens(web_app):
    header, payload, _ = web_app.make_jwt(CLAIMS).split(".")
    invalid_tokens = (
        "",
        f"{header}.{payload}.",
        f"{header}.{payload}.é",
        f"eA.{payload}.x",
        signed_token(web_app, [], CLAIMS, web_app.JWT_SECRET),
        signed_token(web_app, {"alg": "HS256"}, [], web_app.JWT_SECRET),
    )
    for token in invalid_tokens:
        assert web_app.verify_jwt(token) is None


def test_bearer_authentication_and_cookie_fallback(web_app):
    browser = web_app.app.test_client()
    response = browser.post("/login", data={"username": "student.test", "password": "demo"})
    assert response.status_code == 302
    with browser.session_transaction() as session:
        token = session["token"]

    api = web_app.app.test_client(use_cookies=False)
    path = "/api/notes/1"
    assert api.get(path, headers={"Authorization": f"Bearer {token}"}).json["student"] == "student.test"
    assert browser.get(path).status_code == 200
    for invalid in ("Bearer", "Bearer invalid"):
        denied = browser.get(path, headers={"Authorization": invalid})
        assert denied.status_code == 401
        assert denied.json == {"error": "unauthorized"}
