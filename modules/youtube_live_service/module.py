import logging

from .service import YoutubeLiveService
from .youtube_client import MockYoutubeClient, RealYoutubeClient
from .resources.start_broadcast import StartBroadcastResource

logger = logging.getLogger(__name__)


def _read_secret_file(path: str) -> str | None:
    if not path:
        return None
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("YoutubeLiveServiceModule: secret file not found: %s", path)
        return None


class YoutubeLiveServiceModule:  

    def __init__(self, config: dict, api):
        self.api = api

        client_id = config.get("youtube_client_id")
        client_secret = _read_secret_file(config.get("youtube_client_secret_file"))
        refresh_token = _read_secret_file(config.get("youtube_refresh_token_file"))

        if client_id and client_secret and refresh_token:
            logger.info("YoutubeLiveServiceModule: using RealYoutubeClient")
            youtube_client = RealYoutubeClient(client_id, client_secret, refresh_token)
        else:
            logger.warning(
                "YoutubeLiveServiceModule: youtube credentials not configured "
                "(missing client_id/client_secret_file/refresh_token_file), "
                "using MockYoutubeClient (broadcasts created will NOT be real)"
            )
            youtube_client = MockYoutubeClient()

        service = YoutubeLiveService(api=api, youtube_client=youtube_client)

        api.register_web_resource(
            "/_synapse/youtube_live_service/start_broadcast",
            StartBroadcastResource(api, service),
        )

        logger.info("YoutubeLiveServiceModule loaded")