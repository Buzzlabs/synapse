import logging

from synapse.http.server import DirectServeJsonResource
from synapse.http.servlet import parse_json_object_from_request
from synapse.api.errors import SynapseError

logger = logging.getLogger(__name__)


class ChangeVisibilityResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api, service):
        super().__init__(api._hs)
        self.api = api
        self.auth = api._hs.get_auth()
        self.service = service

    async def _async_render_POST(self, request):
        requester = await self.auth.get_user_by_req(request)

        if requester is None:
            logger.warning(
                "change_visibility_resource: unauthenticated request"
            )
            raise SynapseError(401, "Authentication required")

        content = parse_json_object_from_request(request)

        room_id = content.get("room_id")
        visible = content.get("visible")
        price = content.get("price")

        if room_id is None or visible is None:
            raise SynapseError(
                400,
                "Missing required fields: room_id, visible",
            )

        logger.info(
            "change_visibility_resource: request user=%s room_id=%s visible=%s price=%s",
            requester.user.to_string(),
            room_id,
            visible,
            price,
        )
        
        await self.service.change_visibility(
            requester=requester,
            room_id=room_id,
            visible=visible,
            price=price,
        )

        logger.info(
            "change_visibility_resource: success user=%s room_id=%s",
            requester.user.to_string(),
            room_id,
        )

        return 200, {
            "ok": True,
            "room_id": room_id,
            "visible": visible,
        }
