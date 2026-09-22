import re
from unittest.mock import MagicMock, patch

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

        client._youtube = fake_youtube  # pula _get_client (não bate na rede real)
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
