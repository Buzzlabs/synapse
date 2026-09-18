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

    # ---------------- GET STREAM ----------------
    async def get_stream(self, room_id: str):
        
        if not room_id:
            raise SynapseError(400, "missing room_id")

        row = await self.store.db_pool.runInteraction(
            "get_stream",
            db.get_stream,
            room_id,
        )

        if row is None:
            return {"room_id": room_id, "playback_url": None, "provider": "fixed"}

        return row

    # ---------------- SET STREAM ----------------
    async def set_stream(self, user_id: str, room_id: str, playback_url: str | None, provider: str = "fixed"):
        
        is_admin = await self._is_admin(user_id)
        if not is_admin:
            logger.warning(
                "set_stream: permission denied user=%s room_id=%s",
                user_id,
                room_id,
            )
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
            # youtube: não guardamos URL fixa aqui
            playback_url = None

        await self.store.db_pool.runInteraction(
            "set_stream",
            db.set_stream,
            room_id,
            playback_url,
            provider,
        )

        logger.info(
            "set_stream: room_id=%s provider=%s updated by user=%s",
            room_id,
            provider,
            user_id,
        )

        return {"room_id": room_id, "playback_url": playback_url, "provider": provider}