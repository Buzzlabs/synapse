import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.api.errors import SynapseError

from modules.room_service.service import RoomService

# testa 
# 1. se o admin não estiver na sala, chama join_room corretamente
# 2. se algo der errado, o código falha de forma visível

# para testar:  PYTHONPATH=. pytest -vv modules/room_service/tests/test_room_service_ensure_admin.py

@pytest.mark.asyncio
async def test_ensure_admin_calls_join_room():
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    room_member_handler = MagicMock()
    room_member_handler.join_room = AsyncMock()

    hs.get_room_member_handler.return_value = room_member_handler

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    await service._ensure_admin("!room:localhost")

    room_member_handler.join_room.assert_called_once_with(
        user_id="@admin:localhost",
        room_id="!room:localhost",
        ratelimit=False,
        remote_room_hosts=[],
    )

@pytest.mark.asyncio
async def test_ensure_admin_ignores_403():
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    room_member_handler = MagicMock()
    room_member_handler.join_room = AsyncMock(
        side_effect=SynapseError(403, "Forbidden")
    )

    hs.get_room_member_handler.return_value = room_member_handler

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    # não deve lançar exceção
    await service._ensure_admin("!room:localhost")

@pytest.mark.asyncio
async def test_ensure_admin_raises_other_errors():
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    room_member_handler = MagicMock()
    room_member_handler.join_room = AsyncMock(
        side_effect=SynapseError(500, "boom")
    )

    hs.get_room_member_handler.return_value = room_member_handler

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    with pytest.raises(SynapseError):
        await service._ensure_admin("!room:localhost")
