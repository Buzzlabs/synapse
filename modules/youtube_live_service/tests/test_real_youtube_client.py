import pytest
from unittest.mock import patch

from modules.youtube_live_service.youtube_client import RealYoutubeClient, YoutubeBroadcastInfo


@pytest.mark.asyncio
async def test_real_client_dispatches_to_thread_and_returns_info():
    """
    Confirma que create_broadcast (async) chama corretamente a parte
    síncrona via run_in_executor, sem travar, e monta o YoutubeBroadcastInfo
    esperado a partir do retorno "cru" da API (aqui mockado).
    """
    client = RealYoutubeClient(
        client_id="fake-client-id",
        client_secret="fake-secret",
        refresh_token="fake-refresh-token",
    )

    fake_info = YoutubeBroadcastInfo(
        broadcast_id="abc123XYZ_9",
        watch_url="https://www.youtube.com/watch?v=abc123XYZ_9",
        ingestion_address="rtmp://a.rtmp.youtube.com/live2",
        stream_key="real-stream-key-123",
    )

    # substitui só a parte síncrona/bloqueante (as chamadas HTTP reais)
    with patch.object(client, "_create_broadcast_sync", return_value=fake_info) as mock_sync:
        result = await client.create_broadcast("Minha live real")

    mock_sync.assert_called_once_with("Minha live real")
    assert result == fake_info
    assert result.watch_url == "https://www.youtube.com/watch?v=abc123XYZ_9"


@pytest.mark.asyncio
async def test_real_client_propagates_errors():
    """Se a chamada à API falhar, o erro deve subir, não ser engolido."""
    client = RealYoutubeClient(
        client_id="fake-client-id",
        client_secret="fake-secret",
        refresh_token="fake-refresh-token",
    )

    with patch.object(client, "_create_broadcast_sync", side_effect=RuntimeError("API down")):
        with pytest.raises(RuntimeError, match="API down"):
            await client.create_broadcast("Vai falhar")
