import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError
from modules.bundle_service.service import BundleService


@pytest.mark.asyncio
async def test_update_bundle_success():
    """
    Deve atualizar o bundle com sucesso quando o usuário é dono ou admin.
    """

    api = MagicMock()

    store = MagicMock()
    db_pool = MagicMock()

    api._hs.get_datastores.return_value.main = store
    store.db_pool = db_pool

    service = BundleService(api)

    db_pool.runInteraction = AsyncMock(side_effect=[
        [
            {
                "bundle_id": "bundle1",
                "bundle_name": "Old Bundle",
                "price": 10,
                "created_by": "@user:localhost",
            }
        ],
        None
    ])

    service._is_admin = AsyncMock(return_value=False)

    result = await service.update_bundle(
        "@user:localhost",
        "bundle1",
        "New Bundle",
        20,
        ["!room1:localhost", "!room1:localhost"],
    )

    assert result["bundle_id"] == "bundle1"
    assert db_pool.runInteraction.await_count == 2


@pytest.mark.asyncio
async def test_update_bundle_not_found():
    """
    Deve retornar erro se o bundle não existir.
    """

    api = MagicMock()

    store = MagicMock()
    db_pool = MagicMock()

    api._hs.get_datastores.return_value.main = store
    store.db_pool = db_pool

    service = BundleService(api)

    db_pool.runInteraction = AsyncMock(return_value=[])

    service._is_admin = AsyncMock(return_value=False)

    with pytest.raises(SynapseError) as err:
        await service.update_bundle(
            "@user:localhost",
            "bundle1",
            "New Bundle",
            20,
            [],
        )

    assert err.value.code == 404


@pytest.mark.asyncio
async def test_update_bundle_permission_denied():
    """
    Usuário que não é dono nem admin não pode atualizar o bundle.
    """

    api = MagicMock()

    store = MagicMock()
    db_pool = MagicMock()

    api._hs.get_datastores.return_value.main = store
    store.db_pool = db_pool

    service = BundleService(api)

    db_pool.runInteraction = AsyncMock(return_value=[
        {
            "bundle_id": "bundle1",
            "bundle_name": "Bundle",
            "price": 10,
            "created_by": "@other:localhost",
        }
    ])

    service._is_admin = AsyncMock(return_value=False)

    with pytest.raises(SynapseError) as err:
        await service.update_bundle(
            "@user:localhost",
            "bundle1",
            "New Bundle",
            20,
            [],
        )

    assert err.value.code == 403


@pytest.mark.asyncio
async def test_update_bundle_missing_bundle_id():
    """
    Deve retornar erro se bundle_id não for informado.
    """

    api = MagicMock()
    store = MagicMock()

    api._hs.get_datastores.return_value.main = store

    service = BundleService(api)

    with pytest.raises(SynapseError) as err:
        await service.update_bundle(
            "@user:localhost",
            None,
            "Bundle",
            10,
            [],
        )

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_update_bundle_missing_name():
    """
    Deve retornar erro se bundle_name não for informado.
    """

    api = MagicMock()
    store = MagicMock()

    api._hs.get_datastores.return_value.main = store

    service = BundleService(api)

    with pytest.raises(SynapseError) as err:
        await service.update_bundle(
            "@user:localhost",
            "bundle1",
            None,
            10,
            [],
        )

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_update_bundle_missing_price():
    """
    Deve retornar erro se price não for informado.
    """

    api = MagicMock()
    store = MagicMock()

    api._hs.get_datastores.return_value.main = store

    service = BundleService(api)

    with pytest.raises(SynapseError) as err:
        await service.update_bundle(
            "@user:localhost",
            "bundle1",
            "Bundle",
            None,
            [],
        )

    assert err.value.code == 400