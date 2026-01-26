# service.py
import logging
import json
from urllib.parse import quote

from synapse.module_api import ModuleApi
from synapse.api.errors import SynapseError

from .db import update_room_visibility
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet.defer import succeed
from zope.interface import implementer

from . import db

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

    # ---------------- DISCOVER ----------------
    async def discover(self):
        rows = await self.store.db_pool.runInteraction(
            "get_visible_rooms",
            db.get_visible_rooms,
        )

        rooms = []

        for room_id, room_kind, access_type, price, keyword in rows:

            if not await self._is_user_in_room(room_id, self.admin_user_id):
                continue

            state_events = await self.api.get_state_events_in_room(
                room_id,
                [("m.room.name", "")]
            )

            name = "Sem nome"
            for ev in state_events:
                name = ev.content.get("name", "Sem nome")
                break

            users = await self.store.get_users_in_room(room_id)
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
            Headers({
                b"Authorization": [f"Bearer {self.admin_token}".encode()],
                b"Content-Type": [b"application/json"],
            }),
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
    
    # ---------------- CREATE ----------------
    async def create_room(self, requester, data):
        creator = requester.user.to_string()
        await self.assert_is_admin(creator)

        if not data.get("keyword"):
            raise SynapseError(400, "Keyword is required")

        exists = await self.store.db_pool.runInteraction(
            "check_keyword",
            lambda txn: (
                txn.execute(
                    "SELECT 1 FROM room_business WHERE keyword = %s",
                    (data["keyword"],),
                ),
                txn.fetchone(),
            )[1],
        )

        if exists:
            raise SynapseError(409, "Keyword already in use")

        visible = bool(data.get("visible", False))
        access_type = data.get("access_type", "private")

        price = int(data.get("price", 0))
        if not visible:
            price = 0

        join_rule = "public"

        room_config = {
            "name": data["name"],
            "is_direct": False,
            "visibility": "private",
            "initial_state": [
                {
                    "type": "m.room.join_rules",
                    "state_key": "",
                    "content": {"join_rule": join_rule},
                },
                {
                    "type": "m.room.power_levels",
                    "state_key": "",
                    "content": {
                        "users": {
                            creator: 100,
                            self.admin_user_id: 100,
                        },
                        "users_default": 0,
                        "events_default": 50,
                        "state_default": 50,
                        "ban": 50,
                        "kick": 50,
                        "redact": 50,
                        "invite": 50,
                    },
                },
            ],
        }

        room_id, _ = await self.api.create_room(
            user_id=creator,
            config=room_config,
        )

        await self.store.db_pool.runInteraction(
            "save_room_metadata",
            db.save_room_metadata,
            room_id,
            {
                **data,
                "price": price,
                "visible": visible,
            },
        )

        await self._admin_join(room_id, self.admin_user_id)

        if access_type == "private":
            await self._admin_send_state(
                room_id,
                "m.room.join_rules",
                "",
                {"join_rule": "invite"},
            )
            await self._admin_send_state(
                room_id,
                "m.room.guest_access",
                "",
                {"guest_access": "forbidden"},
            )

        return room_id

    # ---------------- CHANGE VISIBILITY ----------------
    async def change_visibility(
        self,
        *,
        requester,
        room_id: str,
        visible: bool,
        price: int | None = None,
    ):
        await self._is_user_in_room(room_id, requester)

        row = await self.store.db_pool.runInteraction(
            "get_room_access_type",
            lambda txn: (
                txn.execute(
                    """
                    SELECT access_type
                    FROM room_business
                    WHERE room_id = ?
                    """,
                    (room_id,),
                ),
                txn.fetchone(),
            )[1],
        )

        if not row:
            raise SynapseError(404, "Room not found")

        access_type = row[0]  # 'public' | 'private'

        if not visible:
            # nv → preço irrelevante
            price = 0

        else:
            # visible = true
            if access_type == "private":
                if price is None or price <= 0:
                    raise SynapseError(
                        400,
                        "Missing price: private visible rooms must define a price",
                    )
            else:
                # public
                price = 0

        def _update(txn):
            update_room_visibility(
                txn,
                room_id,
                visible=visible,
                price=price,
            )

        await self.store.db_pool.runInteraction(
            "update_room_visibility",
            _update,
        )

        return {
            "room_id": room_id,
            "visible": visible,
            "price": price,
        }

    # ---------------- GET VISIBILITY ----------------
    async def get_room_visibility(self, *, room_id: str):
        row = await self.store.db_pool.runInteraction(
            "get_room_visibility",
            lambda txn: (
                txn.execute(
                    """
                    SELECT visible, price, access_type
                    FROM room_business
                    WHERE room_id = ?
                    """,
                    (room_id,),
                ),
                txn.fetchone(),
            )[1],
        )

        if not row:
            raise SynapseError(404, "Room not found")

        visible, price, access_type = row

        return {
            "room_id": room_id,
            "visible": bool(visible),
            "price": int(price),
            "access_type": access_type,
        }

    # ---------------- CHANGE PRICE ----------------
    async def change_price(
        self,
        *,
        requester,
        room_id: str,
        price: int,
    ):
        # só admin global
        logger.info("user: %s", requester)
        await self.api.is_user_admin(requester.user.to_string())

        row = await self.store.db_pool.runInteraction(
            "get_room_price_info",
            db.get_room_price_info,
            room_id,
        )

        if not row:
            raise SynapseError(404, "Room not found")

        visible_raw, access_type, current_price = row
        visible = bool(visible_raw)

        # regra de negócio
        if not visible:
            price = 0
        else:
            if access_type == "private":
                if price <= 0:
                    raise SynapseError(
                        400,
                        "Private visible rooms must have price > 0",
                    )
            else:
                # público nunca paga
                price = 0

        await self.store.db_pool.runInteraction(
            "update_room_price",
            db.update_room_price,
            room_id,
            price,
        )

        return {
            "room_id": room_id,
            "price": price,
        }


    # ---------------- INTERNAL ----------------
    async def assert_is_admin(self, user_id: str):
        is_admin = await self.api.is_user_admin(user_id)

        if not is_admin:
            raise SynapseError(
                403,
                "Only Synapse admins can perform this action"
            )

    async def _ensure_admin(self, room_id: str):
        try:

            await self._admin_join(room_id, self.admin_user_id)
        except SynapseError as e:
            if e.code != 403:
                raise


    async def _admin_join(self, room_id: str, user_id: str):
        url = (
            f"{self.homeserver}/_synapse/admin/v1/join/"
            f"{quote(room_id)}"
        )

        payload = json.dumps({"user_id": user_id}).encode()

        response = await self.agent.request(
            b"POST",
            url.encode(),
            Headers({
                b"Authorization": [f"Bearer {self.admin_token}".encode()],
                b"Content-Type": [b"application/json"],
            }),
            bodyProducer=_BodyProducer(payload),
        )

        body = await readBody(response)

        if response.code not in (200, 403):
            raise SynapseError(
                response.code,
                body.decode(errors="ignore"),
            )

    async def _is_user_in_room(self, room_id: str, user_id: str) -> bool:
        users = await self.store.get_users_in_room(room_id)
        return user_id in users

    async def _admin_send_state(self, room_id: str, event_type: str, state_key: str, content: dict):
        url = (
            f"{self.homeserver}/_matrix/client/v3/rooms/"
            f"{quote(room_id)}/state/"
            f"{quote(event_type)}/"
            f"{quote(state_key)}"
        )

        payload = json.dumps(content).encode()

        response = await self.agent.request(
            b"PUT",
            url.encode(),
            Headers({
                b"Authorization": [f"Bearer {self.admin_token}".encode()],
                b"Content-Type": [b"application/json"],
            }),
            bodyProducer=_BodyProducer(payload),
        )

        body = await readBody(response)

        if response.code != 200:
            logger.error(
                "admin send_state failed %s code=%s body=%s",
                event_type,
                response.code,
                body.decode(errors="ignore"),
            )
            raise SynapseError(500, "admin send_state failed")
