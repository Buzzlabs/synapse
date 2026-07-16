# module.py
import logging

from synapse.module_api import ModuleApi

from .service import VodService
from .resources.list_vods import ListVodsResource
from .resources.get_vod import GetVodResource

logger = logging.getLogger(__name__)


class VodServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs

        object_storage_base_url = config["object_storage_base_url"]
        namespace = config["namespace"]
        bucket = config["bucket"]

        service = VodService(
            api=api,
            object_storage_base_url=object_storage_base_url,
            namespace=namespace,
            bucket=bucket,
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

        logger.info(
            "VodServiceModule carregado (namespace=%s bucket=%s)",
            namespace,
            bucket,
        )
