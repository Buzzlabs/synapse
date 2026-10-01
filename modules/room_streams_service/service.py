import logging

from synapse.api.errors import SynapseError

from . import db

logger = logging.getLogger(__name__)


class RoomStreamsService:
    VALID_PROVIDERS = ("fixed", "youtube")

    def __init__(self, api, homeserver: str, admin_user_id: str):
        self.api = api
        self.store = api._hs.get_datastores().main
        self.homeserver = homeserver
        self.admin_user_id = admin_user_id

    async def _is_admin(self, user_id: str) -> bool:
        try:
            return await self.api.is_user_admin(user_id)
        except Exception:
            logger.exception("_is_admin: error checking admin for %s", user_id)
            return False

    async def get_stream(self, room_id: str):
        if not room_id:
            raise SynapseError(400, "missing room_id")

        row = await self.store.db_pool.runInteraction("get_stream", db.get_stream, room_id)

        if row is None:
            return {
                "room_id": room_id,
                "playback_url": None,
                "provider": "fixed",
                "youtube_broadcast_id": None,
                "youtube_watch_url": None,
            }

        return row

    async def set_stream(self, user_id: str, room_id: str, playback_url, provider: str = "fixed"):
        is_admin = await self._is_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only admins can set the stream channel")

        if not room_id:
            raise SynapseError(400, "missing room_id")

        if provider not in self.VALID_PROVIDERS:
            raise SynapseError(400, f"invalid provider: {provider}")

        if provider == "fixed":
            if not playback_url or not playback_url.strip():
                raise SynapseError(400, "missing playback_url")
            playback_url = playback_url.strip()
        else:
            playback_url = None

        await self.store.db_pool.runInteraction("set_stream", db.set_stream, room_id, playback_url, provider)

        return {"room_id": room_id, "playback_url": playback_url, "provider": provider}

    async def require_youtube_room(self, room_id: str) -> None:
        """
        Confirma que a sala existe e está configurada como provider='youtube',
        antes de criar um broadcast pra ela. Chamado pelo youtube_live_service
        no início de start_broadcast, para não gastar uma chamada à API do
        Google contra uma sala inexistente ou configurada como canal fixo.
        """
        row = await self.store.db_pool.runInteraction("get_stream", db.get_stream, room_id)

        if row is None:
            raise SynapseError(404, "Room has no stream configuration; configure it first")

        if row["provider"] != "youtube":
            raise SynapseError(
                400,
                f"room is configured with provider={row['provider']!r}, not 'youtube'",
            )

    async def set_youtube_broadcast(self, room_id: str, broadcast_id: str, watch_url: str) -> None:
        """Persiste o broadcast recém-criado, chamado pelo youtube_live_service
        depois que o YouTube confirma a criação."""
        await self.store.db_pool.runInteraction(
            "set_youtube_broadcast",
            db.set_youtube_broadcast,
            room_id,
            broadcast_id,
            watch_url,
        )

    async def clear_youtube_broadcast(self, user_id: str, room_id: str) -> None:
        """
        Chamado quando alguém encerra uma live (removendo o widget no
        Matrix). Admin-only, mesmo padrão do resto do módulo -- quem pode
        mandar o widget pode encerrar, mas quem limpa o registro no banco
        segue a mesma regra de permissão que set_stream.
        """
        is_admin = await self._is_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only admins can clear the stream")

        if not room_id:
            raise SynapseError(400, "missing room_id")

        await self.store.db_pool.runInteraction(
            "clear_youtube_broadcast", db.clear_youtube_broadcast, room_id
        )
