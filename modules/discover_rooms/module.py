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

    def __init__(self, api: ModuleApi):
        super().__init__()
        self.api = api

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
            requester = await self.api.get_user_by_req(request)
            user_id = requester.user.to_string()

            logger.info(
                "discover_rooms: authenticated user=%s",
                user_id,
            )

            rooms = [
                {
                    "room_id": "!gkOveurKVZZOeNOYDN:localhost",
                    "name": "Comunidade Nexo",
                    "type": "free",
                    "member_count": 10,
                    "price": 0,
                },
                {
                    "room_id": "!rBuRzPVGpFsVohvUEK:localhost",
                    "name": "Comunidade VIP",
                    "type": "paid",
                    "member_count": 5,
                    "price": 1950,
                },
            ]

            logger.info(
                "discover_rooms: returning %d rooms for user=%s",
                len(rooms),
                user_id,
            )

            respond_with_json(request, 200, rooms)

        except Exception:
            logger.exception("discover_rooms: failed")
            respond_with_json(
                request,
                500,
                {"error": "internal"},
            )

class DiscoverRoomsModule:
    def __init__(self, config, api: ModuleApi):
        logger.warning("DiscoverRoomsModule loaded")

        api.register_web_resource(
            path="/_matrix/discover/rooms",
            resource=DiscoverRoomsResource(api),
        )
