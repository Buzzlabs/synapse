from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request


class GetFeatureResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        content = parse_json_object_from_request(request)
        room_id = content.get("room_id")
        feature = content.get("feature")
        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not feature:
            raise SynapseError(400, "feature is required")

        result = await self.service.get_feature(room_id=room_id, feature=feature)
        return 200, result