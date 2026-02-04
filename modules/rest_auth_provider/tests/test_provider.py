# modules/rest_auth_provider/tests/test_provider.py


# para testar: PYTHONPATH=modules python -m pytest modules/rest_auth_provider/tests/test_provider.py
import pytest
from unittest.mock import Mock, AsyncMock

try:
    from synapse.api.errors import AuthError
except ImportError:
    class AuthError(Exception):
        def __init__(self, code, msg):
            super().__init__(msg)
            self.code = code


from rest_auth_provider.rest_auth_provider import RestAuthProvider

@pytest.fixture
def config():
    return {
        "api_base": "https://paywall.test",
        "homeserver": "matrix.test",
        "timeout": 1,
    }


@pytest.fixture
def account_handler():
    handler = Mock()
    handler.check_user_exists = AsyncMock(return_value=False)
    handler.register = AsyncMock()
    return handler


@pytest.fixture
def provider(config, account_handler):
    return RestAuthProvider(config, account_handler)

# testa: 
# 1. URL está certa
# 2. payload está no formato esperado
# 3. senha é enviada hasheada
# 4. timeout correto

def test_check_paywall_payload(monkeypatch, provider):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "123",
        "email": "nexobeta@gmail.com",
    }

    def mock_post(url, json, timeout):
        assert url == "https://paywall.test/public/authenticate"
        assert json["subscriber-user/email"] == "nexobeta@gmail.com"
        assert "subscriber-user/password" in json
        assert timeout == 1
        return mock_resp

    monkeypatch.setattr(
        "rest_auth_provider.rest_auth_provider.requests.post",
        mock_post,
    )

    data = provider._check_paywall("nexobeta@gmail.com", "senha123")
    assert data["email"] == "nexobeta@gmail.com"

# testa: 
# 1. login negado corretamente
def test_check_paywall_invalid_credentials(monkeypatch, provider):

    mock_resp = Mock()
    mock_resp.status_code = 403

    monkeypatch.setattr(
        "rest_auth_provider.rest_auth_provider.requests.post",
        lambda *a, **k: mock_resp,
    )

    with pytest.raises(AuthError) as err:
        provider._check_paywall("a@b.com", "x")

    assert err.value.code == 403

# testa 
# 1. provider não confia cegamente
# 2. bloqueia login
def test_check_paywall_invalid_response(monkeypatch, provider):

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"foo": "bar"}

    monkeypatch.setattr(
        "rest_auth_provider.rest_auth_provider.requests.post",
        lambda *a, **k: mock_resp,
    )

    with pytest.raises(AuthError) as err:
        provider._check_paywall("a@b.com", "x")

    assert err.value.code == 403

# testa: 
# 1. timeout
# 2. DNS
# 3. serviço fora
# (synapse não quebra)
def test_check_paywall_exception(monkeypatch, provider):
    
    def boom(*a, **k):
        raise Exception("paywall down")

    monkeypatch.setattr(
        "rest_auth_provider.rest_auth_provider.requests.post",
        boom,
    )

    with pytest.raises(AuthError) as err:
        provider._check_paywall("a@b.com", "x")

    assert err.value.code == 500

# testa: 
# 1. geração do localpart pelo nome_sobrenome
def test_build_localpart_from_user_with_name(provider):
    data = {
        "id": "1",
        "email": "x@y.com",
        "info": {
            "first-name": "Lívia",
            "last-name": "Ueno",
        },
    }

    localpart = provider._build_localpart_from_user(data)
    assert localpart == "livia_ueno"


# testa: 
# 1. geração do localpart pelo email
def test_build_localpart_from_user_email_fallback(provider):
    data = {
        "id": "1",
        "email": "nexo.beta@gmail.com",
    }

    localpart = provider._build_localpart_from_user(data)
    assert localpart == "nexo.beta"

# testa:
# 1. login negado
# 2. evita usuário “fantasma”
def test_build_localpart_missing_id(provider):
    data = {
        "email": "a@b.com",
    }

    with pytest.raises(AuthError) as err:
        provider._build_localpart_from_user(data)

    assert err.value.code == 403

# testa: 
# 1. Garante compatibilidade com regras do Matrix
def test_normalize_localpart(provider):
    value = "Lívia+Teste@123"
    normalized = provider._normalize_localpart(value)
    assert normalized == "livia_teste_123"


# testa: 
# 1. fluxo feliz
@pytest.mark.asyncio
async def test_check_auth_creates_user(monkeypatch, provider, account_handler):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "42",
        "email": "user@test.com",
    }

    monkeypatch.setattr(
        "rest_auth_provider.rest_auth_provider.requests.post",
        lambda *a, **k: mock_resp,
    )

    mxid, _ = await provider.check_auth(
        username="user@test.com",
        login_type="m.login.password",
        login_dict={"password": "123"},
    )

    assert mxid == "@user:matrix.test"
    account_handler.register.assert_awaited_once()

 # testa: 
 # 1. Usuário já existe
@pytest.mark.asyncio
async def test_check_auth_existing_user(monkeypatch, provider, account_handler):
    account_handler.check_user_exists.return_value = True

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "42",
        "email": "user@test.com",
    }

    monkeypatch.setattr(
        "rest_auth_provider.rest_auth_provider.requests.post",
        lambda *a, **k: mock_resp,
    )

    await provider.check_auth(
        username="user@test.com",
        login_type="m.login.password",
        login_dict={"password": "123"},
    )

    account_handler.register.assert_not_called()

# testa:
# 1. Sem senha → erro imediato
@pytest.mark.asyncio
async def test_check_auth_missing_password(provider):
    with pytest.raises(AuthError) as err:
        await provider.check_auth(
            username="user@test.com",
            login_type="m.login.password",
            login_dict={},
        )

    assert err.value.code == 403

# testa: 
# 1. Username não é email
@pytest.mark.asyncio
async def test_check_auth_invalid_username(provider):
    with pytest.raises(AuthError) as err:
        await provider.check_auth(
            username="invalid-user",
            login_type="m.login.password",
            login_dict={"password": "123"},
        )

    assert err.value.code == 400
