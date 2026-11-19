# get_vod.py
from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request


class GetVodResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        content = parse_json_object_from_request(request)
        vod_pk = content.get("stream_id")

        if not vod_pk:
            raise SynapseError(400, "stream_id is required")

        result = await self.service.get_vod(vod_pk=vod_pk)
        return 200, result
