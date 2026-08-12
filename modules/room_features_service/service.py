# service.py
import logging
import time

from synapse.module_api import ModuleApi
from synapse.api.errors import SynapseError

from . import db

logger = logging.getLogger(__name__)


class RoomFeaturesService:
    """
    Liga/desliga features por sala (tabela room_features).

    Leitura: qualquer um pode consultar se uma feature esta ligada.
    Escrita: apenas admin global (reusa is_admin, igual ao room_service).

    Feature ausente = desligada (get retorna enabled=False, nunca 404).
    """

    def __init__(
        self,
        api: ModuleApi,
        admin_user_id: str,
        admin_token: str,
        homeserver: str,
    ):
        self.api = api
        self.hs = api._hs
        self.admin_user_id = admin_user_id
        self.admin_token = admin_token
        self.homeserver = homeserver

        self.store = self.hs.get_datastores().main

    # ---------------- ADMIN CHECK ----------------
    async def assert_is_admin(self, user_id: str):
        is_admin = await self.api.is_user_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only Synapse admins can perform this action")

    # ---------------- READ ----------------
    async def get_feature(self, room_id: str, feature: str) -> dict:
        logger.info("get_feature: room_id=%s feature=%s", room_id, feature)

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not feature:
            raise SynapseError(400, "feature is required")

        row = await self.store.db_pool.runInteraction(
            "get_room_feature",
            db.get_feature,
            room_id,
            feature,
        )

        # ausente = desligada, nunca 404
        enabled = bool(row[0]) if row else False

        return {
            "roomId": room_id,
            "feature": feature,
            "enabled": enabled,
        }

    async def list_features(self, room_id: str) -> dict:
        logger.info("list_features: room_id=%s", room_id)

        if not room_id:
            raise SynapseError(400, "room_id is required")

        rows = await self.store.db_pool.runInteraction(
            "list_room_features",
            db.list_features,
            room_id,
        )

        return {
            "roomId": room_id,
            "features": {feature: bool(enabled) for (feature, enabled) in rows},
        }

    # ---------------- WRITE ----------------
    async def set_feature(self, *, requester, room_id: str, feature: str, enabled: bool) -> dict:
        user_id = requester.user.to_string()
        logger.info("set_feature: requester=%s room_id=%s feature=%s enabled=%s",
                    user_id, room_id, feature, enabled)

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not feature:
            raise SynapseError(400, "feature is required")
        if not isinstance(enabled, bool):
            raise SynapseError(400, "enabled must be a boolean")

        await self.assert_is_admin(user_id)

        now_ms = int(time.time() * 1000)
        await self.store.db_pool.runInteraction(
            "set_room_feature", db.set_feature, room_id, feature, enabled, now_ms,
        )
        return {"roomId": room_id, "feature": feature, "enabled": enabled}