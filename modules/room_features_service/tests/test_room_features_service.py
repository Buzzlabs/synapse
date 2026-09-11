import pytest
from unittest.mock import MagicMock, AsyncMock

from synapse.api.errors import SynapseError
from modules.room_features_service.service import RoomFeaturesService
from modules.room_features_service import db

# testa
# 1. get retorna enabled=False quando a feature nao existe (nunca 404)
# 2. get retorna o valor gravado quando existe
# 3. set exige admin global
# 4. set faz upsert com os parametros certos
# 5. validacao de room_id / feature / enabled

# para testar: PYTHONPATH=. pytest -vv modules/room_features_service/tests/

ROOM_ID = "!room:localhost"
ADMIN = "@admin:localhost"
USER = "@user:localhost"


def _make_service(row=None, rows=None, is_admin=True):
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    api.is_user_admin = AsyncMock(return_value=is_admin)

    store = MagicMock()

    async def fake_run_interaction(desc, func, *args):
        if desc == "get_room_feature":
            return row
        if desc == "list_room_features":
            return rows if rows is not None else []
        if desc == "set_room_feature":
            return None
        raise AssertionError(f"runInteraction inesperado: {desc}")

    store.db_pool.runInteraction = AsyncMock(side_effect=fake_run_interaction)
    hs.get_datastores.return_value.main = store

    service = RoomFeaturesService(
        api=api,
        admin_user_id=ADMIN,
        admin_token="token",
        homeserver="http://localhost:8008",
    )
    service._store_mock = store
    return service

def _make_requester(user_id: str):
    requester = MagicMock()
    requester.user.to_string.return_value = user_id
    return requester

def _make_txn(fetchone=None, fetchall=None):
    txn = MagicMock()
    txn.fetchone.return_value = fetchone
    txn.fetchall.return_value = fetchall if fetchall is not None else []
    return txn


# ---------------- GET ----------------

@pytest.mark.asyncio
async def test_get_feature_ausente_retorna_false():
    """
    Feature sem linha na tabela deve retornar enabled=False, nao 404.
    """
    service = _make_service(row=None)

    result = await service.get_feature(room_id=ROOM_ID, feature="vods")

    assert result["enabled"] is False
    assert result["roomId"] == ROOM_ID
    assert result["feature"] == "vods"


@pytest.mark.asyncio
async def test_get_feature_ligada():
    """
    Feature ligada deve retornar enabled=True.
    """
    service = _make_service(row=(True,))

    result = await service.get_feature(room_id=ROOM_ID, feature="vods")

    assert result["enabled"] is True


@pytest.mark.asyncio
async def test_get_feature_desligada():
    """
    Feature com linha mas enabled=False deve retornar False.
    """
    service = _make_service(row=(False,))

    result = await service.get_feature(room_id=ROOM_ID, feature="vods")

    assert result["enabled"] is False


@pytest.mark.asyncio
async def test_get_feature_sem_room_id():
    """
    room_id vazio deve retornar 400.
    """
    service = _make_service()

    with pytest.raises(SynapseError) as err:
        await service.get_feature(room_id="", feature="vods")

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_get_feature_sem_feature():
    """
    feature vazia deve retornar 400.
    """
    service = _make_service()

    with pytest.raises(SynapseError) as err:
        await service.get_feature(room_id=ROOM_ID, feature="")

    assert err.value.code == 400


# ---------------- LIST ----------------

@pytest.mark.asyncio
async def test_list_features_mapeia_todas():
    """
    list deve devolver um dict feature -> bool.
    """
    service = _make_service(rows=[("vods", True), ("events", False)])

    result = await service.list_features(room_id=ROOM_ID)

    assert result["features"] == {"vods": True, "events": False}


@pytest.mark.asyncio
async def test_list_features_vazio():
    """
    Sala sem features deve devolver dict vazio.
    """
    service = _make_service(rows=[])

    result = await service.list_features(room_id=ROOM_ID)

    assert result["features"] == {}


# ---------------- SET (admin) ----------------

@pytest.mark.asyncio
async def test_set_feature_exige_admin():
    """
    Nao-admin deve receber 403 e nada deve ser gravado.
    """
    service = _make_service(is_admin=False)

    with pytest.raises(SynapseError) as err:
        await service.set_feature(
            requester=_make_requester(USER),
            room_id=ROOM_ID,
            feature="vods",
            enabled=True,
        )

    assert err.value.code == 403
    # nao deve ter chamado o set no banco
    calls = [c.args[0] for c in service._store_mock.db_pool.runInteraction.await_args_list]
    assert "set_room_feature" not in calls


@pytest.mark.asyncio
async def test_set_feature_admin_grava():
    """
    Admin deve conseguir ligar a feature.
    """
    service = _make_service(is_admin=True)

    result = await service.set_feature(
        requester=_make_requester(ADMIN),
        room_id=ROOM_ID,
        feature="vods",
        enabled=True,
    )

    assert result["enabled"] is True

    call = service._store_mock.db_pool.runInteraction.await_args
    # (desc, func, room_id, feature, enabled, now_ms)
    assert call.args[0] == "set_room_feature"
    assert call.args[2] == ROOM_ID
    assert call.args[3] == "vods"
    assert call.args[4] is True


@pytest.mark.asyncio
async def test_set_feature_enabled_nao_booleano():
    """
    enabled que nao e bool deve retornar 400 (antes de tocar no banco).
    """
    service = _make_service(is_admin=True)

    with pytest.raises(SynapseError) as err:
        await service.set_feature(
            requester=_make_requester(ADMIN),
            room_id=ROOM_ID,
            feature="vods",
            enabled="sim",
        )

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_set_feature_sem_room_id():
    """
    room_id vazio deve retornar 400.
    """
    service = _make_service(is_admin=True)

    with pytest.raises(SynapseError) as err:
        await service.set_feature(
            requester=_make_requester(ADMIN),
            room_id="",
            feature="vods",
            enabled=True,
        )

    assert err.value.code == 400


# ---------------- DB ----------------

def test_db_get_feature_query():
    """
    get_feature deve filtrar por room_id e feature.
    """
    txn = _make_txn(fetchone=(True,))

    db.get_feature(txn, room_id=ROOM_ID, feature="vods")

    sql = txn.execute.call_args.args[0]
    params = txn.execute.call_args.args[1]
    assert "WHERE room_id = ? AND feature = ?" in sql
    assert params == (ROOM_ID, "vods")


def test_db_set_feature_upsert():
    """
    set_feature deve usar upsert (ON CONFLICT).
    """
    txn = _make_txn()

    db.set_feature(txn, room_id=ROOM_ID, feature="vods", enabled=True, now_ms=123)

    sql = txn.execute.call_args.args[0]
    params = txn.execute.call_args.args[1]
    assert "ON CONFLICT" in sql
    assert params == (ROOM_ID, "vods", True, 123, 123)
