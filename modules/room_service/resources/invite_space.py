import logging
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class InviteSpaceResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service
        self.admin_user_id = service.admin_user_id

    async def _async_render_POST(self, request):
        try:
            requester = await self.api.get_user_by_req(request)
            user_id = requester.user.to_string()

            body = parse_json_object_from_request(request)
            space_id = body.get("space_id")

            if not space_id:
                raise SynapseError(400, "missing space_id")

            joined = await self.service.invite_space(
                user_id=user_id,
                space_id=space_id,
            )

            return 200, {"joined": True, "rooms": joined}

        except SynapseError as e:
            return e.code, {"error": e.msg}