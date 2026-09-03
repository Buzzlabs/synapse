import logging

from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class GetStreamResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        try:
            # exige só usuário autenticado (não precisa ser admin: qualquer
            # membro precisa saber a URL do canal para montar/assistir a live)
            await self.api.get_user_by_req(request)

            body = parse_json_object_from_request(request)
            room_id = body.get("room_id")

            result = await self.service.get_stream(room_id)

            return 200, result

        except SynapseError as e:
            return e.code, {"error": e.msg}
