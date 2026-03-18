import json
import logging

from synapse.http.server import DirectServeJsonResource
from synapse.api.errors import SynapseError
from twisted.web.server import Request

logger = logging.getLogger(__name__)


class UpdateBundleResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request: Request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        try:
            body = json.loads(request.content.read())
        except Exception:
            raise SynapseError(400, "Invalid JSON")

        bundle_id = body.get("bundle_id")
        bundle_name = body.get("bundle_name")
        price = body.get("price")
        rooms = body.get("rooms", [])

        result = await self.service.update_bundle(
            user_id=user_id,
            bundle_id=bundle_id,
            bundle_name=bundle_name,
            price=price,
            rooms=rooms,
        )

        return 200, result