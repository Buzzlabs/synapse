import logging

from synapse.module_api import ModuleApi
from synapse.http.server import respond_with_json
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import ensureDeferred

logger = logging.getLogger(__name__)


def add_cors_headers(request):
    request.setHeader(b"Access-Control-Allow-Origin", b"*")
    request.setHeader(
        b"Access-Control-Allow-Headers",
        b"Authorization, Content-Type",
    )
    request.setHeader(
        b"Access-Control-Allow-Methods",
        b"GET, OPTIONS",
    )


class DiscoverRoomsResource(Resource):
    isLeaf = True

    # pra teste
    ROOM_CONFIG = {
        "!gkOveurKVZZOeNOYDN:localhost": {
            "type": "free",
            "price": 0,
        },
        "!rBuRzPVGpFsVohvUEK:localhost": {
            "type": "paid",
            "price": 1990,  
        },
    }

    def __init__(self, api: ModuleApi, admin_user_id: str):
        super().__init__()
        self.api = api
        self.admin_user_id = admin_user_id
        self.hs = api._hs

    def render_OPTIONS(self, request):
        logger.info("discover_rooms: OPTIONS")
        add_cors_headers(request)
        request.setResponseCode(200)
        request.finish()
        return NOT_DONE_YET

    def render_GET(self, request):
        logger.info("discover_rooms: GET")
        add_cors_headers(request)
        ensureDeferred(self._handle(request))
        return NOT_DONE_YET

    async def _handle(self, request):
        try:
            # autentica quem chamou
            requester = await self.api.get_user_by_req(request)
            client_user_id = requester.user.to_string()
            logger.info("discover_rooms: called by user=%s", client_user_id)

            # admin fixo definido no YAML
            user_id = self.admin_user_id

            store = self.hs.get_datastores().main
            joined_rooms = await store.get_rooms_for_user(user_id)

            logger.info(
                "discover_rooms: found %d rooms for admin=%s",
                len(joined_rooms),
                user_id,
            )

            rooms = []

            store = self.hs.get_datastores().main

            for room_id in joined_rooms:
                # Nome da sala
                state_events = await self.api.get_state_events_in_room(
                    room_id,
                    [("m.room.name", "")]
                )

                name = "Sem nome"
                for ev in state_events:
                    name = ev.content.get("name", "Sem nome")
                    break

                # Member count 
                users = await store.get_users_in_room(room_id)
                member_count = len(users)

                # pra teste 
                config = self.ROOM_CONFIG.get(
                    room_id,
                    {"type": "free", "price": 0}
                )


                rooms.append({
                    "room_id": room_id,
                    "name": name,
                    "member_count": member_count,
                    "type": config["type"],
                    "price": config["price"],
                    "isVisible": True,
                })


            respond_with_json(request, 200, rooms)

        except Exception:
            logger.exception("discover_rooms: failed")
            respond_with_json(request, 500, {"error": "internal"})


class DiscoverRoomsModule:
    def __init__(self, config, api: ModuleApi):
        admin_user_id = config.get("admin_user_id")
        if not admin_user_id:
            raise ValueError("DiscoverRoomsModule requires admin_user_id in config")

        logger.warning(
            "DiscoverRoomsModule loaded, using admin user_id=%s",
            admin_user_id,
        )

        api.register_web_resource(
            path="/_matrix/admin/rooms",
            resource=DiscoverRoomsResource(api, admin_user_id),
        )
