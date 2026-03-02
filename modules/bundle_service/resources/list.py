# list.py
from synapse.http.server import DirectServeJsonResource


class ListBundlesResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_GET(self, request):
        bundles = await self.service.list_bundles()
        return 200, {"bundles": bundles}