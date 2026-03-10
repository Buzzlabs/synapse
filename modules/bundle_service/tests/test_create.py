import pytest
from unittest.mock import Mock, AsyncMock
from types import SimpleNamespace

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
async def test_create_bundle_success(service):
    """
    Deve criar o bundle com sucesso e retornar o bundle_id.
    """

    service.store.db_pool.runInteraction = AsyncMock(
        return_value="bundle-123"
    )

    bundle_id = await service.create_bundle(
        bundle_name="Music Bundle",
        price=1000,
        created_by="@admin:test",
        rooms=["!room1:test", "!room2:test"],
    )

    assert bundle_id == "bundle-123"

    service.store.db_pool.runInteraction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_bundle_no_rooms(service):
    """
    Deve criar o bundle mesmo quando nenhuma room for fornecida.
    """

    service.store.db_pool.runInteraction = AsyncMock(
        return_value="bundle-456"
    )

    bundle_id = await service.create_bundle(
        bundle_name="Empty Bundle",
        price=500,
        created_by="@admin:test",
        rooms=[],
    )

    assert bundle_id == "bundle-456"


@pytest.mark.asyncio
async def test_create_bundle_db_error(service):
    """
    Deve propagar erros do banco de dados durante a criação do bundle.
    """

    service.store.db_pool.runInteraction = AsyncMock(
        side_effect=Exception("DB failure")
    )

    with pytest.raises(Exception):
        await service.create_bundle(
            bundle_name="Music Bundle",
            price=1000,
            created_by="@admin:test",
            rooms=["!room1:test"],
        )