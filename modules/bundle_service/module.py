# module.py
import logging

from synapse.module_api import ModuleApi

from .service import BundleService
from modules.room_service.service import RoomService
from .resources.list import ListBundlesResource
from .resources.create import CreateBundleResource
from .resources.publish import PublishResource
from .resources.update import UpdateBundleResource
from .resources.delete import DeleteBundleResource
from .resources.invite import InviteBundleResource

logger = logging.getLogger(__name__)


class BundleServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs
        room_service = self.hs.room_service
        service = BundleService(api, room_service)
        

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

        api.register_web_resource(
            "/_synapse/bundles/invite",
            InviteBundleResource(api, service),
        )

      