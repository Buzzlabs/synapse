import pytest
from unittest.mock import AsyncMock, MagicMock
from synapse.api.errors import SynapseError

from modules.room_service.service import RoomService

# testa: 
# 1. _ensure_admin sempre tenta forçar o admin na sala
# 2. erro 403 é tratado como esperado (admin já está na sala)
# 3. qualquer outro erro explode visivelmente
# 4. o teste não depende do Synapse, HTTP, banco ou reactor

# para testar: PYTHONPATH=. pytest -vv modules/room_service/tests/test_room_service_ensure_admin.py

@pytest.mark.asyncio
async def test_ensure_admin_calls_admin_join():
    api = MagicMock()

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    service._admin_join = AsyncMock()

    await service._ensure_admin("!room:localhost")

    service._admin_join.assert_called_once_with(
        "!room:localhost",
        "@admin:localhost",
    )


@pytest.mark.asyncio
async def test_ensure_admin_ignores_403():
    api = MagicMock()

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    service._admin_join = AsyncMock(
        side_effect=SynapseError(403, "Forbidden")
    )

    await service._ensure_admin("!room:localhost")


@pytest.mark.asyncio
async def test_ensure_admin_raises_other_errors():
    api = MagicMock()

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:8008",
    )

    service._admin_join = AsyncMock(
        side_effect=SynapseError(500, "boom")
    )

    with pytest.raises(SynapseError):
        await service._ensure_admin("!room:localhost")


