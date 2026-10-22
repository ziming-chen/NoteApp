"""Check credentials and legacy upgrades using real Argon2 hashes."""

import pytest
from argon2 import PasswordHasher

from password_storage import check_password


@pytest.fixture(scope="module")
def stored_hash():
    return PasswordHasher().hash("demo-password")


def test_legacy_success_returns_a_salted_argon2id_value():
    authenticated, upgraded = check_password("demo-password", "demo-password")
    assert authenticated
    assert upgraded.startswith("$argon2id$")
    assert PasswordHasher().verify(upgraded, "demo-password")


def test_same_legacy_password_gets_different_salts():
    first = check_password("demo", "demo")[1]
    second = check_password("demo", "demo")[1]
    assert first != second


def test_wrong_legacy_password_does_not_request_an_upgrade():
    assert check_password("demo", "incorrect") == (False, None)


def test_correct_argon2_password_needs_no_legacy_rewrite(stored_hash):
    assert check_password(stored_hash, "demo-password") == (True, None)


def test_wrong_argon2_password_is_rejected(stored_hash):
    assert check_password(stored_hash, "incorrect") == (False, None)


@pytest.mark.parametrize("stored", ["$argon2id$broken", "$argon2invalid", "$argon2id$"])
def test_malformed_argon2_values_fail_closed(stored):
    assert check_password(stored, stored) == (False, None)


def test_unicode_legacy_password_survives_upgrade():
    authenticated, upgraded = check_password("密码-é", "密码-é")
    assert authenticated
    assert PasswordHasher().verify(upgraded, "密码-é")
