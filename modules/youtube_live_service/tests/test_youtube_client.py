import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.youtube_live_service.youtube_client import (
    MockYoutubeClient,
    RealYoutubeClient,
    YoutubeBroadcastInfo,
)


@pytest.mark.asyncio
async def test_mock_client_returns_plausible_fake_data():
    client = MockYoutubeClient()

    info = await client.create_broadcast("Minha live de teste")

    assert len(info.broadcast_id) == 11  # video ids do youtube têm 11 chars
    assert info.watch_url == f"https://www.youtube.com/watch?v={info.broadcast_id}"
    assert info.ingestion_address == "rtmp://a.rtmp.youtube.com/live2"
    assert info.stream_key.startswith("mock-")


class TestRealYoutubeClientSync:
    """
    Testa _create_broadcast_sync isoladamente (é uma função síncrona comum,
    não depende do reactor do Twisted para ser testada). O despacho via
    deferToThread (create_broadcast, a parte async) não é re-testado aqui —
    deferToThread é uma primitiva do próprio Twisted; a integração completa
    foi validada manualmente contra a API real do YouTube, rodando dentro
    do Synapse (onde o reactor está de fato ativo).
    """

    def make_client_with_mocked_api(self):
        client = RealYoutubeClient(
            client_id="fake-id",
            client_secret="fake-secret",
            refresh_token="fake-refresh-token",
            api=MagicMock(),
        )

        fake_youtube = MagicMock()
        fake_youtube.liveBroadcasts.return_value.insert.return_value.execute.return_value = {
            "id": "abc123XYZ_9",
        }
        fake_youtube.liveStreams.return_value.insert.return_value.execute.return_value = {
            "id": "stream-1",
            "cdn": {
                "ingestionInfo": {
                    "ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
                    "streamName": "real-stream-key-123",
                }
            },
        }
        fake_youtube.liveBroadcasts.return_value.bind.return_value.execute.return_value = {}

        client._build_client = MagicMock(return_value=fake_youtube)  # sem rede
        return client, fake_youtube

    def test_returns_broadcast_info_from_api_responses(self):
        client, _ = self.make_client_with_mocked_api()

        info = client._create_broadcast_sync("Minha live")

        assert info == YoutubeBroadcastInfo(
            broadcast_id="abc123XYZ_9",
            watch_url="https://www.youtube.com/watch?v=abc123XYZ_9",
            ingestion_address="rtmp://a.rtmp.youtube.com/live2",
            stream_key="real-stream-key-123",
        )

    def test_sends_scheduled_start_time_in_iso8601_utc(self):
        """
        Regression test: a API do YouTube rejeita liveBroadcasts.insert sem
        snippet.scheduledStartTime, mesmo para início imediato
        (scheduledStartTimeRequired). Confirma que o campo é enviado no
        formato esperado (ISO 8601, sufixo Z).
        """
        client, fake_youtube = self.make_client_with_mocked_api()

        client._create_broadcast_sync("Minha live")

        insert_call = fake_youtube.liveBroadcasts.return_value.insert
        body = insert_call.call_args.kwargs["body"]

        assert "scheduledStartTime" in body["snippet"]
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
            body["snippet"]["scheduledStartTime"],
        )

    def test_sends_auto_start_and_auto_stop(self):
        client, fake_youtube = self.make_client_with_mocked_api()

        client._create_broadcast_sync("Minha live")

        body = fake_youtube.liveBroadcasts.return_value.insert.call_args.kwargs["body"]
        assert body["contentDetails"]["enableAutoStart"] is True
        assert body["contentDetails"]["enableAutoStop"] is True

    def test_binds_broadcast_to_the_created_stream(self):
        client, fake_youtube = self.make_client_with_mocked_api()

        client._create_broadcast_sync("Minha live")

        bind_call = fake_youtube.liveBroadcasts.return_value.bind
        bind_call.assert_called_once()
        assert bind_call.call_args.kwargs["id"] == "abc123XYZ_9"
        assert bind_call.call_args.kwargs["streamId"] == "stream-1"

    def test_propagates_api_errors(self):
        client, fake_youtube = self.make_client_with_mocked_api()
        fake_youtube.liveBroadcasts.return_value.insert.return_value.execute.side_effect = RuntimeError(
            "Scheduled start time is required"
        )

        with pytest.raises(RuntimeError, match="Scheduled start time is required"):
            client._create_broadcast_sync("Minha live")


class TestRealYoutubeClientAsync:
    """
    Antes não dava para testar create_broadcast: o deferToThread cru do
    Twisted exigia o reactor rodando. Com api.defer_to_thread injetado, dá.
    """

    def make_client(self):
        api = MagicMock()
        # defer_to_thread falso: executa a função na hora, como o real faria
        api.defer_to_thread = AsyncMock(side_effect=lambda f, *a, **k: f(*a, **k))
        client = RealYoutubeClient(
            client_id="fake-id",
            client_secret="fake-secret",
            refresh_token="fake-refresh-token",
            api=api,
        )
        return client, api

    @pytest.mark.asyncio
    async def test_create_broadcast_runs_in_synapse_thread_pool(self):
        client, api = self.make_client()
        expected = YoutubeBroadcastInfo("abc", "https://y/abc", "rtmp://x", "key")

        with patch.object(client, "_create_broadcast_sync", return_value=expected) as sync:
            result = await client.create_broadcast("Minha live")

        assert result == expected
        # `sync` já é o mock que substituiu o método: é ele que deve ter
        # sido entregue ao thread pool do Synapse, junto com o título.
        api.defer_to_thread.assert_awaited_once_with(sync, "Minha live")
        sync.assert_called_once_with("Minha live")

    @pytest.mark.asyncio
    async def test_create_broadcast_propagates_errors(self):
        client, _ = self.make_client()

        with patch.object(client, "_create_broadcast_sync", side_effect=RuntimeError("API down")):
            with pytest.raises(RuntimeError, match="API down"):
                await client.create_broadcast("Vai falhar")

    def test_each_call_builds_its_own_google_client(self):
        """
        Regressão do review: o Resource do Google (httplib2) não é thread-safe,
        então dois broadcasts não podem compartilhar o mesmo client.
        """
        client, _ = self.make_client()
        built = []

        def fake_build():
            fake = MagicMock()
            fake.liveBroadcasts.return_value.insert.return_value.execute.return_value = {"id": "b"}
            fake.liveStreams.return_value.insert.return_value.execute.return_value = {
                "id": "s",
                "cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://x", "streamName": "k"}},
            }
            built.append(fake)
            return fake

        client._build_client = fake_build

        client._create_broadcast_sync("Live 1")
        client._create_broadcast_sync("Live 2")

        assert len(built) == 2
        assert built[0] is not built[1]