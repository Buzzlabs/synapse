import json
import logging

from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class PublishResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        body = parse_json_object_from_request(request)

        bundle_id = body.get("bundle_id")
        if not bundle_id:
            raise SynapseError(400, "bundle_id is required")

        result = await self.service.publish_bundle(bundle_id, user_id)

        return 200, result