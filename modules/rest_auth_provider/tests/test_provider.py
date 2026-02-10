import pytest
from unittest.mock import Mock, AsyncMock
from types import SimpleNamespace

from rest_auth_provider.rest_auth_provider import RestAuthProvider, AuthError
import rest_auth_provider.rest_auth_provider as provider_module

@pytest.fixture
def config():
    return {
        "api_base": "https://paywall.test",
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

def test_check_paywall_rejects_invalid_credentials(monkeypatch, provider):
    account_handler.register = AsyncMock()
    mock_resp = Mock()
    mock_resp.status_code = 403

    fake_requests = Mock()
    fake_requests.post = lambda *a, **k: mock_resp
    monkeypatch.setattr(provider_module, "requests", fake_requests)

    with pytest.raises(AuthError) as err:
        provider._check_paywall("a@b.com", "x")

    assert err.value.code == 403
    assert "Invalid credentials" in str(err.value)
    account_handler.register.assert_not_awaited()

def test_check_paywall_rejects_invalid_response(monkeypatch, provider):
    account_handler.register = AsyncMock()
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"foo": "bar"}

    fake_requests = Mock()
    fake_requests.post = lambda *a, **k: mock_resp
    monkeypatch.setattr(provider_module, "requests", fake_requests)

    with pytest.raises(AuthError) as err:
        provider._check_paywall("a@b.com", "x")

    assert err.value.code == 403
    assert "Invalid response" in str(err.value)
    account_handler.register.assert_not_awaited()

def test_check_paywall_handles_network_errors(monkeypatch, provider):
    account_handler.register = AsyncMock()
    def boom(*a, **k):
        raise Exception("paywall down")

    fake_requests = Mock()
    fake_requests.post = boom
    monkeypatch.setattr(provider_module, "requests", fake_requests)

    with pytest.raises(AuthError) as err:
        provider._check_paywall("a@b.com", "x")

    assert err.value.code == 500
    assert "Authentication service error" in str(err.value)
    account_handler.register.assert_not_awaited()

def test_build_localpart_requires_user_id(provider):
    account_handler.register = AsyncMock()
    data = {"email": "a@b.com"}

    with pytest.raises(AuthError) as err:
        provider._build_localpart_from_user(data)

    assert err.value.code == 403
    assert "User ID missing" in str(err.value)
    account_handler.register.assert_not_awaited()

@pytest.mark.asyncio
async def test_check_auth_creates_user_when_not_existing_using_firstname_and_lastname(
    monkeypatch, provider, account_handler
):
    provider._hs = SimpleNamespace()

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "42",
        "email": "email@test.com",
        "info": {
            "first-name": "user",
             "last-name": "user",
        },
    }

    fake_requests = Mock()
    fake_requests.post = lambda *a, **k: mock_resp
    monkeypatch.setattr(provider_module, "requests", fake_requests)

    mxid, _ = await provider.check_auth(
        username="user@test.com",
        login_type="m.login.password",
        login_dict={"password": "123"},
    )

    assert mxid.startswith("@user_user:")
    account_handler.register.assert_awaited_once()

@pytest.mark.asyncio
async def test_check_auth_creates_user_when_not_existing_using_email(
    monkeypatch, provider, account_handler
):
    provider._hs = SimpleNamespace()

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "42",
        "email": "email@test.com",
        "info": {
            "first-name": "",
             "last-name": "",
        },
    }

    fake_requests = Mock()
    fake_requests.post = lambda *a, **k: mock_resp
    monkeypatch.setattr(provider_module, "requests", fake_requests)

    mxid, _ = await provider.check_auth(
        username="user@test.com",
        login_type="m.login.password",
        login_dict={"password": "123"},
    )

    assert mxid.startswith("@email:")
    account_handler.register.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_auth_does_not_recreate_existing_user(monkeypatch, config):
    account_handler = Mock()
    account_handler.check_user_exists = AsyncMock(return_value=True)
    account_handler.register = AsyncMock()

    provider = RestAuthProvider(config, account_handler)
    provider._hs = SimpleNamespace()

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "42",
        "email": "user@test.com",
    }

    fake_requests = Mock()
    fake_requests.post = lambda *a, **k: mock_resp
    monkeypatch.setattr(provider_module, "requests", fake_requests)

    mxid, _ = await provider.check_auth(
        username="user@test.com",
        login_type="m.login.password",
        login_dict={"password": "123"},
    )

    assert mxid.startswith("@user:")
    account_handler.register.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_auth_requires_password(provider):
    account_handler.register = AsyncMock()
    with pytest.raises(AuthError) as err:
        await provider.check_auth(
            username="user@test.com",
            login_type="m.login.password",
            login_dict={},
        )

    assert err.value.code == 403
    assert "password" in str(err.value)
    account_handler.register.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_auth_rejects_non_email_username(provider):
    account_handler.register = AsyncMock()
    with pytest.raises(AuthError) as err:
        await provider.check_auth(
            username="invalid-user",
            login_type="m.login.password",
            login_dict={"password": "123"},
        )

    assert err.value.code == 400
    assert "Email" in str(err.value)
    account_handler.register.assert_not_awaited()
