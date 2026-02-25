import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.room_service.service import RoomService

@pytest.mark.asyncio
async def test_discover_returns_visible_rooms():
    """
    Deve retornar sala quando admin está presente.
    """
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()
    store.get_users_in_room = AsyncMock(
    return_value=["u1", "u2", "u3", "@admin:localhost"]
)

    store.db_pool.runInteraction = AsyncMock(
        return_value=[
            ("!room1:localhost", "group", "public", None, "buzz"),
        ]
    )

    hs.get_datastores.return_value.main = store

    api.get_state_events_in_room = AsyncMock(
        return_value=[
            MagicMock(content={"name": "Buzz Room"})
        ]
    )

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    service._ensure_admin = AsyncMock()

    rooms = await service.discover()

    assert rooms == [
        {
            "room_id": "!room1:localhost",
            "name": "Buzz Room",
            "room_kind": "group",
            "access_type": "public",
            "price": None,
            "keyword": "buzz",
            "member_count": 4,
        }
    ]

@pytest.mark.asyncio
async def test_discover_skips_when_admin_not_in_room():
    """
    Deve ignorar sala se admin não estiver nela.
    """

    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()
    store.db_pool.runInteraction = AsyncMock(
        return_value=[
            ("!room1:localhost", "group", "private", 100, "buzz"),
        ]
    )
    store.get_users_in_room = AsyncMock(
        return_value=["@user:localhost"]
    )

    hs.get_datastores.return_value.main = store

    api.get_state_events_in_room = AsyncMock(return_value=[])

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    rooms = await service.discover()

    assert rooms == []


@pytest.mark.asyncio
async def test_discover_uses_default_name():
    """
    Deve usar 'Sem nome' quando sala não possui m.room.name.
    """

    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()
    store.db_pool.runInteraction = AsyncMock(
        return_value=[
            ("!room1:localhost", "group", "private", 100, "buzz"),
        ]
    )
    store.get_users_in_room = AsyncMock(
        return_value=["@admin:localhost"]
    )

    hs.get_datastores.return_value.main = store

    api.get_state_events_in_room = AsyncMock(return_value=[])

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    rooms = await service.discover()

    assert rooms[0]["name"] == "Sem nome"