from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError
import logging

logger = logging.getLogger(__name__)


class DeleteRoomResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__(api._hs)   # igual ao ChangeVisibility
        self.api = api
        self.auth = api._hs.get_auth()
        self.service = service

    async def _async_render_POST(self, request):
        requester = await self.auth.get_user_by_req(request)

        if requester is None:
            raise SynapseError(401, "Authentication required")

        content = parse_json_object_from_request(request)
        room_id = content.get("room_id")

        if not room_id:
            raise SynapseError(400, "room_id is required")

        await self.service.delete_room(
            requester=requester,
            room_id=room_id,
        )

        return 200, {"ok": True}
