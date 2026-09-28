import logging

from .service import YoutubeLiveService
from .youtube_client import (
    MockYoutubeClient,
    RealYoutubeClient,
    UnconfiguredYoutubeClient,
    YoutubeClient,
)
from .resources.start_broadcast import StartBroadcastResource

logger = logging.getLogger(__name__)


def _read_secret_file(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, "r") as f:
            return f.read().strip() or None
    except OSError:
        # FileNotFoundError, PermissionError, IsADirectoryError, ...
        # Não derruba o Synapse na inicialização: o módulo cai no estado
        # "não configurado" (503), com o motivo no log.
        logger.exception("YoutubeLiveServiceModule: cannot read secret file: %s", path)
        return None


def build_youtube_client(config: dict, api) -> YoutubeClient:
    """
    Escolhe o client conforme a config. Ordem de decisão:

    1. youtube_use_mock: true  -> MockYoutubeClient (só dev/teste, loga WARNING).
    2. client_id + client_secret + refresh_token presentes -> RealYoutubeClient.
    3. qualquer outro caso -> UnconfiguredYoutubeClient: loga ERROR dizendo o
       que falta e o endpoint responde 503. Nunca cai no mock em silêncio.
    """
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
        "start_broadcast will return 503. Set youtube_use_mock: true for local "
        "development.",
        reason,
    )
    return UnconfiguredYoutubeClient(reason)


class YoutubeLiveServiceModule:
    """
    Sem credenciais completas e sem youtube_use_mock, o módulo carrega
    normalmente (não derruba o Synapse), mas start_broadcast responde 503.
    """

    def __init__(self, config: dict, api):
        self.api = api

        youtube_client = build_youtube_client(config, api)
        service = YoutubeLiveService(api=api, youtube_client=youtube_client)

        api.register_web_resource(
            "/_synapse/youtube_live_service/start_broadcast",
            StartBroadcastResource(api, service),
        )

        logger.info("YoutubeLiveServiceModule loaded")