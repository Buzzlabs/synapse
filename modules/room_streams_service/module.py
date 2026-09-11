import logging

from .service import RoomStreamsService
from .resources.get_stream import GetStreamResource
from .resources.set_stream import SetStreamResource

logger = logging.getLogger(__name__)


class RoomStreamsServiceModule:
    def __init__(self, config: dict, api):
        self.api = api

        admin_user_id = config.get("admin_user_id")
        homeserver = config.get("homeserver")

        if not admin_user_id or not homeserver:
            raise RuntimeError(
                "RoomStreamsServiceModule requires 'admin_user_id' and 'homeserver' in config"
            )

        service = RoomStreamsService(
            api=api,
            homeserver=homeserver,
            admin_user_id=admin_user_id,
        )

        api.register_web_resource(
            "/_synapse/room_streams_service/get_stream",
            GetStreamResource(api, service),
        )
        api.register_web_resource(
            "/_synapse/room_streams_service/set_stream",
            SetStreamResource(api, service),
        )

        logger.info("RoomStreamsServiceModule loaded")
