import logging
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError
 
logger = logging.getLogger(__name__)
 
 
class SpaceChildrenResource(DirectServeJsonResource):
    isLeaf = True
 
    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service
 
    async def _async_render_POST(self, request):
        try:
            # exige apenas usuário autenticado (não precisa ser admin:
            # é a "vitrine" do space, visível para quem pode comprar)
            await self.api.get_user_by_req(request)
 
            body = parse_json_object_from_request(request)
            space_id = body.get("space_id")
 
            if not space_id:
                raise SynapseError(400, "missing space_id")
 
            rooms = await self.service.list_space_children(space_id)
 
            return 200, {"rooms": rooms}
 
        except SynapseError as e:
            return e.code, {"error": e.msg}