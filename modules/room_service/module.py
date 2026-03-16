# module.py
import logging

from synapse.module_api import ModuleApi

from .service import RoomService
from .resources.discover import DiscoverRoomResource
from .resources.invite import InviteRoomResource
from .resources.create import CreateRoomResource
from .resources.change_visibility import ChangeVisibilityResource
from .resources.get_visibility import GetVisibilityResource
from .resources.change_price import ChangePriceResource
from .resources.change_access_type import ChangeAccessTypeResource
from .resources.delete_room import DeleteRoomResource
from modules.room_service.resources.is_admin import IsAdminResource

logger = logging.getLogger(__name__)

class RoomServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs  
        admin_user_id = config["admin_user_id"]
        admin_token = config["admin_token"]
        homeserver = config["homeserver"]

        service = RoomService(
            api=api,
            admin_user_id=admin_user_id,
            admin_token=admin_token,
            homeserver=homeserver,
        )

        api.register_web_resource(
            "/_synapse/room_service/discover",
            DiscoverRoomResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/invite",
            InviteRoomResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/create",
            CreateRoomResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/is_admin",
            IsAdminResource(api),
        )

        api.register_web_resource(
            "/_synapse/room_service/changevisibility",
            ChangeVisibilityResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/getvisibility",
            GetVisibilityResource(self.hs, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/changeprice",
            ChangePriceResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/changeaccesstype",
            ChangeAccessTypeResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/room_service/deleteroom",
            DeleteRoomResource(api, service),
        )
