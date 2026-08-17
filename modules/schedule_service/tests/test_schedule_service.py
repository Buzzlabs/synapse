import pytest
from unittest.mock import MagicMock, AsyncMock

from synapse.api.errors import SynapseError
from modules.schedule_service.service import ScheduleService
from modules.schedule_service import db

# testa
# 1. get_calendar de sala sem config retorna None
# 2. set_calendar exige admin
# 3. list_events de sala sem calendar retorna vazio (nao erro)
# 4. list_events chama o Google e filtra cancelados/sem start
# 5. validacao de room_id / calendar_id / limit

# para testar: PYTHONPATH=. pytest -vv modules/schedule_service/tests/

ROOM_ID = "!room:localhost"
ADMIN = "@admin:localhost"
USER = "@user:localhost"


def _make_service(calendar_row=None, google_response=None, is_admin=True):
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs
    api.is_user_admin = AsyncMock(return_value=is_admin)

    store = MagicMock()

    async def fake_run(desc, func, *args):
        if desc == "get_room_calendar":
            return calendar_row
        if desc == "set_room_calendar":
            return None
        raise AssertionError(f"runInteraction inesperado: {desc}")

    store.db_pool.runInteraction = AsyncMock(side_effect=fake_run)
    hs.get_datastores.return_value.main = store

    http = MagicMock()
    http.get_json = AsyncMock(return_value=google_response or {"items": []})
    hs.get_proxied_http_client.return_value = http

    service = ScheduleService(api=api, google_api_key="KEY")
    service._store_mock = store
    service._http_mock = http
    return service


def _make_txn(fetchone=None):
    txn = MagicMock()
    txn.fetchone.return_value = fetchone
    return txn


def _requester(user_id):
    r = MagicMock()
    r.user.to_string.return_value = user_id
    return r


# ---------------- GET CALENDAR ----------------

@pytest.mark.asyncio
async def test_get_calendar_sem_config():
    service = _make_service(calendar_row=None)
    result = await service.get_calendar(room_id=ROOM_ID)
    assert result["calendarId"] is None


@pytest.mark.asyncio
async def test_get_calendar_configurado():
    service = _make_service(calendar_row=("cal123@group.calendar.google.com",))
    result = await service.get_calendar(room_id=ROOM_ID)
    assert result["calendarId"] == "cal123@group.calendar.google.com"


# ---------------- SET CALENDAR ----------------

@pytest.mark.asyncio
async def test_set_calendar_exige_admin():
    service = _make_service(is_admin=False)
    with pytest.raises(SynapseError) as err:
        await service.set_calendar(
            requester=_requester(USER), room_id=ROOM_ID, calendar_id="cal"
        )
    assert err.value.code == 403


@pytest.mark.asyncio
async def test_set_calendar_admin_grava():
    service = _make_service(is_admin=True)
    result = await service.set_calendar(
        requester=_requester(ADMIN), room_id=ROOM_ID, calendar_id="cal123"
    )
    assert result["calendarId"] == "cal123"
    call = service._store_mock.db_pool.runInteraction.await_args
    assert call.args[0] == "set_room_calendar"
    assert call.args[2] == ROOM_ID
    assert call.args[3] == "cal123"


@pytest.mark.asyncio
async def test_set_calendar_sem_id():
    service = _make_service(is_admin=True)
    with pytest.raises(SynapseError) as err:
        await service.set_calendar(
            requester=_requester(ADMIN), room_id=ROOM_ID, calendar_id=""
        )
    assert err.value.code == 400


# ---------------- LIST EVENTS ----------------

@pytest.mark.asyncio
async def test_list_events_sem_calendar():
    """Sala sem calendar configurado retorna lista vazia, nao erro."""
    service = _make_service(calendar_row=None)
    result = await service.list_events(room_id=ROOM_ID)
    assert result["items"] == []
    # nao deve ter chamado o Google
    service._http_mock.get_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_events_chama_google_e_filtra():
    google = {
        "items": [
            {"id": "1", "status": "confirmed", "summary": "Live", "start": {"dateTime": "2026-08-20T20:00:00Z"}},
            {"id": "2", "status": "cancelled", "summary": "Cancelado", "start": {"dateTime": "2026-08-21T20:00:00Z"}},
            {"id": "3", "status": "confirmed", "summary": "Sem start"},  # sem start -> filtrado
        ]
    }
    service = _make_service(calendar_row=("cal123",), google_response=google)

    result = await service.list_events(room_id=ROOM_ID)

    # so o evento 1 sobra (2 cancelado, 3 sem start)
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == "1"
    service._http_mock.get_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_events_limit_invalido():
    service = _make_service(calendar_row=("cal123",))
    with pytest.raises(SynapseError) as err:
        await service.list_events(room_id=ROOM_ID, limit=999)
    assert err.value.code == 400


@pytest.mark.asyncio
async def test_list_events_google_falha():
    service = _make_service(calendar_row=("cal123",))
    service._http_mock.get_json = AsyncMock(side_effect=Exception("timeout"))
    with pytest.raises(SynapseError) as err:
        await service.list_events(room_id=ROOM_ID)
    assert err.value.code == 502


# ---------------- DB ----------------

def test_db_set_calendar_upsert():
    txn = _make_txn()
    db.set_calendar(txn, room_id=ROOM_ID, calendar_id="cal", now_ms=123)
    sql = txn.execute.call_args.args[0]
    params = txn.execute.call_args.args[1]
    assert "ON CONFLICT" in sql
    assert params == (ROOM_ID, "cal", 123, 123)


def test_db_get_calendar_query():
    txn = _make_txn(fetchone=("cal",))
    db.get_calendar(txn, room_id=ROOM_ID)
    params = txn.execute.call_args.args[1]
    assert params == (ROOM_ID,)