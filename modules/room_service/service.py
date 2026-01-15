# service.py
import logging
from synapse.module_api import ModuleApi
from synapse.api.errors import SynapseError
from synapse.handlers.room_member import create_requester
from synapse.types import UserID
from . import db

import json
from urllib.parse import quote

from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer
from twisted.internet.defer import succeed


logger = logging.getLogger(__name__)


@implementer(IBodyProducer)
class _BodyProducer:
    def __init__(self, body: bytes):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

class RoomService:
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

        self.agent = Agent(self.hs.get_reactor())

    # ---------------- CREATE ----------------
    # todo
    # async def create_room(self, creator, data):
    #     room_config = self._build_room_config(data)

    #     room_id = await self.api.create_room(
    #         creator_user_id=creator,
    #         config=room_config,
    #     )

    #     await self.store.db_pool.runInteraction(
    #         "save_room_metadata",
    #         db.save_room_metadata,
    #         room_id,
    #         data,
    #     )

    #     if data["visible"]:
    #         await self._ensure_admin(room_id)

    #     return room_id

    # ---------------- DISCOVER ----------------
    async def discover(self):
        rows = await self.store.db_pool.runInteraction(
            "get_visible_rooms",
            db.get_visible_rooms,
        )

        rooms = []
        store = self.store

        for room_id, room_kind, access_type, price, keyword in rows:
            # garante admin na sala
            await self._ensure_admin(room_id)

            # -------- nome da sala --------
            state_events = await self.api.get_state_events_in_room(
                room_id,
                [("m.room.name", "")]
            )

            name = "Sem nome"
            for ev in state_events:
                name = ev.content.get("name", "Sem nome")
                break

            # -------- member count --------
            users = await store.get_users_in_room(room_id)
            member_count = len(users)

            rooms.append({
                "room_id": room_id,
                "name": name,
                "room_kind": room_kind,
                "access_type": access_type,
                "price": price,
                "keyword": keyword,
                "member_count": member_count,
            })

        return rooms


    # ---------------- INVITE ----------------
    async def join_by_keyword(self, target_user_id: str, keyword: str):
        row = await self.store.db_pool.runInteraction(
            "get_room_by_keyword",
            lambda txn: (
                txn.execute(
                    """
                    SELECT room_id
                    FROM room_business
                    WHERE keyword = %s AND visible = TRUE
                    """,
                    (keyword,),
                ),
                txn.fetchone(),
            )[1],
        )

        if not row:
            raise SynapseError(404, "Room not found")

        room_id = row[0]

        logger.info(
            "join_by_keyword: room_id=%s target=%s",
            room_id,
            target_user_id,
        )

        url = (
            f"{self.homeserver}/_synapse/admin/v1/join/"
            f"{quote(room_id)}"
        )

        payload = json.dumps({"user_id": target_user_id}).encode()

        response = await self.agent.request(
            b"POST",
            url.encode(),
            Headers(
                {
                    b"Authorization": [
                        f"Bearer {self.admin_token}".encode()
                    ],
                    b"Content-Type": [b"application/json"],
                }
            ),
            bodyProducer=_BodyProducer(payload),
        )

        response_body = await readBody(response)

        if response.code != 200:
            logger.error(
                "admin join failed code=%s body=%s",
                response.code,
                response_body.decode(errors="ignore"),
            )
            raise SynapseError(500, "admin join failed")

        logger.info(
            "join_by_keyword: success user=%s room=%s",
            target_user_id,
            room_id,
        )

    # ---------------- INTERNAL ----------------
    # todo
    # def _build_room_config(self, data):
    #     kind = data["room_kind"]

    #     if kind == "group":
    #         return {"name": data["name"], "preset": "private_chat"}

    #     if kind == "space":
    #         return {
    #             "name": data["name"],
    #             "preset": "private_chat",
    #             "creation_content": {"type": "m.space"},
    #         }

    #     if kind == "private":
    #         return {"preset": "trusted_private_chat"}

    #     raise Exception("invalid room_kind")

    async def _ensure_admin(self, room_id):
        try:
            await self._force_join(self.admin_user_id, room_id)
        except SynapseError as e:
            if e.code != 403:
                raise

    async def _force_join(self, user_id: str, room_id: str):
        try:
            await self.hs.get_room_member_handler().join_room(
                user_id=user_id,
                room_id=room_id,
                ratelimit=False,
                remote_room_hosts=[],
            )
        except SynapseError as e:
            if e.code != 403:  
                raise

