# list.py
from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource


class ListBundlesResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_GET(self, request):

        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        bundles = await self.service.list_bundles(user_id)

        return 200, {"bundles": bundles}