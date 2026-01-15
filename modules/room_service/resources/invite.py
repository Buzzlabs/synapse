import logging
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError
from synapse.types import UserID

logger = logging.getLogger(__name__)

class InviteRoomResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service  
        self.admin_user_id = service.admin_user_id

    async def _async_render_POST(self, request):
        try:
            requester = await self.api.get_user_by_req(request)
            target_user_id = requester.user.to_string()

            body = parse_json_object_from_request(request)
            keyword = body.get("keyword")

            if not keyword:
                raise SynapseError(400, "missing keyword")

            await self.service.join_by_keyword(
                target_user_id=target_user_id,
                keyword=keyword,
            )

            return 200, {"joined": True}

        except SynapseError as e:
            return e.code, {"error": e.msg}
