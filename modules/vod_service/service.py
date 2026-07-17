# service.py
import logging

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
    ):
        self.api = api
        self.hs = api._hs
        self.object_storage_base_url = object_storage_base_url.rstrip("/")
        self.namespace = namespace
        self.bucket = bucket

        self.store = self.hs.get_datastores().main

    # ---------------- URL BUILDERS ----------------
    def _object_prefix(self, recording_path: str) -> str:
        """
        Monta o prefixo da URL nativa do Oracle Object Storage.

        Formato:
        https://objectstorage.<regiao>.oraclecloud.com
            /n/<namespace>/b/<bucket>/o/<recording_path>

        Substitui o antigo `https://<CF_DOMAIN>/<recording_path>` do AdonisJS.
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
        Porta do @computed() latestThumbnail do model Stream (AdonisJS).

        Pega o thumbnail do meio da gravacao. O IVS gera 4 thumbs por minuto
        (1 a cada 15s), entao: thumb_num = (minutos_totais / 2) * 4.
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
            channel_id,
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
            "channelId": channel_id,
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
    async def list_vods(self, channel_id: int, page: int = 1, limit: int = 10):
        logger.info(
            "list_vods: channel_id=%s page=%s limit=%s", channel_id, page, limit
        )

        if page < 1:
            raise SynapseError(400, "page must be >= 1")
        if limit < 1 or limit > 100:
            raise SynapseError(400, "limit must be between 1 and 100")

        offset = (page - 1) * limit

        rows = await self.store.db_pool.runInteraction(
            "get_vods",
            db.get_vods,
            channel_id,
            limit,
            offset,
        )

        total = await self.store.db_pool.runInteraction(
            "count_vods",
            db.count_vods,
            channel_id,
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
