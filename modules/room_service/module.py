# module.py
import logging

from synapse.module_api import ModuleApi

from .service import RoomService
from .resources.discover import DiscoverRoomResource
from .resources.invite import InviteRoomResource

logger = logging.getLogger(__name__)

class RoomServiceModule:
    def __init__(self, config, api: ModuleApi):
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

     
