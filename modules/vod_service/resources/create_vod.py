# create_vod.py
from synapse.api.errors import SynapseError
from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request


def _extract_service_token(request) -> str:
    """
    Le o token de servico do header Authorization: Bearer <token>.
    Nao usa get_user_by_req porque quem chama e uma maquina (Jibri/OBS),
    nao um usuario logado.
    """
    auth = request.getHeader(b"Authorization")
    if not auth:
        return ""
    auth = auth.decode("utf-8", "ignore")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


class CreateVodResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__()
        self.api = api
        self.service = service

    async def _async_render_POST(self, request):
        service_token = _extract_service_token(request)

        content = parse_json_object_from_request(request)

        room_id = content.get("room_id")
        recording_path = content.get("recording_path")

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not recording_path:
            raise SynapseError(400, "recording_path is required")

        result = await self.service.create_vod(
            service_token=service_token,
            room_id=room_id,
            recording_path=recording_path,
            title=content.get("title"),
            started_at=content.get("started_at"),
            ended_at=content.get("ended_at"),
            recording_duration_ms=content.get("recording_duration_ms"),
        )
        return 200, result