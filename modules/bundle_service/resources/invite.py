import logging

from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class InviteBundleResource(DirectServeJsonResource):
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
            bundle_id = body.get("bundle_id")

            if not bundle_id:
                raise SynapseError(400, "missing bundle_id")

            await self.service.invite_bundle(
                user_id=user_id,
                bundle_id=bundle_id,
            )

            return 200, {"invited": True}

        except SynapseError as e:
            return e.code, {"error": e.msg}