# module.py
import logging
import os

from synapse.module_api import ModuleApi

from .service import ScheduleService
from .resources.list_events import ListEventsResource
from .resources.get_calendar import GetCalendarResource
from .resources.set_calendar import SetCalendarResource

logger = logging.getLogger(__name__)

def _read_google_api_key(config: dict):
    """
    Le a Google API key de arquivo (preferido) ou direto do config.
    A key fica no servidor e nunca vai para o front.
    """
    key_file = config.get("google_api_key_file")
    if key_file and os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    return config.get("google_api_key")


class ScheduleServiceModule:
    def __init__(self, config, api: ModuleApi):
        self.hs = api._hs

        google_api_key = _read_google_api_key(config)
        if not google_api_key:
            raise Exception(
                "schedule_service: 'google_api_key_file' or 'google_api_key' is required"
            )

        timezone_name = config.get("timezone", "America/Sao_Paulo")

        service = ScheduleService(
            api=api,
            google_api_key=google_api_key,
            timezone_name=timezone_name,
        )

        self.hs.schedule_service = service

        api.register_web_resource(
            "/_synapse/schedule_service/list_events",
            ListEventsResource(api, service),
        )
        api.register_web_resource(
            "/_synapse/schedule_service/get_calendar",
            GetCalendarResource(api, service),
        )
        api.register_web_resource(
            "/_synapse/schedule_service/set_calendar",
            SetCalendarResource(api, service),
        )

        logger.info("ScheduleServiceModule carregado")