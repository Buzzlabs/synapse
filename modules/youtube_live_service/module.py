import logging

from .service import YoutubeLiveService
from .youtube_client import MockYoutubeClient, RealYoutubeClient, UnconfiguredYoutubeClient, YoutubeClient
from .resources.start_broadcast import StartBroadcastResource
from .resources.stop_broadcast import StopBroadcastResource

logger = logging.getLogger(__name__)


def _read_secret_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, "r") as f:
            return f.read().strip() or None
    except OSError:
        logger.exception("YoutubeLiveServiceModule: cannot read secret file: %s", path)
        return None


def build_youtube_client(config: dict, api) -> YoutubeClient:
    if config.get("youtube_use_mock") is True:
        logger.warning(
            "YoutubeLiveServiceModule: youtube_use_mock is enabled -- broadcasts "
            "created will be FAKE. Do not use this in production."
        )
        return MockYoutubeClient()

    client_id = config.get("youtube_client_id")
    client_secret = _read_secret_file(config.get("youtube_client_secret_file"))
    refresh_token = _read_secret_file(config.get("youtube_refresh_token_file"))

    missing = [
        name
        for name, value in (
            ("youtube_client_id", client_id),
            ("youtube_client_secret_file", client_secret),
            ("youtube_refresh_token_file", refresh_token),
        )
        if not value
    ]

    if not missing:
        logger.info("YoutubeLiveServiceModule: using RealYoutubeClient")
        return RealYoutubeClient(client_id, client_secret, refresh_token, api=api)

    reason = "missing or unreadable config: " + ", ".join(missing)
    logger.error(
        "YoutubeLiveServiceModule: YouTube integration NOT configured (%s). "
        "start_broadcast will return 503. Set youtube_use_mock: true for local development.",
        reason,
    )
    return UnconfiguredYoutubeClient(reason)


class YoutubeLiveServiceModule:
    def __init__(self, config: dict, api):
        self.api = api

        room_streams_service = getattr(api._hs, "room_streams_service", None)
        if room_streams_service is None:
            raise RuntimeError(
                "YoutubeLiveServiceModule requires room_streams_service to be "
                "loaded first in homeserver.yaml's modules list."
            )

        youtube_client = build_youtube_client(config, api)
        service = YoutubeLiveService(
            api=api,
            youtube_client=youtube_client,
            room_streams_service=room_streams_service,
        )

        api.register_web_resource(
            "/_synapse/youtube_live_service/start_broadcast",
            StartBroadcastResource(api, service),
        )
        api.register_web_resource(
            "/_synapse/youtube_live_service/stop_broadcast",
            StopBroadcastResource(api, service),
        )

        logger.info("YoutubeLiveServiceModule loaded")