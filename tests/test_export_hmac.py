"""Authentication of exact CSV bytes, including hostile or incomplete trailers."""

import csv
import io
import os

import pytest

from export_hmac import ExportAuthenticator, ExportIntegrityError

CSV = b"student,class,grade,comment\r\nalice,Math,14.0,good work\r\n"


@pytest.fixture
def authenticator():
    return ExportAuthenticator(bytes(range(32)))


def test_export_round_trip_preserves_exact_csv_bytes(authenticator):
    signed = authenticator.sign(CSV)
    assert signed.startswith(CSV + b"# HMAC: v1:sha256:")
    assert signed.endswith(b"\r\n")
    assert authenticator.verify(signed) == CSV
    assert authenticator.sign(CSV) == signed


def test_unicode_quoted_multiline_comments_and_marker_are_preserved(authenticator):
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["student", "class", "grade", "comment"])
    writer.writerow(["alice", "Math", "14", '中文 😀,"quoted"\n# HMAC: fake'])
    original = buf.getvalue().encode("utf-8")
    assert authenticator.verify(authenticator.sign(original)) == original


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.replace(b"14.0", b"18.0"),
        lambda value: value.replace(b"alice", b"other"),
        lambda value: value.replace(b"good work", b"bad work"),
        lambda value: value.replace(b"\r\n", b"\n"),
        lambda value: value[:-1],
        lambda value: value[:-2],
        lambda value: value + b"\r\n",
        lambda value: value + b"mallory,Math,20.0,extra\r\n",
        lambda value: value + value,
        lambda value: value.replace(b"v1:sha256:", b"v2:sha256:"),
        lambda value: value.replace(b"v1:sha256:", b"v1:sha1:"),
        lambda value: value[:value.rfind(b"# HMAC:")],
        lambda value: value[:value.rfind(b":") + 1] + b"z" * 64 + b"\r\n",
        lambda value: value[:value.rfind(b":") + 1] + b"0" * 63 + b"\r\n",
    ],
)
def test_modified_malformed_or_stripped_file_is_rejected(authenticator, change):
    signed = authenticator.sign(CSV)
    with pytest.raises(ExportIntegrityError):
        authenticator.verify(change(signed))


@pytest.mark.parametrize("content", [b"", b"unsigned\r\n", CSV])
def test_unsigned_file_is_rejected(authenticator, content):
    with pytest.raises(ExportIntegrityError):
        authenticator.verify(content)


def test_wrong_key_and_modified_tag_are_rejected(authenticator):
    signed = authenticator.sign(CSV)
    with pytest.raises(ExportIntegrityError):
        ExportAuthenticator(os.urandom(32)).verify(signed)
    replacement = b"0" if signed[-3:-2] != b"0" else b"1"
    with pytest.raises(ExportIntegrityError):
        authenticator.verify(signed[:-3] + replacement + b"\r\n")


def test_loading_persistent_key_and_missing_key(tmp_path):
    path = tmp_path / "export.key"
    path.write_bytes(bytes(range(32)))
    first = ExportAuthenticator.from_key_file(path)
    second = ExportAuthenticator.from_key_file(path)
    assert second.verify(first.sign(CSV)) == CSV
    with pytest.raises(FileNotFoundError):
        ExportAuthenticator.from_key_file(tmp_path / "missing.key")


@pytest.mark.parametrize("length", [0, 16, 31, 33, 64])
def test_invalid_key_length_is_rejected(length):
    with pytest.raises(ValueError):
        ExportAuthenticator(b"x" * length)


def test_signing_requires_a_complete_csv_line(authenticator):
    with pytest.raises(ValueError):
        authenticator.sign(b"incomplete")
