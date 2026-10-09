import logging
from unittest.mock import MagicMock

import pytest

from modules.youtube_live_service.module import _read_secret_file, build_youtube_client
from modules.youtube_live_service.youtube_client import (
    MockYoutubeClient,
    RealYoutubeClient,
    UnconfiguredYoutubeClient,
    YoutubeNotConfiguredError,
)


@pytest.fixture
def secrets(tmp_path):
    secret = tmp_path / "client_secret.txt"
    secret.write_text("the-secret\n")
    token = tmp_path / "refresh_token.txt"
    token.write_text("the-token\n")
    return {
        "youtube_client_id": "id.apps.googleusercontent.com",
        "youtube_client_secret_file": str(secret),
        "youtube_refresh_token_file": str(token),
    }


def test_full_credentials_use_real_client(secrets):
    client = build_youtube_client(secrets, MagicMock())

    assert isinstance(client, RealYoutubeClient)
    assert client.client_secret == "the-secret"  # .strip() aplicado
    assert client.refresh_token == "the-token"


def test_mock_only_when_explicitly_requested(caplog):
    with caplog.at_level(logging.WARNING):
        client = build_youtube_client({"youtube_use_mock": True}, MagicMock())

    assert isinstance(client, MockYoutubeClient)
    assert "FAKE" in caplog.text


def test_empty_config_does_not_fall_back_to_mock(caplog):
    """Regressão do review: config vazia NÃO pode virar mock em silêncio."""
    with caplog.at_level(logging.ERROR):
        client = build_youtube_client({}, MagicMock())

    assert isinstance(client, UnconfiguredYoutubeClient)
    assert not isinstance(client, MockYoutubeClient)
    assert "NOT configured" in caplog.text


def test_secret_mounted_at_wrong_path_is_unconfigured_not_mock(secrets):
    """O cenário do review: secret montado no lugar errado em produção."""
    secrets["youtube_client_secret_file"] = "/nonexistent/client_secret.txt"

    client = build_youtube_client(secrets, MagicMock())

    assert isinstance(client, UnconfiguredYoutubeClient)
    assert "youtube_client_secret_file" in client.reason


def test_reason_lists_only_what_is_missing(secrets):
    del secrets["youtube_client_id"]

    client = build_youtube_client(secrets, MagicMock())

    assert client.reason == "missing or unreadable config: youtube_client_id"


def test_reason_never_contains_secret_values(secrets):
    del secrets["youtube_refresh_token_file"]

    client = build_youtube_client(secrets, MagicMock())

    assert "the-secret" not in client.reason
    assert "the-token" not in client.reason


def test_use_mock_false_is_not_mock():
    client = build_youtube_client({"youtube_use_mock": False}, MagicMock())

    assert isinstance(client, UnconfiguredYoutubeClient)


@pytest.mark.asyncio
async def test_unconfigured_client_raises_on_create():
    client = UnconfiguredYoutubeClient("missing or unreadable config: youtube_client_id")

    with pytest.raises(YoutubeNotConfiguredError):
        await client.create_broadcast("Minha live")


class TestReadSecretFile:
    def test_directory_does_not_crash_startup(self, tmp_path):
        # secret montado como diretório: antes abortava o Synapse
        assert _read_secret_file(str(tmp_path)) is None

    def test_empty_file_is_treated_as_missing(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("  \n")
        assert _read_secret_file(str(f)) is None

    def test_none_path(self):
        assert _read_secret_file(None) is None