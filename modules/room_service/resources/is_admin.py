from synapse.http.server import DirectServeJsonResource, respond_with_json
from synapse.module_api import ModuleApi


class IsAdminResource(DirectServeJsonResource):
    isLeaf = True

    def __init__(self, api: ModuleApi):
        super().__init__()
        self.api = api

    async def _async_render_GET(self, request):
        requester = await self.api.get_user_by_req(request)
        user_id = requester.user.to_string()

        is_admin = await self.api.is_user_admin(user_id)

        return respond_with_json(
            request,
            200,
            {
                "user_id": user_id,
                "is_admin": is_admin,
            },
        )
