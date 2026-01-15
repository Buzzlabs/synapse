import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from io import BytesIO

from twisted.web.test.requesthelper import DummyRequest
from twisted.web.http_headers import Headers

from modules.room_service.resources.invite import InviteRoomResource

# testa:
# 1. o endpoint /invite funciona como contrato http
# 2. o resource chama a regra de negócio certa (roomservice.join_by_keyword)
# 3. erros de domínio viram erros http corretos
# 4. endpoint independente do synapse

# para testar: PYTHONPATH=. pytest modules/room_service/tests/test_invite.py

@pytest.mark.asyncio
async def test_invite_room_success():
    api = MagicMock()

    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)

    service = MagicMock()
    service.join_by_keyword = AsyncMock()
    service.admin_user_id = "@admin:localhost"

    resource = InviteRoomResource(api, service)

    request = DummyRequest([b"_synapse", b"room_service", b"invite"])
    request.method = b"POST"
    request.requestHeaders = Headers({
        b"Content-Type": [b"application/json"],
    })

    request.content = BytesIO(
        json.dumps({"keyword": "buzz"}).encode()
    )

    code, body = await resource._async_render_POST(request)

    assert code == 200
    assert body == {"joined": True}

    service.join_by_keyword.assert_awaited_once_with(
        target_user_id="@alice:localhost",
        keyword="buzz",
    )

@pytest.mark.asyncio
async def test_invite_room_missing_keyword():
    api = MagicMock()
    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)

    service = MagicMock()
    service.admin_user_id = "@admin:localhost"

    resource = InviteRoomResource(api, service)

    request = DummyRequest([b"_synapse", b"room_service", b"invite"])
    request.method = b"POST"
    request.content = BytesIO(b"{}")

    code, body = await resource._async_render_POST(request)

    assert code == 400
    assert body["error"] == "missing keyword"
