from synapse.http.server import DirectServeJsonResource
from synapse.api.errors import SynapseError
from twisted.web.server import Request
import json
import logging

logger = logging.getLogger(__name__)


class DeleteBundleResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request: Request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        body = json.loads(request.content.read().decode("utf-8"))

        bundle_id = body.get("bundle_id")

        if not bundle_id:
            raise SynapseError(400, "bundle_id é obrigatório")

        result = await self.service.delete_bundle(
            bundle_id=bundle_id,
            user_id=user_id,
        )

        return 200, result