import logging

from modules._common import secret_file
from modules._common.secret_file import read_secret_file


def test_returns_none_without_path():
    assert read_secret_file(None) is None
    assert read_secret_file("") is None


def test_reads_and_strips(tmp_path):
    f = tmp_path / "secret"
    f.write_text("  abc123\n")
    assert read_secret_file(str(f)) == "abc123"


def test_empty_file_is_none(tmp_path):
    f = tmp_path / "secret"
    f.write_text("  \n")
    assert read_secret_file(str(f)) is None


def test_missing_file_is_none_without_waiting(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(secret_file.time, "sleep", sleeps.append)
    assert read_secret_file(str(tmp_path / "nope")) is None
    assert sleeps == []


def test_directory_is_none(tmp_path):
    assert read_secret_file(str(tmp_path)) is None


def test_permission_denied_is_none(tmp_path, monkeypatch):
    f = tmp_path / "secret"
    f.write_text("abc")

    def deny(*args, **kwargs):
        raise PermissionError(13, "Permission denied", str(f))

    # chmod does not work in CI (the container runs as root), so shadow open()
    monkeypatch.setattr(secret_file, "open", deny, raising=False)
    assert read_secret_file(str(f)) is None


def test_waits_until_file_appears(tmp_path, monkeypatch):
    f = tmp_path / "secret"
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            f.write_text("late-token\n")

    monkeypatch.setattr(secret_file.time, "sleep", fake_sleep)
    assert read_secret_file(str(f), wait_seconds=5) == "late-token"
    assert len(sleeps) == 2


def test_gives_up_after_wait(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(secret_file.time, "sleep", sleeps.append)
    assert read_secret_file(str(tmp_path / "nope"), wait_seconds=3) is None
    assert len(sleeps) == 3


def test_unset_path_logs_debug(caplog):
    with caplog.at_level(logging.DEBUG):
        assert read_secret_file(None) is None
    assert "not configured" in caplog.text


def test_missing_file_logs_warning_with_path(tmp_path, caplog):
    path = tmp_path / "nope"
    with caplog.at_level(logging.WARNING):
        assert read_secret_file(str(path)) is None
    assert "secret file not found" in caplog.text
    assert str(path) in caplog.text


def test_empty_file_logs_warning_with_path(tmp_path, caplog):
    f = tmp_path / "secret"
    f.write_text("\n")
    with caplog.at_level(logging.WARNING):
        assert read_secret_file(str(f)) is None
    assert "secret file is empty" in caplog.text
    assert str(f) in caplog.text


def test_unreadable_file_logs_error_without_content(tmp_path, monkeypatch, caplog):
    f = tmp_path / "secret"
    f.write_text("topsecret")

    def deny(*args, **kwargs):
        raise PermissionError(13, "Permission denied", str(f))

    monkeypatch.setattr(secret_file, "open", deny, raising=False)
    with caplog.at_level(logging.ERROR):
        assert read_secret_file(str(f)) is None
    assert "cannot read secret file" in caplog.text
    assert str(f) in caplog.text
    assert "topsecret" not in caplog.text
