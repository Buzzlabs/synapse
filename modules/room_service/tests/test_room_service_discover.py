import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.room_service.service import RoomService

# testa:
# 1. lista apenas salas visíveis
# 2. tenta garantir admin em cada sala
# 3. retorna dados consistentes pra UI
# 4. calcula corretamente o número de membros

# para testar: PYTHONPATH=. pytest modules/room_service/tests/test_room_service_discover.py -vv

@pytest.mark.asyncio
async def test_discover_returns_visible_rooms():
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()
    store.get_users_in_room = AsyncMock(return_value=["u1", "u2", "u3"])

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
            "member_count": 3,
        }
    ]

    service._ensure_admin.assert_awaited_once_with("!room1:localhost")
