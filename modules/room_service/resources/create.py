from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet.defer import ensureDeferred

from synapse.http.servlet import parse_json_object_from_request
from synapse.http.server import respond_with_json


class CreateRoomResource(Resource):
    isLeaf = True

    def __init__(self, api, service):
        self.api = api
        self.service = service

    def render_POST(self, request):
        ensureDeferred(self._handle(request))
        return NOT_DONE_YET

    async def _handle(self, request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        data = parse_json_object_from_request(request)
        room_id = await self.service.create_room(user_id, data)

        respond_with_json(request, 200, {"room_id": room_id})
