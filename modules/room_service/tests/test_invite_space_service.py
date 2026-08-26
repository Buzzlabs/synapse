import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError


# ---------------------------------------------------------------------------
# Reproduz os dois métodos que serão adicionados ao RoomService, isolados numa
# classe mínima só com o necessário, para testar a lógica sem subir o Synapse.
# ---------------------------------------------------------------------------
class RoomServiceSpaceMixin:
    def __init__(self, api):
        self.api = api

    async def _get_space_children(self, space_id):
        try:
            state_events = await self.api.get_state_events_in_room(
                space_id,
                [("m.space.child", None)],
            )
        except Exception:
            return []

        children = []
        for ev in state_events:
            child_id = ev.state_key
            via = ev.content.get("via")
            if child_id and via:
                children.append(child_id)
        return children

    async def invite_space(self, user_id, space_id):
        room_ids = await self._get_space_children(space_id)
        if not room_ids:
            raise SynapseError(404, "Space not found or empty")

        joined_rooms = []
        for room_id in room_ids:
            try:
                result = await self._admin_join(room_id, user_id)
                if result in ("joined", "already_joined"):
                    joined_rooms.append(room_id)
            except Exception:
                pass
        return joined_rooms


def _child_event(room_id, via=("localhost",)):
    ev = MagicMock()
    ev.state_key = room_id
    ev.content = {"via": list(via)} if via is not None else {}
    return ev


@pytest.mark.asyncio
async def test_get_space_children_returns_active_children():
    """Filhos com 'via' são retornados."""
    api = MagicMock()
    api.get_state_events_in_room = AsyncMock(return_value=[
        _child_event("!room1:localhost"),
        _child_event("!room2:localhost"),
    ])

    svc = RoomServiceSpaceMixin(api)
    children = await svc._get_space_children("!space:localhost")

    assert children == ["!room1:localhost", "!room2:localhost"]


@pytest.mark.asyncio
async def test_get_space_children_ignores_removed_children():
    """Filho com content vazio (sem 'via') = removido, deve ser ignorado."""
    api = MagicMock()
    api.get_state_events_in_room = AsyncMock(return_value=[
        _child_event("!active:localhost"),
        _child_event("!removed:localhost", via=None),  # removido
    ])

    svc = RoomServiceSpaceMixin(api)
    children = await svc._get_space_children("!space:localhost")

    assert children == ["!active:localhost"]


@pytest.mark.asyncio
async def test_get_space_children_empty_on_error():
    """Se a leitura de estado falhar, retorna lista vazia (não explode)."""
    api = MagicMock()
    api.get_state_events_in_room = AsyncMock(side_effect=Exception("boom"))

    svc = RoomServiceSpaceMixin(api)
    children = await svc._get_space_children("!space:localhost")

    assert children == []


@pytest.mark.asyncio
async def test_invite_space_joins_all_children():
    """invite_space faz admin join em cada sala filha e retorna as que entrou."""
    api = MagicMock()
    api.get_state_events_in_room = AsyncMock(return_value=[
        _child_event("!room1:localhost"),
        _child_event("!room2:localhost"),
    ])

    svc = RoomServiceSpaceMixin(api)
    svc._admin_join = AsyncMock(return_value="joined")

    joined = await svc.invite_space("@bob:localhost", "!space:localhost")

    assert joined == ["!room1:localhost", "!room2:localhost"]
    assert svc._admin_join.await_count == 2
    svc._admin_join.assert_any_await("!room1:localhost", "@bob:localhost")
    svc._admin_join.assert_any_await("!room2:localhost", "@bob:localhost")


@pytest.mark.asyncio
async def test_invite_space_empty_raises_404():
    """Space sem filhos ativos deve resultar em 404."""
    api = MagicMock()
    api.get_state_events_in_room = AsyncMock(return_value=[])

    svc = RoomServiceSpaceMixin(api)
    svc._admin_join = AsyncMock()

    with pytest.raises(SynapseError) as exc:
        await svc.invite_space("@bob:localhost", "!empty:localhost")

    assert exc.value.code == 404
    svc._admin_join.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_space_skips_failed_joins():
    """Se um join falha, os outros continuam; só os que entraram são retornados."""
    api = MagicMock()
    api.get_state_events_in_room = AsyncMock(return_value=[
        _child_event("!ok:localhost"),
        _child_event("!fail:localhost"),
    ])

    svc = RoomServiceSpaceMixin(api)

    async def join_side_effect(room_id, user_id):
        if room_id == "!fail:localhost":
            raise Exception("join failed")
        return "joined"

    svc._admin_join = AsyncMock(side_effect=join_side_effect)

    joined = await svc.invite_space("@bob:localhost", "!space:localhost")

    assert joined == ["!ok:localhost"]