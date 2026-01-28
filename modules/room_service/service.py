# service.py
import logging
import json
from urllib.parse import quote

from synapse.module_api import ModuleApi
from synapse.api.errors import SynapseError

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
        logger.info("discover: start fetching visible rooms")
        rows = await self.store.db_pool.runInteraction(
            "get_visible_rooms",
            db.get_visible_rooms,
        )

        logger.info("discover: %d visible rooms found in DB", len(rows))
        rooms = []

        for room_id, room_kind, access_type, price, keyword in rows:
            logger.debug(
                "discover: processing room_id=%s kind=%s access=%s visible_price=%s keyword=%s",
                room_id,
                room_kind,
                access_type,
                price,
                keyword,
            )
            if not await self._is_user_in_room(room_id, self.admin_user_id):
                logger.debug(
                    "discover: skipping room_id=%s (admin not in room)",
                    room_id,
                )
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

            logger.debug(
                "discover: room_id=%s name='%s' members=%d",
                room_id,
                name,
                member_count,
            )
            rooms.append({
                "room_id": room_id,
                "name": name,
                "room_kind": room_kind,
                "access_type": access_type,
                "price": price,
                "keyword": keyword,
                "member_count": member_count,
            })

        logger.info(
            "discover: finished, %d rooms returned",
            len(rooms),
        )

        return rooms


    # ---------------- INVITE ----------------
    async def join_by_keyword(self, target_user_id: str, keyword: str):
        logger.info(
            "join_by_keyword: start target=%s keyword=%s",
            target_user_id,
            keyword,
        )
        row = await self.store.db_pool.runInteraction(
            "get_room_by_keyword",
            db.get_room_by_keyword,
            keyword,
        )


        if not row:
            logger.warning(
                "join_by_keyword: no room found for keyword=%s",
                keyword,
            )
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

        logger.debug(
            "join_by_keyword: sending admin join request user=%s room_id=%s",
            target_user_id,
            room_id,
        )
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
        logger.info(
            "create_room: start creator=%s data_keys=%s",
            creator,
            list(data.keys()),
        )
        await self.assert_is_admin(creator)

        if not data.get("keyword"):
            logger.warning(
                "create_room: missing keyword creator=%s",
                creator,
            )
            raise SynapseError(400, "Keyword is required")

        exists = await self.store.db_pool.runInteraction(
            "keyword_exists",
            db.keyword_exists,
            data["keyword"],
        )

        if exists:
            logger.warning(
                "create_room: keyword already in use keyword=%s creator=%s",
                data["keyword"],
                creator,
            )
            raise SynapseError(409, "Keyword already in use")

        visible = bool(data.get("visible", False))
        access_type = data.get("access_type", "private")

        price = int(data.get("price", 0))
        if not visible:
            price = 0

        logger.debug(
            "create_room: business params keyword=%s visible=%s access_type=%s price=%s",
            data["keyword"],
            visible,
            access_type,
            price,
        )

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
        logger.info(
            "create_room: creating room name='%s' creator=%s",
            data.get("name"),
            creator,
        )
        room_id, _ = await self.api.create_room(
            user_id=creator,
            config=room_config,
        )

        logger.info(
            "create_room: room created room_id=%s",
            room_id,
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

        logger.debug(
            "create_room: metadata saved room_id=%s",
            room_id,
        )

        await self._admin_join(room_id, self.admin_user_id)

        logger.debug(
            "create_room: admin joined room room_id=%s admin=%s",
            room_id,
            self.admin_user_id,
        )

        if access_type == "private":
            logger.info(
                "create_room: configuring private access room_id=%s",
                room_id,
            )
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

        logger.info(
            "create_room: success room_id=%s creator=%s",
            room_id,
            creator,
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
        logger.info(
            "change_visibility: start room_id=%s requester=%s visible=%s price=%s",
            room_id,
            requester.user.to_string(),
            visible,
            price,
        )

        is_in_room = await self._is_user_in_room(room_id, requester.user.to_string())
        if not is_in_room:
            logger.warning(
                "change_visibility: requester not in room room_id=%s user=%s",
                room_id,
                requester.user.to_string(),
            )
            raise SynapseError(403, "User not in room")

        access_type = await self.store.db_pool.runInteraction(
            "get_room_access_type",
            db.get_room_access_type,
            room_id,
        )

        if access_type is None:
            logger.warning(
                "change_visibility: room not found room_id=%s",
                room_id,
            )
            raise SynapseError(404, "Room not found")

        access_type = access_type.lower()

        logger.debug(
            "change_visibility: current access_type=%s room_id=%s",
            access_type,
            room_id,
        )

        if not visible:
            logger.debug(
                "change_visibility: setting invisible, price forced to 0 room_id=%s",
                room_id,
            )
            price = 0

        else:
            if access_type == "private":
                if price is None or price <= 0:
                    logger.warning(
                        "change_visibility: missing/invalid price for private room "
                        "room_id=%s price=%s",
                        room_id,
                        price,
                    )
                    raise SynapseError(
                        400,
                        "Missing price: private visible rooms must define a price",
                    )
            else:
                # public
                logger.debug(
                    "change_visibility: public room, price forced to 0 room_id=%s",
                    room_id,
                )
                price = 0

        logger.info(
            "change_visibility: updating DB room_id=%s visible=%s price=%s",
            room_id,
            visible,
            price,
        )

        await self.store.db_pool.runInteraction(
            "update_room_visibility",
            db.update_room_visibility,
            room_id,
            visible,
            price,
        )

        logger.info(
            "change_visibility: success room_id=%s visible=%s price=%s",
            room_id,
            visible,
            price,
        )

        return {
            "room_id": room_id,
            "visible": visible,
            "price": price,
        }

    # ---------------- GET VISIBILITY ----------------
    async def get_room_visibility(self, *, room_id: str):
        logger.info(
            "get_room_visibility: start room_id=%s",
            room_id,
        )

        row = await self.store.db_pool.runInteraction(
            "get_room_visibility",
            db.get_room_visibility,
            room_id,
        )

        if not row:
            logger.warning(
                "get_room_visibility: room not found room_id=%s",
                room_id,
            )
            raise SynapseError(404, "Room not found")

        visible, price, access_type = row

        logger.info(
            "get_room_visibility: success room_id=%s visible=%s price=%s access_type=%s",
            room_id,
            bool(visible),
            price,
            access_type,
        )

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
        user_id = requester.user.to_string()
        logger.info(
            "change_price: start user=%s room_id=%s requested_price=%s",
            user_id,
            room_id,
            price,
        )

        await self.api.is_user_admin(user_id)

        row = await self.store.db_pool.runInteraction(
            "get_room_price_info",
            db.get_room_price_info,
            room_id,
        )

        if not row:
            logger.warning(
                "change_price: room not found room_id=%s user=%s",
                room_id,
                user_id,
            )
            raise SynapseError(404, "Room not found")

        visible_raw, access_type, current_price = row
        visible = bool(visible_raw)

        logger.debug(
            "change_price: current state room_id=%s visible=%s access_type=%s current_price=%s",
            room_id,
            visible,
            access_type,
            current_price,
        )
        if not visible:
            if price not in (None, 0):
                logger.warning(
                    "change_price: rejected non-visible room room_id=%s price=%s",
                    room_id,
                    price,
                )
                raise SynapseError(
                    400,
                    "Cannot set price on a non-visible room",
                )
            price = 0

        else:
            if access_type == "private":
                if price is None or price <= 0:
                    logger.warning(
                        "change_price: invalid price for private room "
                        "room_id=%s price=%s",
                        room_id,
                        price,
                    )
                    raise SynapseError(
                        400,
                        "Private visible rooms must have price > 0",
                    )
            else:
                if price not in (None, 0):
                    logger.warning(
                        "change_price: rejected price on public room "
                        "room_id=%s price=%s",
                        room_id,
                        price,
                    )
                    raise SynapseError(
                        400,
                        "Public rooms cannot have a price",
                    )
                price = 0
        logger.info(
            "change_price: updating price room_id=%s new_price=%s",
            room_id,
            price,
        )
        await self.store.db_pool.runInteraction(
            "update_room_price",
            db.update_room_price,
            room_id,
            price,
        )

        logger.info(
            "change_price: success room_id=%s price=%s",
            room_id,
            price,
        )
        return {
            "room_id": room_id,
            "price": price,
        }

    # ---------------- CHANGE ACCESS TYPE ---------------
    async def change_access_type(
        self,
        *,
        requester,
        room_id: str,
        access_type: str,
        price: int | None = None,
    ):
        logger.info(
            "change_access_type: start room_id=%s user=%s access_type=%s price=%s",
            room_id,
            requester.user.to_string(),
            access_type,
            price,
        )

        await self.api.is_user_admin(requester.user.to_string())

        access_type = access_type.lower()
        if access_type not in ("public", "private"):
            raise SynapseError(400, "Invalid access_type")

        row = await self.store.db_pool.runInteraction(
            "get_room_price_info",
            db.get_room_price_info,
            room_id,
        )

        if not row:
            raise SynapseError(404, "Room not found")

        visible_raw, current_access_type, current_price = row
        visible = bool(visible_raw)

        logger.debug(
            "change_access_type: current state room_id=%s visible=%s access_type=%s price=%s",
            room_id,
            visible,
            current_access_type,
            current_price,
        )

        if not visible:
            logger.debug(
                "change_access_type: room not visible, forcing price=0 room_id=%s",
                room_id,
            )
            price = 0

        else:
            if current_access_type == "public" and access_type == "private":
                # PUBLIC → PRIVATE (visível)
                if price is None or price <= 0:
                    price = 1000
                    logger.info(
                        "change_access_type: no price provided, applying default price=%s room_id=%s",
                        price,
                        room_id,
                    )
                    
            elif current_access_type == "private" and access_type == "public":
                # PRIVATE → PUBLIC
                logger.debug(
                    "change_access_type: private->public, forcing price=0 room_id=%s",
                    room_id,
                )
                price = 0

        logger.info(
            "change_access_type: updating DB room_id=%s access_type=%s price=%s",
            room_id,
            access_type,
            price,
        )

        await self.store.db_pool.runInteraction(
            "update_room_access_and_price",
            db.update_room_access_and_price,
            room_id,
            access_type,
            price,
        )

        logger.info(
            "change_access_type: success room_id=%s access_type=%s price=%s",
            room_id,
            access_type,
            price,
        )

        return {
            "room_id": room_id,
            "access_type": access_type,
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
