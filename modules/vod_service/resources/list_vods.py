from synapse.http.server import DirectServeJsonResource, respond_with_json
from synapse.http.servlet import parse_integer


class ListVodsResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_GET(self, request):
        channel_id = parse_integer(request, "channel_id", default=4)
        page = parse_integer(request, "page", default=1)
        limit = parse_integer(request, "limit", default=10)

        result = await self.service.list_vods(
            channel_id=channel_id,
            page=page,
            limit=limit,
        )
        respond_with_json(request, 200, result, send_cors=True)