from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

class ChangePriceResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__(api._hs)
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        requester = await self.api.get_user_by_req(request)

        content = parse_json_object_from_request(request)

        await self.service.change_price(
            requester=requester,
            room_id=content["room_id"],
            price=content["price"],
        )

        return 200, {"ok": True}
