# module.py
import logging

from synapse.module_api import ModuleApi

from .service import BundleService
from .resources.list import ListBundlesResource
from .resources.create import CreateBundleResource
from .resources.publish import PublishResource
from .resources.update import UpdateBundleResource
from .resources.delete import DeleteBundleResource
# from .resources.activate import ActivateBundleResource

logger = logging.getLogger(__name__)


class BundleServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs

        service = BundleService(api)

        api.register_web_resource(
            "/_synapse/bundles/list",
            ListBundlesResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/bundles/create",
            CreateBundleResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/bundles/publish",
            PublishResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/bundles/update",
            UpdateBundleResource(api, service),
        )

        api.register_web_resource(
            "/_synapse/bundles/delete",
            DeleteBundleResource(api, service),
        )

      