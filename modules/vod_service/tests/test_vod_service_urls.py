import pytest
from unittest.mock import MagicMock, AsyncMock

from synapse.api.errors import SynapseError
from modules.vod_service.service import VodService
from modules.vod_service import db

# testa
# 1. formato da URL nativa do Oracle Object Storage
# 2. porte do @computed() latestThumbnail do model AdonisJS
# 3. validacao de page/limit e calculo da paginacao
# 4. serializacao das linhas do banco nos campos que o front espera
# 5. vod inexistente retorna 404 explicito
# 6. SQL filtra so gravacoes encerradas (ended_at IS NOT NULL)

# para testar: PYTHONPATH=. pytest -vv modules/vod_service/tests/test_vod_service_urls.py


ROOM_ID = "!room:localhost"


# ---------------- HELPERS ----------------

def _make_service(base_url="https://objectstorage.sa-saopaulo-1.oraclecloud.com"):
    api = MagicMock()
    return VodService(
        api=api,
        object_storage_base_url=base_url,
        namespace="grmsqxilk3cb",
        bucket="vod-teste",
    )


def _make_service_with_db(rows=None, total=0):
    """Service com o db_pool mockado, para testar list_vods."""
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()

    async def fake_run_interaction(desc, func, *args):
        if desc == "get_vods":
            return rows if rows is not None else []
        if desc == "count_vods":
            return total
        raise AssertionError(f"runInteraction inesperado: {desc}")

    store.db_pool.runInteraction = AsyncMock(side_effect=fake_run_interaction)
    hs.get_datastores.return_value.main = store

    service = VodService(
        api=api,
        object_storage_base_url="https://objectstorage.sa-saopaulo-1.oraclecloud.com",
        namespace="grmsqxilk3cb",
        bucket="vod-teste",
    )
    service._store_mock = store
    return service


def _make_service_with_row(row=None):
    """Service com o db_pool mockado, para testar get_vod."""
    api = MagicMock()
    hs = MagicMock()
    api._hs = hs

    store = MagicMock()
    store.db_pool.runInteraction = AsyncMock(return_value=row)
    hs.get_datastores.return_value.main = store

    service = VodService(
        api=api,
        object_storage_base_url="https://objectstorage.sa-saopaulo-1.oraclecloud.com",
        namespace="grmsqxilk3cb",
        bucket="vod-teste",
    )
    service._store_mock = store
    return service


def _row(row_id=1, recording_path="abc123", started_at=0, ended_at=600_000):
    return (
        row_id,
        f"teste-{row_id}",
        ROOM_ID,
        "VOD de teste",
        None,
        recording_path,
        25900,
        started_at,
        ended_at,
    )


def _make_txn(fetchall=None, fetchone=None):
    txn = MagicMock()
    txn.fetchall.return_value = fetchall if fetchall is not None else []
    txn.fetchone.return_value = fetchone
    return txn


# ---------------- URL: PLAYLIST ----------------

def test_master_playlist_url():
    """
    Deve montar a URL nativa do Oracle Object Storage.
    """
    service = _make_service()
    url = service.master_playlist_url("abc123")

    assert url == (
        "https://objectstorage.sa-saopaulo-1.oraclecloud.com"
        "/n/grmsqxilk3cb/b/vod-teste/o/abc123/media/hls/master.m3u8"
    )


def test_base_url_com_barra_no_fim_nao_duplica():
    """
    base_url configurada com barra no fim nao deve gerar '//' na URL.
    """
    service = _make_service(
        base_url="https://objectstorage.sa-saopaulo-1.oraclecloud.com/"
    )
    url = service.master_playlist_url("abc123")

    assert "//n/" not in url
    assert url.startswith("https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/")


def test_recording_path_aninhado():
    """
    recording_path com barras (formato do IVS) deve ser preservado.
    """
    service = _make_service()
    url = service.master_playlist_url("canal/2026/07/abc123")

    assert url.endswith("/o/canal/2026/07/abc123/media/hls/master.m3u8")


# ---------------- URL: THUMBNAILS ----------------

def test_thumbnail_base_url():
    """
    Deve apontar para o latest_thumbnail do IVS.
    """
    service = _make_service()
    url = service.thumbnail_base_url("abc123")

    assert url.endswith("/o/abc123/media/latest_thumbnail")


def test_thumbnail_url_numerada():
    """
    Deve montar a URL de um thumbnail especifico.
    """
    service = _make_service()
    url = service.thumbnail_url("abc123", 12)

    assert url.endswith("/media/thumbnails/thumb12.jpg")


def test_latest_thumbnail_sem_datas():
    """
    Sem started_at/ended_at deve cair no thumb0.
    """
    service = _make_service()
    url = service.latest_thumbnail("abc123", None, None)

    assert url.endswith("/media/thumbnails/thumb0.jpg")


def test_latest_thumbnail_sem_ended_at():
    """
    Stream ainda ao vivo (sem ended_at) deve cair no thumb0.
    """
    service = _make_service()
    url = service.latest_thumbnail("abc123", 0, None)

    assert url.endswith("/media/thumbnails/thumb0.jpg")


def test_latest_thumbnail_meio_da_gravacao():
    """
    Gravacao de 10 min -> minuto do meio = 5 -> thumb20 (4 thumbs por minuto).
    """
    service = _make_service()

    started_at = 0
    ended_at = 10 * 60 * 1000  # 10 minutos em ms

    url = service.latest_thumbnail("abc123", started_at, ended_at)

    assert url.endswith("/media/thumbnails/thumb20.jpg")


def test_latest_thumbnail_gravacao_curta():
    """
    Gravacao de menos de 2 min -> minuto do meio = 0 -> thumb0.
    """
    service = _make_service()

    url = service.latest_thumbnail("abc123", 0, 30_000)

    assert url.endswith("/media/thumbnails/thumb0.jpg")


def test_latest_thumbnail_datas_invertidas():
    """
    ended_at antes de started_at nao deve gerar thumb negativo.
    """
    service = _make_service()

    url = service.latest_thumbnail("abc123", 600_000, 0)

    assert url.endswith("/media/thumbnails/thumb0.jpg")


def test_latest_thumbnail_gravacao_longa():
    """
    Gravacao de 2h -> minuto do meio = 60 -> thumb240.
    """
    service = _make_service()

    started_at = 0
    ended_at = 120 * 60 * 1000  # 2 horas em ms

    url = service.latest_thumbnail("abc123", started_at, ended_at)

    assert url.endswith("/media/thumbnails/thumb240.jpg")


# ---------------- LIST VODS: VALIDACAO ----------------

@pytest.mark.asyncio
async def test_list_vods_rejeita_room_id_vazio():
    """
    room_id vazio deve retornar 400.
    """
    service = _make_service_with_db()

    with pytest.raises(SynapseError) as err:
        await service.list_vods(room_id="", page=1, limit=10)

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_list_vods_rejeita_page_zero():
    """
    Deve retornar 400 quando page < 1.
    """
    service = _make_service_with_db()

    with pytest.raises(SynapseError) as err:
        await service.list_vods(room_id=ROOM_ID, page=0, limit=10)

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_list_vods_rejeita_limit_zero():
    """
    Deve retornar 400 quando limit < 1.
    """
    service = _make_service_with_db()

    with pytest.raises(SynapseError) as err:
        await service.list_vods(room_id=ROOM_ID, page=1, limit=0)

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_list_vods_rejeita_limit_acima_do_maximo():
    """
    Deve retornar 400 quando limit > 100, evitando dump da tabela inteira.
    """
    service = _make_service_with_db()

    with pytest.raises(SynapseError) as err:
        await service.list_vods(room_id=ROOM_ID, page=1, limit=101)

    assert err.value.code == 400


@pytest.mark.asyncio
async def test_list_vods_aceita_limit_no_limite():
    """
    Deve aceitar limit = 100 (fronteira valida).
    """
    service = _make_service_with_db(rows=[], total=0)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=100)

    assert result["meta"]["perPage"] == 100


# ---------------- LIST VODS: PAGINACAO ----------------

@pytest.mark.asyncio
async def test_list_vods_calcula_offset_da_primeira_pagina():
    """
    Pagina 1 deve consultar com offset 0.
    """
    service = _make_service_with_db(rows=[], total=0)

    await service.list_vods(room_id=ROOM_ID, page=1, limit=10)

    call = service._store_mock.db_pool.runInteraction.await_args_list[0]
    # (desc, func, room_id, limit, offset)
    assert call.args[2] == ROOM_ID
    assert call.args[3] == 10
    assert call.args[4] == 0


@pytest.mark.asyncio
async def test_list_vods_calcula_offset_da_terceira_pagina():
    """
    Pagina 3 com limit 10 deve consultar com offset 20.
    """
    service = _make_service_with_db(rows=[], total=0)

    await service.list_vods(room_id=ROOM_ID, page=3, limit=10)

    call = service._store_mock.db_pool.runInteraction.await_args_list[0]
    assert call.args[4] == 20


@pytest.mark.asyncio
async def test_list_vods_calcula_last_page_com_resto():
    """
    25 vods com limit 10 devem resultar em 3 paginas (arredonda pra cima).
    """
    service = _make_service_with_db(rows=[], total=25)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)

    assert result["meta"]["total"] == 25
    assert result["meta"]["lastPage"] == 3


@pytest.mark.asyncio
async def test_list_vods_calcula_last_page_exata():
    """
    20 vods com limit 10 devem resultar em exatamente 2 paginas.
    """
    service = _make_service_with_db(rows=[], total=20)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)

    assert result["meta"]["lastPage"] == 2


@pytest.mark.asyncio
async def test_list_vods_sem_resultados():
    """
    Deve retornar lista vazia sem quebrar quando nao ha vods.
    """
    service = _make_service_with_db(rows=[], total=0)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)

    assert result["data"] == []
    assert result["meta"]["total"] == 0


# ---------------- LIST VODS: SERIALIZACAO ----------------

@pytest.mark.asyncio
async def test_list_vods_serializa_campos():
    """
    Deve devolver os campos que o front espera, incluindo roomId.
    """
    service = _make_service_with_db(rows=[_row()], total=1)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)
    vod = result["data"][0]

    assert vod["id"] == 1
    assert vod["streamId"] == "teste-1"
    assert vod["roomId"] == ROOM_ID
    assert vod["title"] == "VOD de teste"
    assert vod["recordingPath"] == "abc123"
    assert vod["recordingDurationMs"] == 25900
    assert vod["isVod"] is True
    assert vod["isLive"] is False


@pytest.mark.asyncio
async def test_list_vods_monta_master_playlist_url():
    """
    A URL de playback deve apontar para o Object Storage da Oracle.
    """
    service = _make_service_with_db(rows=[_row(recording_path="xyz789")], total=1)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)
    vod = result["data"][0]

    assert vod["masterPlaylistUrl"] == (
        "https://objectstorage.sa-saopaulo-1.oraclecloud.com"
        "/n/grmsqxilk3cb/b/vod-teste/o/xyz789/media/hls/master.m3u8"
    )


@pytest.mark.asyncio
async def test_list_vods_marca_live_quando_ended_at_null():
    """
    Stream sem ended_at deve ser marcada como live, nao como vod.
    """
    service = _make_service_with_db(rows=[_row(ended_at=None)], total=1)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)
    vod = result["data"][0]

    assert vod["isLive"] is True
    assert vod["isVod"] is False


@pytest.mark.asyncio
async def test_list_vods_serializa_varios_vods():
    """
    Deve serializar todas as linhas retornadas pelo banco.
    """
    rows = [_row(row_id=1), _row(row_id=2), _row(row_id=3)]
    service = _make_service_with_db(rows=rows, total=3)

    result = await service.list_vods(room_id=ROOM_ID, page=1, limit=10)

    assert len(result["data"]) == 3
    assert [v["id"] for v in result["data"]] == [1, 2, 3]


# ---------------- GET VOD ----------------

@pytest.mark.asyncio
async def test_get_vod_not_found():
    """
    Deve retornar 404 quando o stream_id nao existe.
    """
    service = _make_service_with_row(row=None)

    with pytest.raises(SynapseError) as err:
        await service.get_vod(stream_id=999)

    assert err.value.code == 404


@pytest.mark.asyncio
async def test_get_vod_success():
    """
    Deve retornar o vod serializado com a URL de playback montada.
    """
    service = _make_service_with_row(row=_row())

    result = await service.get_vod(stream_id=1)

    assert result["id"] == 1
    assert result["recordingPath"] == "abc123"
    assert result["isVod"] is True
    assert result["masterPlaylistUrl"].endswith("/abc123/media/hls/master.m3u8")


@pytest.mark.asyncio
async def test_get_vod_passa_id_para_o_banco():
    """
    O stream_id recebido deve ser o mesmo consultado no banco.
    """
    service = _make_service_with_row(row=_row(row_id=7))

    await service.get_vod(stream_id=7)

    call = service._store_mock.db_pool.runInteraction.await_args
    assert call.args[0] == "get_vod_by_id"
    assert call.args[2] == 7


# ---------------- DB: GET VODS ----------------

def test_get_vods_filtra_apenas_gravacoes_encerradas():
    """
    Live em andamento (ended_at NULL) nao deve aparecer na listagem de vods.
    """
    txn = _make_txn(fetchall=[])

    db.get_vods(txn, room_id=ROOM_ID, limit=10, offset=0)

    sql = txn.execute.call_args.args[0]
    assert "ended_at IS NOT NULL" in sql


def test_get_vods_ordena_do_mais_recente():
    """
    Vods devem vir do mais recente para o mais antigo.
    """
    txn = _make_txn(fetchall=[])

    db.get_vods(txn, room_id=ROOM_ID, limit=10, offset=0)

    sql = txn.execute.call_args.args[0]
    assert "ORDER BY started_at DESC" in sql


def test_get_vods_passa_parametros_na_ordem():
    """
    Os parametros devem ser (room_id, limit, offset).
    """
    txn = _make_txn(fetchall=[])

    db.get_vods(txn, room_id=ROOM_ID, limit=25, offset=50)

    params = txn.execute.call_args.args[1]
    assert params == (ROOM_ID, 25, 50)


def test_get_vods_retorna_linhas_do_cursor():
    """
    Deve devolver exatamente o que o cursor retornou.
    """
    rows = [_row()]
    txn = _make_txn(fetchall=rows)

    result = db.get_vods(txn, room_id=ROOM_ID, limit=10, offset=0)

    assert result == rows


# ---------------- DB: COUNT VODS ----------------

def test_count_vods_usa_mesmo_filtro_do_list():
    """
    O total precisa contar so gravacoes encerradas, senao a paginacao mente.
    """
    txn = _make_txn(fetchone=(3,))

    db.count_vods(txn, room_id=ROOM_ID)

    sql = txn.execute.call_args.args[0]
    assert "ended_at IS NOT NULL" in sql


def test_count_vods_retorna_total():
    """
    Deve extrair o total da primeira coluna.
    """
    txn = _make_txn(fetchone=(42,))

    result = db.count_vods(txn, room_id=ROOM_ID)

    assert result == 42


def test_count_vods_sem_linhas():
    """
    Deve retornar 0 quando o cursor nao devolve nada.
    """
    txn = _make_txn(fetchone=None)

    result = db.count_vods(txn, room_id=ROOM_ID)

    assert result == 0


# ---------------- DB: GET VOD BY ID ----------------

def test_get_vod_by_id_passa_id():
    """
    Deve consultar pelo id recebido.
    """
    txn = _make_txn(fetchone=None)

    db.get_vod_by_id(txn, stream_id=7)

    params = txn.execute.call_args.args[1]
    assert params == (7,)


def test_get_vod_by_id_retorna_none_quando_nao_existe():
    """
    Deve devolver None para o service transformar em 404.
    """
    txn = _make_txn(fetchone=None)

    result = db.get_vod_by_id(txn, stream_id=999)

    assert result is None