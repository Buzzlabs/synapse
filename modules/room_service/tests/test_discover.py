import pytest
from unittest.mock import AsyncMock, MagicMock

from twisted.web.test.requesthelper import DummyRequest

from modules.room_service.resources.discover import DiscoverRoomResource

# testa
# 1. endpoint /discover funciona como contrato http
# 2. formato da resposta está correto
# 3. campos que o app usa estão corretos
# 4. o resource chama a regra de negócio certa

# para testar: PYTHONPATH=. pytest modules/room_service/tests/test_discover.py

@pytest.mark.asyncio
async def test_discover_success():
    api = MagicMock()

    service = MagicMock()
    service.discover = AsyncMock(return_value=[
        {
            "room_id": "!room:localhost",
            "name": "Sala Teste",
            "room_kind": "group",
            "access_type": "free",
            "price": 0,
            "keyword": "buzz",
            "member_count": 3,
        }
    ])

    resource = DiscoverRoomResource(api, service)

    request = DummyRequest([b"_synapse", b"room_service", b"discover"])

    code, body = await resource._async_render_GET(request)

    assert code == 200
    assert "rooms" in body
    assert len(body["rooms"]) == 1

    room = body["rooms"][0]
    assert room["name"] == "Sala Teste"
    assert room["member_count"] == 3

    service.discover.assert_called_once()
