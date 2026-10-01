import logging

from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class ClearYoutubeBroadcastResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        try:
            requester = await self.api.get_user_by_req(request)
            user_id = requester.user.to_string()

            body = parse_json_object_from_request(request)
            room_id = body.get("room_id")

            await self.service.clear_youtube_broadcast(user_id=user_id, room_id=room_id)

            return 200, {"room_id": room_id, "cleared": True}

        except SynapseError as e:
            return e.code, {"error": e.msg}
