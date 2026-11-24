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
async def test_create_bundle_success(service):
    """
    Deve criar o bundle com sucesso e retornar o bundle_id.
    """

    service.store.db_pool.runInteraction = AsyncMock(
        side_effect=[
            [("!room1:test", "kw1"), ("!room2:test", "kw2")],
            "bundle-123",
        ]
    )

    bundle_id = await service.create_bundle(
        bundle_name="Music Bundle",
        price=1000,
        created_by="@admin:test",
        rooms=["!room1:test", "!room2:test"],
    )

    assert bundle_id == "bundle-123"

    assert service.store.db_pool.runInteraction.await_count == 2


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


@pytest.mark.asyncio
async def test_create_bundle_unknown_room_returns_400(service):
    """
    Sala que nao existe em room_business deve devolver 400 e nao inserir nada.
    """

    service.store.db_pool.runInteraction = AsyncMock(
        return_value=[("!room1:test", "kw1")]
    )

    with pytest.raises(SynapseError) as exc:
        await service.create_bundle(
            bundle_name="Music Bundle",
            price=1000,
            created_by="@admin:test",
            rooms=["!room1:test", "!typo:test"],
        )

    assert exc.value.code == 400
    assert "!typo:test" in exc.value.msg

    names = [c.args[0] for c in service.store.db_pool.runInteraction.await_args_list]
    assert "create_bundle" not in names
