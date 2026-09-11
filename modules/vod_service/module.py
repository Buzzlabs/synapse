# module.py
import logging
import os

from synapse.module_api import ModuleApi

from .service import VodService
from .resources.list_vods import ListVodsResource
from .resources.get_vod import GetVodResource
from .resources.create_vod import CreateVodResource

logger = logging.getLogger(__name__)


def _read_service_token(config: dict):
    """
    Le o token de servico usado para criar VODs.
    Aceita service_token_file (preferido) ou service_token direto.
    Se nenhum for configurado, a criacao de VOD fica desabilitada (503).
    """
    token_file = config.get("service_token_file")
    if token_file and os.path.exists(token_file):
        with open(token_file, "r") as f:
            return f.read().strip()
    return config.get("service_token")


class VodServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs

        object_storage_base_url = config["object_storage_base_url"]
        namespace = config["namespace"]
        bucket = config["bucket"]
        service_token = _read_service_token(config)

        service = VodService(
            api=api,
            object_storage_base_url=object_storage_base_url,
            namespace=namespace,
            bucket=bucket,
            service_token=service_token,
        )

        self.hs.vod_service = service

        api.register_web_resource(
            "/_synapse/vod_service/list",
            ListVodsResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/vod_service/get",
            GetVodResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/vod_service/create",
            CreateVodResource(api, service),
        )

        logger.info(
            "VodServiceModule carregado (namespace=%s bucket=%s create=%s)",
            namespace,
            bucket,
            "on" if service_token else "off",
        )