import pytest
import requests_mock
from rest_auth_provider.rest_auth_provider import RestAuthProvider

## testa: 
## - rest auth provider é importável
## - o endpoint rest está sendo chamado corretamente
## - JSON está sendo interpretado certo
## - check_password() funciona
## - provider não depende do synapse pra funcionar (isolado completamente)

class FakeAccountHandler:
    async def check_user_exists(self, user_id):
        return True

@pytest.mark.asyncio
async def test_check_password_success():
    config = type("Config", (), {
        "endpoint": "http://0.0.0.0:9000",
        "regLower": True,
        "setNameOnRegister": False,
        "setNameOnLogin": False,
        "updateThreepid": False,
    })

    provider = RestAuthProvider(config, FakeAccountHandler())

    with requests_mock.Mocker() as m:
        m.post(
            "http://0.0.0.0:9000/_matrix-internal/identity/v1/check_credentials",
            json={"auth": {"success": True}},
        )

        ok = await provider.check_password("@alice:test", "senha")
        assert ok is True
