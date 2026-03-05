from synapse.http.server import DirectServeJsonResource
from synapse.api.errors import SynapseError
from twisted.web.server import Request
import json
import logging

logger = logging.getLogger(__name__)


class CreateBundleResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request: Request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        body = json.loads(request.content.read().decode("utf-8"))

        bundle_name = body.get("bundle_name")
        price = body.get("price")
        rooms = body.get("rooms", [])

        if not bundle_name:
            raise SynapseError(400, "bundle_name é obrigatório")

        if price is None:
            raise SynapseError(400, "price é obrigatório")

        bundle_id = await self.service.create_bundle(
            bundle_name=bundle_name,
            price=price,
            created_by=user_id,
            rooms=rooms,
        )

        return 201, {
            "bundle_id": bundle_id,
            "status": "draft",
        }