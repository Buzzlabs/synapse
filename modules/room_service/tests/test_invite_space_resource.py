import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from io import BytesIO

from twisted.web.test.requesthelper import DummyRequest
from twisted.web.http_headers import Headers

from modules.room_service.resources.invite_space import InviteSpaceResource


@pytest.mark.asyncio
async def test_invite_space_success():
    """
    Deve retornar 200 e a lista de salas em que o usuário entrou.
    """
    api = MagicMock()

    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)

    service = MagicMock()
    service.invite_space = AsyncMock(
        return_value=["!room1:localhost", "!room2:localhost"]
    )
    service.admin_user_id = "@admin:localhost"

    resource = InviteSpaceResource(api, service)

    request = DummyRequest([b"_synapse", b"room_service", b"invite_space"])
    request.method = b"POST"
    request.requestHeaders = Headers({
        b"Content-Type": [b"application/json"],
    })
    request.content = BytesIO(
        json.dumps({"space_id": "!space:localhost"}).encode()
    )

    code, body = await resource._async_render_POST(request)

    assert code == 200
    assert body["joined"] is True
    assert body["rooms"] == ["!room1:localhost", "!room2:localhost"]

    service.invite_space.assert_awaited_once_with(
        user_id="@alice:localhost",
        space_id="!space:localhost",
    )


@pytest.mark.asyncio
async def test_invite_space_missing_space_id():
    """
    Deve retornar 400 quando space_id não é enviado.
    """
    api = MagicMock()
    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)

    service = MagicMock()
    service.admin_user_id = "@admin:localhost"

    resource = InviteSpaceResource(api, service)

    request = DummyRequest([b"_synapse", b"room_service", b"invite_space"])
    request.method = b"POST"
    request.content = BytesIO(b"{}")

    code, body = await resource._async_render_POST(request)

    assert code == 400
    assert body["error"] == "missing space_id"


@pytest.mark.asyncio
async def test_invite_space_propagates_not_found():
    """
    Erros do service (ex: space vazio -> 404) devem ser repassados.
    """
    from synapse.api.errors import SynapseError

    api = MagicMock()
    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)

    service = MagicMock()
    service.admin_user_id = "@admin:localhost"
    service.invite_space = AsyncMock(
        side_effect=SynapseError(404, "Space not found or empty")
    )

    resource = InviteSpaceResource(api, service)

    request = DummyRequest([b"_synapse", b"room_service", b"invite_space"])
    request.method = b"POST"
    request.content = BytesIO(
        json.dumps({"space_id": "!empty:localhost"}).encode()
    )

    code, body = await resource._async_render_POST(request)

    assert code == 404
    assert body["error"] == "Space not found or empty"