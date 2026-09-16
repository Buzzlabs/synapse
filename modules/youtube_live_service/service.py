import logging

from synapse.api.errors import SynapseError

from .youtube_client import YoutubeClient

logger = logging.getLogger(__name__)


class YoutubeLiveService:

    def __init__(self, api, youtube_client: YoutubeClient):
        self.api = api
        self.youtube_client = youtube_client

    async def start_broadcast(self, *, user_id: str, room_id: str, title: str):
        """
        Cria uma nova transmissão no YouTube para a sala. Retorna os dados
        que o front precisa: a URL para assistir (o widget) e a chave de
        ingestão (para a pessoa colar no OBS).
        """
        is_admin = await self.api.is_user_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only admins can start a broadcast")

        if not room_id:
            raise SynapseError(400, "missing room_id")

        if not title or not title.strip():
            raise SynapseError(400, "missing title")

        logger.info(
            "start_broadcast: creating youtube broadcast room_id=%s user=%s title=%s",
            room_id,
            user_id,
            title,
        )

        try:
            broadcast = await self.youtube_client.create_broadcast(title.strip())
        except NotImplementedError:
            # credenciais reais ainda não configuradas
            logger.error("start_broadcast: youtube client not configured yet")
            raise SynapseError(503, "YouTube integration not configured yet")
        except Exception:
            logger.exception(
                "start_broadcast: failed to create youtube broadcast room_id=%s",
                room_id,
            )
            raise SynapseError(502, "Failed to create YouTube broadcast")

        logger.info(
            "start_broadcast: success room_id=%s broadcast_id=%s",
            room_id,
            broadcast.broadcast_id,
        )

        return {
            "room_id": room_id,
            "broadcast_id": broadcast.broadcast_id,
            "watch_url": broadcast.watch_url,
            "ingestion_address": broadcast.ingestion_address,
            "stream_key": broadcast.stream_key,
        }
