from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

class ChangeVisibilityResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__(api._hs)
        self.service = service

    async def _async_render_POST(self, request):
        content = parse_json_object_from_request(request)

        await self.service.change_visibility(
            requester=request.requester,
            room_id=content["room_id"],
            visible=content["visible"],
            price=content.get("price"),
        )

        return 200, {
            "ok": True,
            "room_id": content["room_id"],
            "visible": content["visible"],
        }
