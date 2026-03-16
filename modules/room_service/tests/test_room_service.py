import pytest
from unittest.mock import Mock, AsyncMock
from types import SimpleNamespace

from synapse.api.errors import SynapseError

from room_service.module import RoomService


# ---------------- FIXTURES ----------------

@pytest.fixture
def fake_store():
    store = Mock()
    store.db_pool = Mock()
    store.db_pool.runInteraction = AsyncMock()
    store.get_users_in_room = AsyncMock(return_value=[])
    return store


@pytest.fixture
def fake_api():
    api = Mock()
    api.is_user_admin = AsyncMock(return_value=True)
    api.create_room = AsyncMock(return_value=("!room:id", None))
    api.get_state_events_in_room = AsyncMock(return_value=[])
    return api


@pytest.fixture
def fake_hs(fake_store):
    hs = Mock()
    hs.get_datastores.return_value = SimpleNamespace(main=fake_store)
    hs.get_room_member_handler.return_value = Mock()
    hs.get_reactor.return_value = Mock()
    return hs


@pytest.fixture
def service(fake_api, fake_hs):
    fake_api._hs = fake_hs
    svc = RoomService(
        api=fake_api,
        admin_user_id="@admin:test",
        admin_token="token",
        homeserver="http://localhost:3000",
    )
    svc.agent = Mock()
    svc._admin_join = AsyncMock()
    svc._admin_send_state = AsyncMock()
    svc._admin_get_room_members = AsyncMock(return_value=[])
    svc._admin_kick_user = AsyncMock()
    svc._leave_room = AsyncMock()
    return svc


@pytest.fixture
def requester():
    user = Mock()
    user.to_string.return_value = "@creator:test"
    return SimpleNamespace(user=user)


# ---------------- CREATE ROOM ----------------

@pytest.mark.asyncio
async def test_create_room_non_admin_rejected(service, requester):
    """
    Should reject room creation when requester is not a Synapse admin (403).
    """
    service.api.is_user_admin = AsyncMock(return_value=False)

    with pytest.raises(SynapseError) as err:
        await service.create_room(requester, {
            "name": "Room",
            "keyword": "abc",
        })

    assert err.value.code == 403


@pytest.mark.asyncio
async def test_create_room_requires_keyword(service, requester):
    """
    Should reject room creation when keyword is missing (400).
    """
    with pytest.raises(SynapseError) as err:
        await service.create_room(requester, {"name": "Room"})

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_create_room_keyword_conflict(service, requester):
    """
    Should reject room creation when keyword already exists (409).
    """
    service.store.db_pool.runInteraction = AsyncMock(return_value=True)

    with pytest.raises(SynapseError) as err:
        await service.create_room(requester, {
            "name": "Room",
            "keyword": "abc",
        })

    assert err.value.code == 409


@pytest.mark.asyncio
async def test_create_room_success(service, requester):
    """
    Should successfully create a room when all business rules are valid.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        False,
        None,
    ])

    room_id = await service.create_room(requester, {
        "name": "Room",
        "keyword": "abc",
        "visible": True,
        "access_type": "private",
        "price": 100,
    })

    assert room_id == "!room:id"
    service.api.create_room.assert_awaited_once()
    service._admin_join.assert_awaited_once()


# ---------------- CHANGE VISIBILITY ----------------

@pytest.mark.asyncio
async def test_change_visibility_success_public(service, requester):
    """
    Should force price to 0 when making a public room visible.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        "public",
        None,
    ])

    result = await service.change_visibility(
        requester=requester,
        room_id="!r",
        visible=True,
        price=999,
    )

    assert result["visible"] is True
    assert result["price"] == 0


@pytest.mark.asyncio
async def test_change_visibility_success_private(service, requester):
    """
    Should allow setting price when room is private and visible.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        "private",
        None,
    ])

    result = await service.change_visibility(
        requester=requester,
        room_id="!r",
        visible=True,
        price=100,
    )

    assert result["price"] == 100


@pytest.mark.asyncio
async def test_change_visibility_room_not_found(service, requester):
    """
    Should return 404 when changing visibility of a non-existing room.
    """
    service.store.db_pool.runInteraction = AsyncMock(return_value=None)

    with pytest.raises(SynapseError) as err:
        await service.change_visibility(
            requester=requester,
            room_id="!r",
            visible=True,
            price=10,
        )

    assert err.value.code == 404


@pytest.mark.asyncio
async def test_change_visibility_private_requires_price(service, requester):
    """
    Should reject private visible rooms without a valid price (400).
    """
    service.store.db_pool.runInteraction = AsyncMock(return_value="private")

    with pytest.raises(SynapseError):
        await service.change_visibility(
            requester=requester,
            room_id="!r",
            visible=True,
            price=0,
        )


# ---------------- CHANGE PRICE ----------------

@pytest.mark.asyncio
async def test_change_price_non_visible_rejects(service, requester):
    """
    Should reject price update if room is not visible.
    """
    service.store.db_pool.runInteraction = AsyncMock(
        return_value=(0, "private", 0)
    )

    with pytest.raises(SynapseError):
        await service.change_price(
            requester=requester,
            room_id="!r",
            price=100,
        )


@pytest.mark.asyncio
async def test_change_price_public_rejects(service, requester):
    """
    Should reject setting price on a public room.
    """
    service.store.db_pool.runInteraction = AsyncMock(
        return_value=(1, "public", 0)
    )

    with pytest.raises(SynapseError):
        await service.change_price(
            requester=requester,
            room_id="!r",
            price=50,
        )


@pytest.mark.asyncio
async def test_change_price_private_visible_success(service, requester):
    """
    Should successfully update price when room is private and visible.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        (1, "private", 10),
        None,
    ])

    result = await service.change_price(
        requester=requester,
        room_id="!r",
        price=200,
    )

    assert result["price"] == 200


@pytest.mark.asyncio
async def test_change_price_private_visible_invalid_price(service, requester):
    """
    Should reject invalid price for private visible room.
    """
    service.store.db_pool.runInteraction = AsyncMock(
        return_value=(1, "private", 10)
    )

    with pytest.raises(SynapseError):
        await service.change_price(
            requester=requester,
            room_id="!r",
            price=0,
        )


# ---------------- CHANGE ACCESS TYPE ----------------

@pytest.mark.asyncio
async def test_change_access_type_invalid(service, requester):
    """
    Should reject invalid access type values.
    """
    with pytest.raises(SynapseError):
        await service.change_access_type(
            requester=requester,
            room_id="!r",
            access_type="invalid",
        )


@pytest.mark.asyncio
async def test_change_access_type_not_found(service, requester):
    """
    Should return 404 when changing access type of a non-existing room.
    """
    service.store.db_pool.runInteraction = AsyncMock(return_value=None)

    with pytest.raises(SynapseError):
        await service.change_access_type(
            requester=requester,
            room_id="!r",
            access_type="public",
        )


@pytest.mark.asyncio
async def test_change_access_type_public_to_private_sets_default_price(service, requester):
    """
    Should apply default price (1000) when converting public visible room to private without price.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        (1, "public", 0),
        None,
    ])

    result = await service.change_access_type(
        requester=requester,
        room_id="!r",
        access_type="private",
    )

    assert result["access_type"] == "private"
    assert result["price"] == 1000


@pytest.mark.asyncio
async def test_change_access_type_private_to_public_forces_zero(service, requester):
    """
    Should force price to 0 when converting private room to public.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        (1, "private", 50),
        None,
    ])

    result = await service.change_access_type(
        requester=requester,
        room_id="!r",
        access_type="public",
    )

    assert result["access_type"] == "public"
    assert result["price"] == 0


# ---------------- GET VISIBILITY ----------------

@pytest.mark.asyncio
async def test_get_room_visibility_not_found(service):
    """
    Should return 404 when fetching visibility of a non-existing room.
    """
    service.store.db_pool.runInteraction = AsyncMock(return_value=None)

    with pytest.raises(SynapseError):
        await service.get_room_visibility(room_id="!r")


@pytest.mark.asyncio
async def test_get_room_visibility_success(service):
    """
    Should return visibility metadata when room exists.
    """
    service.store.db_pool.runInteraction = AsyncMock(
        return_value=(1, 50, "private")
    )

    result = await service.get_room_visibility(room_id="!r")

    assert result["visible"] is True
    assert result["price"] == 50


# ---------------- DELETE ROOM ----------------

@pytest.mark.asyncio
async def test_delete_room_not_found(service, requester):
    """
    Should return 404 when attempting to delete a non-existing room.
    """
    service.store.db_pool.runInteraction = AsyncMock(return_value=None)

    with pytest.raises(SynapseError):
        await service.delete_room(
            requester=requester,
            room_id="!r",
        )


@pytest.mark.asyncio
async def test_delete_room_success(service, requester):
    """
    Should delete room and kick members when room exists.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        (1, 0, "private"),
        None,
    ])

    service._admin_get_room_members = AsyncMock(return_value=["@u:test"])

    result = await service.delete_room(
        requester=requester,
        room_id="!r",
    )

    assert result["deleted"] is True
    service._admin_kick_user.assert_awaited()


@pytest.mark.asyncio
async def test_delete_room_kicks_all_members_except_requester(service, requester):
    """
    Should kick all joined members except the requester during room deletion.
    """
    service.store.db_pool.runInteraction = AsyncMock(side_effect=[
        (1, 0, "private"),
        None,
    ])

    service._admin_get_room_members = AsyncMock(
        return_value=["@creator:test", "@user1:test", "@user2:test"]
    )

    await service.delete_room(
        requester=requester,
        room_id="!r",
    )

    assert service._admin_kick_user.await_count == 2
