import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from io import BytesIO
from twisted.web.test.requesthelper import DummyRequest
from twisted.web.http_headers import Headers

import modules.discover_rooms.module as module
from modules.discover_rooms.module import DiscoverRoomsResource

# testa:
# autenticação é chamada
# admin rooms são buscadas
# state events são lidos corretamente
# member count funciona
# ROOM_CONFIG funciona
# JSON final está correto

@pytest.mark.asyncio
async def test_discover_rooms_get_success():

    # Config fake e API fake
    admin_user_id = "@admin:localhost"
    api = MagicMock()
    requester = MagicMock()
    requester.user.to_string.return_value = "@user:localhost"
    api.get_user_by_req = AsyncMock(return_value=requester)

    # Fake do banco
    store = MagicMock()
    store.get_rooms_for_user = AsyncMock(return_value=[
        "!gkOveurKVZZOeNOYDN:localhost",
        "!rBuRzPVGpFsVohvUEK:localhost"
    ])
    store.get_users_in_room = AsyncMock(side_effect=[
        ["@user1:localhost", "@user2:localhost"],  # sala 1
        ["@user1:localhost"]                        # sala 2
    ])
    api._hs.get_datastores.return_value.main = store

    event_free = MagicMock()
    event_free.content = {"name": "Sala Grátis"}

    event_paid = MagicMock()
    event_paid.content = {"name": "Sala Paga"}

    api.get_state_events_in_room = AsyncMock(side_effect=[
        [event_free],
        [event_paid],
    ])

    # Resource
    resource = DiscoverRoomsResource(api, admin_user_id)

    # Mock do respond_with_json
    def fake_respond_with_json(request, code, json_object, **kwargs):
        request.responseCode = code
        request.written = [json.dumps(json_object).encode()]
        return None
    module.respond_with_json = fake_respond_with_json

    # Request fake
    request = DummyRequest([b"_matrix", b"rooms"])
    request.method = b"GET"
    request.requestHeaders = Headers({b"Authorization": [b"Bearer token"]})
    request.content = BytesIO()

    # Execução
    await resource._handle(request)

    # Asserts
    assert request.responseCode == 200
    body = json.loads(request.written[0].decode())
    assert len(body) == 2

    assert body[0]["room_id"] == "!gkOveurKVZZOeNOYDN:localhost"
    assert body[0]["name"] == "Sala Grátis"
    assert body[0]["member_count"] == 2
    assert body[0]["type"] == "free"
    assert body[0]["price"] == 0

    assert body[1]["room_id"] == "!rBuRzPVGpFsVohvUEK:localhost"
    assert body[1]["name"] == "Sala Paga"
    assert body[1]["member_count"] == 1
    assert body[1]["type"] == "paid"
    assert body[1]["price"] == 1990
