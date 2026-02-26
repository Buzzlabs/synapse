import pytest
from unittest.mock import MagicMock, AsyncMock
from synapse.api.errors import SynapseError

from modules.room_service.service import RoomService


@pytest.mark.asyncio
async def test_is_user_in_room_true():
    """
    Deve retornar True quando usuário está na sala.
    """

    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()
    store.get_users_in_room = AsyncMock(
        return_value=["@admin:localhost"]
    )

    hs.get_datastores.return_value.main = store

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    result = await service._is_user_in_room(
        "!room:localhost",
        "@admin:localhost",
    )

    assert result is True


@pytest.mark.asyncio
async def test_ensure_admin_ignores_403():
    """
    Deve ignorar erro 403 ao tentar garantir admin.
    """

    api = MagicMock()
    hs = MagicMock()
    api._hs = hs
    hs.get_datastores.return_value.main = MagicMock()

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    service._admin_join = AsyncMock(
        side_effect=SynapseError(403, "already joined")
    )

    await service._ensure_admin("!room:localhost")


@pytest.mark.asyncio
async def test_admin_join_raises_on_error():
    """
    Deve lançar erro quando resposta HTTP != 200/403.
    """

    api = MagicMock()
    hs = MagicMock()
    api._hs = hs
    hs.get_datastores.return_value.main = MagicMock()

    agent = MagicMock()
    response = MagicMock()
    response.code = 500
    agent.request = AsyncMock(return_value=response)

    from modules.room_service import service as service_module
    service_module.readBody = AsyncMock(return_value=b"boom")

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )
    service.agent = agent

    with pytest.raises(SynapseError):
        await service._admin_join("!room:localhost", "@admin:localhost")