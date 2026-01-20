import json
import logging

from synapse.http.server import DirectServeJsonResource
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class CreateRoomResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        content = json.loads(request.content.read())

        requester = await self.api.get_user_by_req(request)

        room_id = await self.service.create_room(
            requester=requester,
            data=content,
        )

        return 200, {
            "room_id": room_id,
        }
