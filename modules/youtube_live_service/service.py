import logging

from synapse.api.errors import SynapseError

from .youtube_client import YoutubeClient, YoutubeNotConfiguredError

logger = logging.getLogger(__name__)


class YoutubeLiveService:
    def __init__(self, api, youtube_client: YoutubeClient, room_streams_service):
        self.api = api
        self.youtube_client = youtube_client
        self.room_streams_service = room_streams_service

    async def start_broadcast(self, *, user_id: str, room_id: str, title: str):
        is_admin = await self.api.is_user_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only admins can start a broadcast")

        if not room_id:
            raise SynapseError(400, "missing room_id")

        if not title or not title.strip():
            raise SynapseError(400, "missing title")

        await self.room_streams_service.require_youtube_room(room_id)

        logger.info(
            "start_broadcast: creating youtube broadcast room_id=%s user=%s title=%s",
            room_id, user_id, title,
        )

        try:
            broadcast = await self.youtube_client.create_broadcast(title.strip())
        except YoutubeNotConfiguredError as e:
            logger.error("start_broadcast: youtube integration not configured: %s", e)
            raise SynapseError(503, "YouTube integration not configured")
        except Exception:
            logger.exception("start_broadcast: failed to create youtube broadcast room_id=%s", room_id)
            raise SynapseError(502, "Failed to create YouTube broadcast")

        logger.info("start_broadcast: success room_id=%s broadcast_id=%s", room_id, broadcast.broadcast_id)

        try:
            await self.room_streams_service.set_youtube_broadcast(
                room_id, broadcast.broadcast_id, broadcast.watch_url
            )
        except Exception:
            logger.exception(
                "start_broadcast: broadcast created but failed to persist room_id=%s broadcast_id=%s",
                room_id, broadcast.broadcast_id,
            )

        return {
            "room_id": room_id,
            "broadcast_id": broadcast.broadcast_id,
            "watch_url": broadcast.watch_url,
            "ingestion_address": broadcast.ingestion_address,
            "stream_key": broadcast.stream_key,
        }

    async def stop_broadcast(self, *, user_id: str, room_id: str):
        """
        Encerra a transmissão de verdade no YouTube (liveBroadcasts.transition
        para 'complete'), e só depois limpa o registro local. Antes desta
        função, "Encerrar transmissão" no Element só removia o widget do
        Matrix -- a live continuava ativa no YouTube até o encoder parar ou
        alguém encerrar manualmente no YouTube Studio.

        Se a chamada ao YouTube falhar, o registro local NÃO é limpo: ao
        contrário de start_broadcast (onde falhar ao persistir só perde uma
        conveniência, já que o broadcast existe de verdade), aqui limpar o
        banco mesmo com o YouTube recusando faria o Element achar que a
        live acabou quando ela continua no ar -- pior que mostrar um erro.
        """
        is_admin = await self.api.is_user_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only admins can stop a broadcast")

        if not room_id:
            raise SynapseError(400, "missing room_id")

        stream = await self.room_streams_service.get_stream(room_id)
        broadcast_id = stream.get("youtube_broadcast_id")

        if not broadcast_id:
            raise SynapseError(400, "no active YouTube broadcast for this room")

        logger.info("stop_broadcast: ending youtube broadcast room_id=%s broadcast_id=%s", room_id, broadcast_id)

        try:
            await self.youtube_client.end_broadcast(broadcast_id)
        except YoutubeNotConfiguredError as e:
            logger.error("stop_broadcast: youtube integration not configured: %s", e)
            raise SynapseError(503, "YouTube integration not configured")
        except Exception:
            logger.exception(
                "stop_broadcast: failed to end youtube broadcast room_id=%s broadcast_id=%s",
                room_id, broadcast_id,
            )
            raise SynapseError(502, "Failed to end YouTube broadcast")

        logger.info("stop_broadcast: success room_id=%s broadcast_id=%s", room_id, broadcast_id)

        await self.room_streams_service.clear_youtube_broadcast(user_id=user_id, room_id=room_id)

        return {"room_id": room_id, "broadcast_id": broadcast_id, "stopped": True}