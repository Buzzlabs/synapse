# service.py
import logging
import time
import uuid

from synapse.module_api import ModuleApi
from synapse.api.errors import SynapseError

from . import db

logger = logging.getLogger(__name__)


class VodService:
    def __init__(
        self,
        api: ModuleApi,
        object_storage_base_url: str,
        namespace: str,
        bucket: str,
        service_token: str = None,
    ):
        self.api = api
        self.hs = api._hs
        self.object_storage_base_url = object_storage_base_url.rstrip("/")
        self.namespace = namespace
        self.bucket = bucket
        # segredo compartilhado com quem cria VODs (finalize.sh do Jibri, OBS, etc).
        # Nao e um usuario logado - e maquina chamando maquina.
        self.service_token = service_token

        self.store = self.hs.get_datastores().main

    # ---------------- URL BUILDERS ----------------
    def _object_prefix(self, recording_path: str) -> str:
        """
        Monta o prefixo da URL nativa do Oracle Object Storage.

        Formato:
        https://objectstorage.<regiao>.oraclecloud.com
            /n/<namespace>/b/<bucket>/o/<recording_path>
        """
        return (
            f"{self.object_storage_base_url}"
            f"/n/{self.namespace}"
            f"/b/{self.bucket}"
            f"/o/{recording_path}"
        )

    def master_playlist_url(self, recording_path: str) -> str:
        return f"{self._object_prefix(recording_path)}/media/hls/master.m3u8"

    def thumbnail_base_url(self, recording_path: str) -> str:
        return f"{self._object_prefix(recording_path)}/media/latest_thumbnail"

    def thumbnail_url(self, recording_path: str, thumb_num: int) -> str:
        return (
            f"{self._object_prefix(recording_path)}"
            f"/media/thumbnails/thumb{thumb_num}.jpg"
        )

    def latest_thumbnail(
        self,
        recording_path: str,
        started_at,
        ended_at,
    ) -> str:
        """
        Pega o thumbnail do meio da gravacao (4 thumbs por minuto).
        """
        if started_at is None or ended_at is None:
            return self.thumbnail_url(recording_path, 0)

        try:
            total_minutes = (ended_at - started_at) / 60000.0
            middle_minute = int(total_minutes // 2)
            thumb_num = middle_minute * 4

            if thumb_num < 0:
                return self.thumbnail_url(recording_path, 0)

            return self.thumbnail_url(recording_path, thumb_num)
        except Exception:
            logger.exception(
                "latest_thumbnail: falha ao calcular para recording_path=%s",
                recording_path,
            )
            return self.thumbnail_url(recording_path, 0)

    # ---------------- SERIALIZER ----------------
    def _serialize(self, row) -> dict:
        (
            row_id,
            stream_id,
            room_id,
            title,
            category_id,
            recording_path,
            recording_duration_ms,
            started_at,
            ended_at,
        ) = row

        return {
            "id": row_id,
            "streamId": stream_id,
            "roomId": room_id,
            "title": title,
            "categoryId": category_id,
            "recordingPath": recording_path,
            "recordingDurationMs": recording_duration_ms,
            "startedAt": started_at,
            "endedAt": ended_at,
            "masterPlaylistUrl": self.master_playlist_url(recording_path),
            "thumbnailBaseUrl": self.thumbnail_base_url(recording_path),
            "latestThumbnail": self.latest_thumbnail(
                recording_path, started_at, ended_at
            ),
            "isLive": ended_at is None,
            "isVod": ended_at is not None,
        }

    # ---------------- LIST ----------------
    async def list_vods(self, room_id: str, page: int = 1, limit: int = 10):
        logger.info(
            "list_vods: room_id=%s page=%s limit=%s", room_id, page, limit
        )

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if page < 1:
            raise SynapseError(400, "page must be >= 1")
        if limit < 1 or limit > 100:
            raise SynapseError(400, "limit must be between 1 and 100")

        offset = (page - 1) * limit

        rows = await self.store.db_pool.runInteraction(
            "get_vods",
            db.get_vods,
            room_id,
            limit,
            offset,
        )

        total = await self.store.db_pool.runInteraction(
            "count_vods",
            db.count_vods,
            room_id,
        )

        logger.info("list_vods: %d vods retornados (total=%d)", len(rows), total)

        return {
            "data": [self._serialize(row) for row in rows],
            "meta": {
                "total": total,
                "page": page,
                "perPage": limit,
                "lastPage": (total + limit - 1) // limit if limit else 1,
            },
        }

    # ---------------- GET ----------------
    async def get_vod(self, stream_id: int):
        logger.info("get_vod: stream_id=%s", stream_id)

        row = await self.store.db_pool.runInteraction(
            "get_vod_by_id",
            db.get_vod_by_id,
            stream_id,
        )

        if not row:
            raise SynapseError(404, "VOD not found")

        return self._serialize(row)

    # ---------------- CREATE (escrita) ----------------
    def assert_service_token(self, token: str) -> None:
        """
        Autentica quem cria VODs. Nao e usuario logado - e um servico
        (finalize.sh do Jibri, OBS, pipeline) mandando um segredo compartilhado.
        """
        if not self.service_token:
            raise SynapseError(503, "VOD creation is not configured (no service token)")
        if not token or token != self.service_token:
            raise SynapseError(403, "Invalid service token")

    async def create_vod(
        self,
        *,
        service_token: str,
        room_id: str,
        recording_path: str,
        title=None,
        started_at=None,
        ended_at=None,
        recording_duration_ms=None,
    ) -> dict:
        self.assert_service_token(service_token)

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not recording_path:
            raise SynapseError(400, "recording_path is required")

        now_ms = int(time.time() * 1000)
        # o backend gera o stream_id, o caller nao precisa se preocupar
        stream_id = f"vod_{uuid.uuid4().hex}"

        logger.info(
            "create_vod: room_id=%s recording_path=%s stream_id=%s",
            room_id,
            recording_path,
            stream_id,
        )

        row = await self.store.db_pool.runInteraction(
            "insert_vod",
            db.insert_vod,
            stream_id,
            room_id,
            title,
            recording_path,
            recording_duration_ms,
            started_at,
            ended_at,
            now_ms,
            now_ms,
        )

        return self._serialize(row)