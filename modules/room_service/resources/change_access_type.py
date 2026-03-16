import logging
import json

from synapse.http.server import DirectServeJsonResource
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class ChangeAccessTypeResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        requester = await self.api.get_user_by_req(request)

        content = json.loads(request.content.read())

        room_id = content.get("room_id")
        access_type = content.get("access_type")

        if not room_id or not access_type:
            raise SynapseError(400, "Missing room_id or access_type")

        logger.info(
            "change_access_type_resource: request user=%s room_id=%s access_type=%s",
            requester.user.to_string(),
            room_id,
            access_type,
        )

        result = await self.service.change_access_type(
            requester=requester,
            room_id=room_id,
            access_type=access_type,
        )

        logger.info(
            "change_access_type_resource: success user=%s room_id=%s access_type=%s",
            requester.user.to_string(),
            room_id,
            access_type,
        )

        return 200, result
