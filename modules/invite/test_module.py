import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from twisted.web.test.requesthelper import DummyRequest
from twisted.web.http_headers import Headers

import invite.module as module
from invite.module import InviteResource

# testa:
# _handle consegue processar um POST válido de convite.
# _handle valida a comunidade corretamente ("free").
# _handle chama o endpoint do Synapse para convidar o usuário.
# _handle retorna resposta JSON de sucesso ({"ok": True}) no request.

@pytest.mark.asyncio
async def test_invite_success():
    # Config fake
    config = MagicMock()
    config.admin_token = "admintoken"
    config.homeserver = "http://localhost:8008"
    config.communities = {
        "free": "!roomid:localhost",
    }

    # ModuleApi fake
    api = MagicMock()
    requester = MagicMock()
    requester.user.to_string.return_value = "@alice:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)
    api._hs.get_reactor.return_value = MagicMock()

    # Resource (obj que processa POST /invite)
    resource = InviteResource(api, config)

    # Mock do Agent do twisted e readBody
    response = MagicMock()
    response.code = 200
    resource.agent.request = AsyncMock(return_value=response)
    async def fake_read_body(resp):
        return b"{}"
    module.readBody = fake_read_body

    # Mock do respond_with_json
    def fake_respond_with_json(request, code, json_object, **kwargs):
        request.responseCode = code
        request.written = [json.dumps(json_object).encode()]
        return None

    module.respond_with_json = fake_respond_with_json

    # Request fake
    request = DummyRequest([b"_matrix", b"invite"])
    request.method = b"POST"
    request.requestHeaders = Headers({
        b"Authorization": [b"Bearer usertoken"],
        b"Content-Type": [b"application/json"],
    })
    request.content = BytesIO()
    request.content.write(json.dumps({"community": "free"}).encode())
    request.content.seek(0)

    # Execução
    await resource._handle(request)

    # Asserts
    assert request.responseCode == 200
    body = json.loads(request.written[0].decode())
    assert body["ok"] is True
    resource.agent.request.assert_called_once()
