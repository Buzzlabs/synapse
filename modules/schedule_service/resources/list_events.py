# list_events.py
from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request


class ListEventsResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        content = parse_json_object_from_request(request)

        room_id = content.get("room_id")
        if not room_id:
            raise SynapseError(400, "room_id is required")

        limit = content.get("limit", 6)
        time_min = content.get("time_min")

        result = await self.service.list_events(
            room_id=room_id,
            limit=limit,
            time_min=time_min,
        )
        return 200, result