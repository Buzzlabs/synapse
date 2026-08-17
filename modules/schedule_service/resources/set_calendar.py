# set_calendar.py
from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request


class SetCalendarResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        # quem chama (para o admin check) - requester inteiro, igual room_features
        requester = await self.api.get_user_by_req(request)

        content = parse_json_object_from_request(request)

        room_id = content.get("room_id")
        calendar_id = content.get("calendar_id")

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not calendar_id:
            raise SynapseError(400, "calendar_id is required")

        result = await self.service.set_calendar(
            requester=requester,
            room_id=room_id,
            calendar_id=calendar_id,
        )
        return 200, result