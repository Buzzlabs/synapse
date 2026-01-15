import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.room_service.resources.is_admin import IsAdminResource

# testa 
# 1. resourse usa usuário autenticado
# 2. user_id vem do requester
# 3. endpoint responde 200
# 4. json retonado tem o formato exato esperado

# para testar: PYTHONPATH=. pytest -vv modules/room_service/tests/test_is_admin.py

@pytest.mark.asyncio
async def test_is_admin_resource_returns_true_for_admin():
    api = MagicMock()

    requester = MagicMock()
    requester.user.to_string.return_value = "@admin:localhost"

    api.get_user_by_req = AsyncMock(return_value=requester)
    api.is_user_admin = AsyncMock(return_value=True)

    resource = IsAdminResource(api)

    request = MagicMock()

    with patch(
        "modules.room_service.resources.is_admin.respond_with_json"
    ) as respond:
        await resource._async_render_GET(request)

        respond.assert_called_once_with(
            request,
            200,
            {
                "user_id": "@admin:localhost",
                "is_admin": True,
            },
        )


@pytest.mark.asyncio
async def test_is_admin_resource_returns_false_for_non_admin():
    api = MagicMock()

    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"

    api.get_user_by_req = AsyncMock(return_value=requester)
    api.is_user_admin = AsyncMock(return_value=False)

    resource = IsAdminResource(api)

    request = MagicMock()

    with patch(
        "modules.room_service.resources.is_admin.respond_with_json"
    ) as respond:
        await resource._async_render_GET(request)

        respond.assert_called_once_with(
            request,
            200,
            {
                "user_id": "@alice:localhost",
                "is_admin": False,
            },
        )
