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
async def test_get_stream_returns_saved_url():
    svc = make_service()
    svc.store.db_pool.runInteraction.return_value = {
        "room_id": "!r:localhost",
        "playback_url": "https://cdn.example/live/r.m3u8",
    }

    result = await svc.get_stream("!r:localhost")

    assert result["playback_url"] == "https://cdn.example/live/r.m3u8"


@pytest.mark.asyncio
async def test_get_stream_missing_room_id():
    svc = make_service()

    with pytest.raises(SynapseError) as exc:
        await svc.get_stream(None)

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_get_stream_no_channel_configured():
    svc = make_service()
    svc.store.db_pool.runInteraction.return_value = None

    result = await svc.get_stream("!empty:localhost")

    assert result == {"room_id": "!empty:localhost", "playback_url": None}


@pytest.mark.asyncio
async def test_set_stream_requires_admin():
    svc = make_service(is_admin=False)

    with pytest.raises(SynapseError) as exc:
        await svc.set_stream(
            user_id="@user:localhost",
            room_id="!r:localhost",
            playback_url="https://cdn.example/live.m3u8",
        )

    assert exc.value.code == 403
    svc.store.db_pool.runInteraction.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_stream_missing_room_id():
    svc = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await svc.set_stream(
            user_id="@admin:localhost",
            room_id=None,
            playback_url="https://cdn.example/live.m3u8",
        )

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_set_stream_missing_playback_url():
    svc = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await svc.set_stream(
            user_id="@admin:localhost",
            room_id="!r:localhost",
            playback_url="   ",
        )

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_set_stream_success():
    svc = make_service(is_admin=True)

    result = await svc.set_stream(
        user_id="@admin:localhost",
        room_id="!r:localhost",
        playback_url="  https://cdn.example/live.m3u8  ",
    )

    assert result == {"room_id": "!r:localhost", "playback_url": "https://cdn.example/live.m3u8"}
    svc.store.db_pool.runInteraction.assert_awaited_once()
