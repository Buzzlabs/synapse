import pytest
from unittest.mock import Mock, AsyncMock
from types import SimpleNamespace

from synapse.api.errors import SynapseError
from modules.bundle_service.service import BundleService


@pytest.fixture
def fake_store():
    store = Mock()
    store.db_pool = Mock()
    store.db_pool.runInteraction = AsyncMock()
    return store


@pytest.fixture
def fake_api(fake_store):
    api = Mock()

    hs = Mock()
    hs.get_datastores.return_value = SimpleNamespace(main=fake_store)

    api._hs = hs
    return api


@pytest.fixture
def service(fake_api):
    return BundleService(api=fake_api)


@pytest.mark.asyncio
async def test_publish_bundle_success(service):
    """
    Deve publicar o bundle com sucesso quando o usuário é admin e o bundle existe.
    """

    service._is_admin = AsyncMock(return_value=True)

    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        True,   # bundle_exists
        None,   # publish_bundle
    ])

    result = await service.publish_bundle(
        bundle_id="bundle-123",
        user_id="@admin:test",
    )

    assert result["status"] == "published"


@pytest.mark.asyncio
async def test_publish_bundle_non_admin(service):
    """
    Deve rejeitar publicação quando o usuário não é admin.
    """

    service._is_admin = AsyncMock(return_value=False)

    with pytest.raises(SynapseError) as err:
        await service.publish_bundle(
            bundle_id="bundle-123",
            user_id="@user:test",
        )

    assert err.value.code == 403


@pytest.mark.asyncio
async def test_publish_bundle_not_found(service):
    """
    Deve retornar erro quando o bundle não existe.
    """

    service._is_admin = AsyncMock(return_value=True)

    service.store.db_pool.runInteraction = AsyncMock(
        return_value=False
    )

    with pytest.raises(SynapseError) as err:
        await service.publish_bundle(
            bundle_id="bundle-123",
            user_id="@admin:test",
        )

    assert err.value.code == 404