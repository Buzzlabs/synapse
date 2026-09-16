import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError
from modules.youtube_live_service.service import YoutubeLiveService
from modules.youtube_live_service.youtube_client import MockYoutubeClient


def make_service(is_admin=True):
    api = MagicMock()
    api.is_user_admin = AsyncMock(return_value=is_admin)
    return YoutubeLiveService(api=api, youtube_client=MockYoutubeClient())


@pytest.mark.asyncio
async def test_start_broadcast_requires_admin():
    service = make_service(is_admin=False)

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(
            user_id="@user:localhost",
            room_id="!room:localhost",
            title="Minha live",
        )

    assert exc.value.code == 403


@pytest.mark.asyncio
async def test_start_broadcast_with_mock_returns_expected_shape():
    service = make_service(is_admin=True)

    result = await service.start_broadcast(
        user_id="@admin:localhost",
        room_id="!room:localhost",
        title="Minha live de teste",
    )

    assert result["room_id"] == "!room:localhost"
    assert result["watch_url"].startswith("https://www.youtube.com/watch?v=")
    assert result["ingestion_address"] == "rtmp://a.rtmp.youtube.com/live2"
    assert result["stream_key"].startswith("mock-")
    assert len(result["broadcast_id"]) == 11


@pytest.mark.asyncio
async def test_start_broadcast_missing_room_id():
    service = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(user_id="@admin:localhost", room_id=None, title="x")

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_start_broadcast_missing_title():
    service = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(user_id="@admin:localhost", room_id="!r:localhost", title="   ")

    assert exc.value.code == 400
