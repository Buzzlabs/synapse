import pytest
from unittest.mock import MagicMock, AsyncMock

from room_service.service import RoomService


def _make_service():
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    # admin check passa
    api.is_user_admin = AsyncMock(return_value=True)
    # create_room devolve (room_id, _)
    api.create_room = AsyncMock(return_value=("!new:localhost", None))

    store = MagicMock()

    async def fake_run(desc, func, *args):
        if desc == "keyword_exists":
            return False
        # save_room_metadata e afins: no-op
        return None

    store.db_pool.runInteraction = AsyncMock(side_effect=fake_run)
    hs.get_datastores.return_value.main = store

    service = RoomService(
        api=api,
        admin_user_id="@admin:localhost",
        admin_token="token",
        homeserver="http://localhost:3000",
    )
    service.store = store
    # neutraliza efeitos colaterais que batem no Matrix real
    service._admin_join = AsyncMock()
    service._admin_send_state = AsyncMock()
    return service, api


def _requester(user_id="@creator:localhost"):
    r = MagicMock()
    r.user.to_string.return_value = user_id
    return r


@pytest.mark.asyncio
async def test_create_room_normal_nao_e_space():
    """
    Sem room_kind=space, o config nao deve marcar creation_content m.space.
    """
    service, api = _make_service()

    await service.create_room(
        requester=_requester(),
        data={"keyword": "k1", "name": "Sala", "room_kind": "group"},
    )

    config = api.create_room.await_args.kwargs["config"]
    assert "creation_content" not in config


@pytest.mark.asyncio
async def test_create_room_space_marca_creation_content():
    """
    Com room_kind=space, o config deve conter creation_content type m.space.
    """
    service, api = _make_service()

    await service.create_room(
        requester=_requester(),
        data={"keyword": "k2", "name": "Espaco", "room_kind": "space"},
    )

    config = api.create_room.await_args.kwargs["config"]
    assert config.get("creation_content", {}).get("type") == "m.space"


@pytest.mark.asyncio
async def test_create_room_default_e_group():
    """
    Sem room_kind no request, assume group (nao space).
    """
    service, api = _make_service()

    await service.create_room(
        requester=_requester(),
        data={"keyword": "k3", "name": "Sala"},
    )

    config = api.create_room.await_args.kwargs["config"]
    assert "creation_content" not in config