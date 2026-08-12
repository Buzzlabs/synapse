# module.py
import logging
import time
import os

from synapse.module_api import ModuleApi

from .service import RoomFeaturesService
from .resources.get_feature import GetFeatureResource
from .resources.list_features import ListFeaturesResource
from .resources.set_feature import SetFeatureResource

logger = logging.getLogger(__name__)


def _read_admin_token(config: dict):
    """
    Le o admin token, esperando o arquivo aparecer (~30s), igual ao room_service.
    Aceita admin_token_file (preferido) ou admin_token direto.
    """
    admin_token_file = config.get("admin_token_file")
    if admin_token_file:
        for _ in range(30):  # tenta por ~30s
            if os.path.exists(admin_token_file):
                with open(admin_token_file, "r") as f:
                    return f.read().strip()
            time.sleep(1)
        return None

    return config.get("admin_token")


class RoomFeaturesServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs

        admin_user_id = config["admin_user_id"]
        homeserver = config["homeserver"]
        admin_token = _read_admin_token(config)

        service = RoomFeaturesService(
            api=api,
            admin_user_id=admin_user_id,
            admin_token=admin_token,
            homeserver=homeserver,
        )

        self.hs.room_features_service = service

        api.register_web_resource(
            "/_synapse/room_features/get",
            GetFeatureResource(api, service),
        )
        api.register_web_resource(
            "/_synapse/room_features/list",
            ListFeaturesResource(api, service),
        )
        api.register_web_resource(
            "/_synapse/room_features/set",
            SetFeatureResource(api, service),
        )

        logger.info("RoomFeaturesServiceModule carregado")