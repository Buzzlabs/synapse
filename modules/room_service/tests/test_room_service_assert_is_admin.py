import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError
from modules.room_service.service import RoomService

# testa
# 1. código consulta Synapse
# 2. respeita a resposta (false -> bloqueia)
# 3. falha é explícita

#para testar: PYTHONPATH=. pytest -vv modules/room_service/tests/test_room_service_assert_is_admin.py

@pytest.mark.asyncio
async def test_assert_is_admin_allows_admin():
    api = MagicMock()
    api.is_user_admin = AsyncMock(return_value=True)

    service = RoomService(
        api=api,
        admin_user_id="@bot:localhost",
        admin_token="token",
        homeserver="http://localhost",
    )

    await service.assert_is_admin("@alice:localhost")


@pytest.mark.asyncio
async def test_assert_is_admin_blocks_non_admin():
    api = MagicMock()
    api.is_user_admin = AsyncMock(return_value=False)

    service = RoomService(
        api=api,
        admin_user_id="@bot:localhost",
        admin_token="token",
        homeserver="http://localhost",
    )

    with pytest.raises(SynapseError):
        await service.assert_is_admin("@bob:localhost")
