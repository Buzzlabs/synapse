import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.bundle_service.service import BundleService


@pytest.mark.asyncio
async def test_list_bundles_success():
    """
    Deve retornar bundles publicados corretamente formatados.
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
                "bundle_name": "Bundle Teste",
                "price": 10,
                "rooms": ["!room1:localhost"],
                "status": "published",
                "created_by": "@admin:localhost",
            }
        ],
        [
            ("!room1:localhost", "buzz")
        ]
    ])

    api.is_user_admin = AsyncMock(return_value=False)

    api.get_state_events_in_room = AsyncMock(return_value=[
        MagicMock(content={"name": "Sala Teste"})
    ])

    result = await service.list_bundles("@user:localhost")

    assert len(result) == 1

    bundle = result[0]

    assert bundle["bundle_id"] == "bundle1"
    assert bundle["bundle_name"] == "Bundle Teste"
    assert bundle["price"] == 10
    assert bundle["rooms"] == ["Sala Teste"]
    assert bundle["keywords"] == ["buzz"]
    assert bundle["status"] == "published"

    api.is_user_admin.assert_called_once()


@pytest.mark.asyncio
async def test_list_bundles_hides_draft():
    """
    Usuário comum não deve ver bundles draft de outros usuários.
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
            "bundle_name": "Bundle Draft",
            "price": 10,
            "rooms": [],
            "status": "draft",
            "created_by": "@other:localhost",
        }
    ])

    api.is_user_admin = AsyncMock(return_value=False)

    result = await service.list_bundles("@user:localhost")

    assert result == []


@pytest.mark.asyncio
async def test_list_bundles_admin_can_see_draft():
    """
    Admin deve conseguir ver bundles draft.
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
                "bundle_name": "Bundle Draft",
                "price": 10,
                "rooms": ["!room1:localhost"],
                "status": "draft",
                "created_by": "@other:localhost",
            }
        ],
        [
            ("!room1:localhost", "buzz")
        ]
    ])

    api.is_user_admin = AsyncMock(return_value=True)

    api.get_state_events_in_room = AsyncMock(return_value=[
        MagicMock(content={"name": "Sala Teste"})
    ])

    result = await service.list_bundles("@admin:localhost")

    assert len(result) == 1