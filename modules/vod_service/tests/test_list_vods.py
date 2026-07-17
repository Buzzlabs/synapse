import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from io import BytesIO

from twisted.web.test.requesthelper import DummyRequest
from twisted.web.http_headers import Headers

from synapse.api.errors import SynapseError
from modules.vod_service.resources.list_vods import ListVodsResource
from modules.vod_service.resources.get_vod import GetVodResource
from modules.vod_service.module import VodServiceModule

# testa
# 1. endpoints respondem 200 no formato esperado
# 2. query params sao parseados e repassados ao service
# 3. defaults aplicados quando os params nao vem
# 4. stream_id ausente retorna 400
# 5. rotas registradas e config obrigatoria validada no boot

# para testar: PYTHONPATH=. pytest -vv modules/vod_service/tests/test_list_vods.py


# ---------------- HELPERS ----------------

def _make_list_resource(return_value=None):
    api = MagicMock()
    service = MagicMock()
    service.list_vods = AsyncMock(
        return_value=return_value
        if return_value is not None
        else {"data": [], "meta": {"total": 0, "page": 1, "perPage": 10, "lastPage": 0}}
    )
    return ListVodsResource(api, service), service


def _make_list_request(args=None):
    request = DummyRequest([b"_synapse", b"vod_service", b"list"])
    request.args = args or {}
    return request


def _make_get_resource(return_value=None):
    api = MagicMock()
    service = MagicMock()
    service.get_vod = AsyncMock(return_value=return_value or {})
    return GetVodResource(api, service), service


def _make_get_request(body: dict):
    request = DummyRequest([b"_synapse", b"vod_service", b"get"])
    request.method = b"POST"
    request.requestHeaders = Headers({
        b"Content-Type": [b"application/json"],
    })
    request.content = BytesIO(json.dumps(body).encode())
    return request


def _make_config(**overrides):
    config = {
        "object_storage_base_url": "https://objectstorage.sa-saopaulo-1.oraclecloud.com",
        "namespace": "grmsqxilk3cb",
        "bucket": "vod-teste",
    }
    config.update(overrides)
    return config


def _make_module_api():
    api = MagicMock()
    api._hs = MagicMock()
    return api


# ---------------- LIST VODS RESOURCE ----------------

@pytest.mark.asyncio
async def test_list_vods_success():
    """
    Deve retornar 200 e a lista de vods com as URLs montadas.
    """
    resource, service = _make_list_resource({
        "data": [
            {
                "id": 1,
                "title": "VOD de teste",
                "recordingPath": "abc123",
                "masterPlaylistUrl": (
                    "https://objectstorage.sa-saopaulo-1.oraclecloud.com"
                    "/n/grmsqxilk3cb/b/vod-teste/o/abc123/media/hls/master.m3u8"
                ),
                "isVod": True,
            }
        ],
        "meta": {"total": 1, "page": 1, "perPage": 10, "lastPage": 1},
    })

    request = _make_list_request()

    code, body = await resource._async_render_GET(request)

    assert code == 200
    assert "data" in body
    assert len(body["data"]) == 1

    vod = body["data"][0]
    assert vod["recordingPath"] == "abc123"
    assert vod["masterPlaylistUrl"].endswith("/media/hls/master.m3u8")
    assert "oraclecloud.com" in vod["masterPlaylistUrl"]

    service.list_vods.assert_called_once()


@pytest.mark.asyncio
async def test_list_vods_usa_defaults():
    """
    Sem query params deve usar channel_id=4, page=1, limit=10.
    """
    resource, service = _make_list_resource()

    request = _make_list_request()

    await resource._async_render_GET(request)

    service.list_vods.assert_awaited_once_with(
        channel_id=4,
        page=1,
        limit=10,
    )


@pytest.mark.asyncio
async def test_list_vods_repassa_query_params():
    """
    Os query params devem chegar no service como inteiros.
    """
    resource, service = _make_list_resource()

    request = _make_list_request({
        b"channel_id": [b"9"],
        b"page": [b"3"],
        b"limit": [b"25"],
    })

    await resource._async_render_GET(request)

    service.list_vods.assert_awaited_once_with(
        channel_id=9,
        page=3,
        limit=25,
    )


@pytest.mark.asyncio
async def test_list_vods_retorna_meta_da_paginacao():
    """
    O meta da paginacao deve ser repassado intacto para o front.
    """
    resource, _ = _make_list_resource({
        "data": [],
        "meta": {"total": 25, "page": 2, "perPage": 10, "lastPage": 3},
    })

    request = _make_list_request()

    code, body = await resource._async_render_GET(request)

    assert code == 200
    assert body["meta"]["total"] == 25
    assert body["meta"]["lastPage"] == 3


# ---------------- GET VOD RESOURCE ----------------

@pytest.mark.asyncio
async def test_get_vod_success():
    """
    Deve retornar 200 e o vod serializado.
    """
    resource, service = _make_get_resource({
        "id": 1,
        "title": "VOD de teste",
        "recordingPath": "abc123",
        "masterPlaylistUrl": (
            "https://objectstorage.sa-saopaulo-1.oraclecloud.com"
            "/n/grmsqxilk3cb/b/vod-teste/o/abc123/media/hls/master.m3u8"
        ),
        "isVod": True,
    })

    request = _make_get_request({"stream_id": 1})

    code, body = await resource._async_render_POST(request)

    assert code == 200
    assert body["id"] == 1
    assert body["recordingPath"] == "abc123"

    service.get_vod.assert_awaited_once_with(stream_id=1)


@pytest.mark.asyncio
async def test_get_vod_sem_stream_id():
    """
    Deve retornar 400 quando stream_id nao vem no body.
    """
    resource, service = _make_get_resource()

    request = _make_get_request({})

    with pytest.raises(SynapseError) as err:
        await resource._async_render_POST(request)

    assert err.value.code == 400
    service.get_vod.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_vod_stream_id_null():
    """
    stream_id explicitamente null tambem deve retornar 400.
    """
    resource, _ = _make_get_resource()

    request = _make_get_request({"stream_id": None})

    with pytest.raises(SynapseError) as err:
        await resource._async_render_POST(request)

    assert err.value.code == 400


# ---------------- MODULE ----------------

def test_registra_as_duas_rotas():
    """
    Deve registrar /list e /get sob o namespace do modulo.
    """
    api = _make_module_api()

    VodServiceModule(config=_make_config(), api=api)

    paths = [call.args[0] for call in api.register_web_resource.call_args_list]

    assert "/_synapse/vod_service/list" in paths
    assert "/_synapse/vod_service/get" in paths


def test_expoe_service_no_homeserver():
    """
    O service deve ficar acessivel no hs, igual ao room_service.
    """
    api = _make_module_api()

    VodServiceModule(config=_make_config(), api=api)

    assert api._hs.vod_service is not None
    assert api._hs.vod_service.bucket == "vod-teste"
    assert api._hs.vod_service.namespace == "grmsqxilk3cb"


@pytest.mark.parametrize(
    "missing_key",
    ["object_storage_base_url", "namespace", "bucket"],
)
def test_config_obrigatoria_ausente_falha_no_boot(missing_key):
    """
    Config incompleta deve quebrar no startup, nao na primeira request.
    """
    api = _make_module_api()

    config = _make_config()
    del config[missing_key]

    with pytest.raises(KeyError):
        VodServiceModule(config=config, api=api)