# module.py
import logging

from synapse.module_api import ModuleApi

from .service import RoomFeaturesService
from .resources.get_feature import GetFeatureResource
from .resources.list_features import ListFeaturesResource
from .resources.set_feature import SetFeatureResource
from modules._common.secret_file import read_secret_file

logger = logging.getLogger(__name__)


def _read_admin_token(config: dict):
    """
    Le o admin token, esperando o arquivo aparecer (~30s), igual ao room_service.
    Aceita admin_token_file (preferido) ou admin_token direto.
    """
    admin_token_file = config.get("admin_token_file")
    if admin_token_file:
        return read_secret_file(admin_token_file, wait_seconds=30)  # tenta por ~30s

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