# get_calendar.py
from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request


class GetCalendarResource(DirectServeJsonResource):
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

        result = await self.service.get_calendar(room_id=room_id)
        return 200, result