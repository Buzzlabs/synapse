import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError
from modules.room_streams_service.service import RoomStreamsService


def make_service(is_admin=True):
    api = MagicMock()
    api._hs.get_datastores.return_value.main = MagicMock()
    api.is_user_admin = AsyncMock(return_value=is_admin)
    svc = RoomStreamsService(api=api, homeserver="http://localhost:3000", admin_user_id="@admin:localhost")
    svc.store.db_pool.runInteraction = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_get_stream_defaults_to_fixed_when_unconfigured():
    svc = make_service()
    svc.store.db_pool.runInteraction.return_value = None

    result = await svc.get_stream("!room:localhost")

    assert result == {"room_id": "!room:localhost", "playback_url": None, "provider": "fixed"}


@pytest.mark.asyncio
async def test_set_stream_fixed_requires_playback_url():
    svc = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await svc.set_stream(
            user_id="@admin:localhost",
            room_id="!room:localhost",
            playback_url=None,
            provider="fixed",
        )

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_set_stream_fixed_success():
    svc = make_service(is_admin=True)

    result = await svc.set_stream(
        user_id="@admin:localhost",
        room_id="!room:localhost",
        playback_url="  https://cdn.example/live.m3u8  ",
        provider="fixed",
    )

    assert result == {
        "room_id": "!room:localhost",
        "playback_url": "https://cdn.example/live.m3u8",
        "provider": "fixed",
    }


@pytest.mark.asyncio
async def test_set_stream_youtube_ignores_playback_url():
    svc = make_service(is_admin=True)

    result = await svc.set_stream(
        user_id="@admin:localhost",
        room_id="!room:localhost",
        playback_url="isso deveria ser ignorado",
        provider="youtube",
    )

    assert result == {"room_id": "!room:localhost", "playback_url": None, "provider": "youtube"}


@pytest.mark.asyncio
async def test_set_stream_invalid_provider():
    svc = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await svc.set_stream(
            user_id="@admin:localhost",
            room_id="!room:localhost",
            playback_url="x",
            provider="twitch",
        )

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_set_stream_requires_admin():
    svc = make_service(is_admin=False)

    with pytest.raises(SynapseError) as exc:
        await svc.set_stream(
            user_id="@user:localhost",
            room_id="!room:localhost",
            playback_url="https://cdn.example/live.m3u8",
            provider="fixed",
        )

    assert exc.value.code == 403