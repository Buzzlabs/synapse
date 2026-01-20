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
        rows = await self.store.db_pool.runInteraction(
            "get_visible_rooms",
            db.get_visible_rooms,
        )

        rooms = []

        for room_id, room_kind, access_type, price, keyword in rows:

            # 🔒 FILTRO: admin precisa estar na sala
            if not await self._is_user_in_room(room_id, self.admin_user_id):
                continue

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

        join_rule = (
            "invite"
            if data.get("access_type") == "private"
            else "public"
        )

        room_config = {
            "name": data["name"],
            "is_direct": False,
            "visibility": "private",

            # ❌ NUNCA usar preset aqui
            # "preset": "public_chat",

            # ✅ tudo definido ANTES da sala existir
            "initial_state": [
                {
                    "type": "m.room.join_rules",
                    "state_key": "",
                    "content": {
                        "join_rule": join_rule
                    },
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

        # 1️⃣ cria a sala (já nasce correta)
        room_id, _ = await self.api.create_room(
            user_id=creator,
            config=room_config,
        )

        # 2️⃣ salva metadados
        await self.store.db_pool.runInteraction(
            "save_room_metadata",
            db.save_room_metadata,
            room_id,
            data,
        )

        # 3️⃣ admin entra (já tem PL 100 definido)
        await self._admin_join(room_id, self.admin_user_id)

        # 4️⃣ FECHA A SALA (AGORA SIM FUNCIONA)
        if data.get("access_type") == "paid":
            # 1️⃣ join_rules = invite
            await self._admin_send_state(
                room_id,
                "m.room.join_rules",
                "",
                {"join_rule": "invite"},
            )

            # 2️⃣ guest_access = forbidden
            await self._admin_send_state(
                room_id,
                "m.room.guest_access",
                "",
                {"guest_access": "forbidden"},
            )


        return room_id


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
