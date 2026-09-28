"""
youtube_client.py — fala com a YouTube Live Streaming API.

MockYoutubeClient: dados falsos, usado enquanto não há credenciais.
RealYoutubeClient: implementação real, usando google-api-python-client.

Requer as libs:
    pip install google-auth google-api-python-client

A biblioteca do Google é SÍNCRONA (bloqueante). Synapse roda em cima do
Twisted (reactor de um único thread) — chamar código bloqueante direto
travaria o servidor inteiro enquanto espera a resposta do Google. Por isso
cada chamada é despachada para uma thread separada via
twisted.internet.threads.deferToThread (o jeito nativo do Twisted de fazer
isso — asyncio.get_event_loop().run_in_executor não é confiável nesse
ambiente, porque o Synapse roda sobre o reactor do Twisted, não o loop
padrão do asyncio: dá "RuntimeError: await wasn't used with future").
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class YoutubeBroadcastInfo:
    """O que o front precisa depois de criar uma transmissão."""
    broadcast_id: str          # id do vídeo/transmissão no YouTube
    watch_url: str             # url para embutir/assistir (ex: https://youtube.com/watch?v=...)
    ingestion_address: str     # servidor RTMP para configurar no OBS
    stream_key: str            # chave de transmissão para configurar no OBS


class YoutubeClient(ABC):
    """Interface comum entre o client real e o mock."""

    @abstractmethod
    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        ...


class YoutubeNotConfiguredError(Exception):
    """
    Levantada quando não há como falar com o YouTube: nem credenciais
    completas, nem o mock foi pedido explicitamente. O service converte
    isso em HTTP 503.
    """


class UnconfiguredYoutubeClient(YoutubeClient):
    """
    Usado quando a config do módulo está incompleta/errada e o mock NÃO foi
    pedido explicitamente (youtube_use_mock). Falha alto em vez de devolver
    uma chave falsa que parece real.
    """

    def __init__(self, reason: str):
        self.reason = reason

    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        raise YoutubeNotConfiguredError(self.reason)


class MockYoutubeClient(YoutubeClient):
    """
    Implementação falsa, usada enquanto não temos credenciais OAuth do
    canal do YouTube da empresa. Gera valores plausíveis, mas que não
    funcionam de verdade (não é possível transmitir para eles).
    """

    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        fake_id = uuid.uuid4().hex[:11]  # video ids do youtube tem 11 chars
        logger.warning(
            "MockYoutubeClient: create_broadcast is FAKE (no real OAuth "
            "credentials configured yet). title=%s fake_id=%s",
            title,
            fake_id,
        )
        return YoutubeBroadcastInfo(
            broadcast_id=fake_id,
            watch_url=f"https://www.youtube.com/watch?v={fake_id}",
            ingestion_address="rtmp://a.rtmp.youtube.com/live2",
            stream_key=f"mock-{uuid.uuid4().hex}",
        )


class RealYoutubeClient(YoutubeClient):
    """
    Implementação real, usando a YouTube Data API / Live Streaming API.

    O fluxo para criar uma transmissão ao vivo tem 3 passos:
    1. liveBroadcasts().insert — cria o "evento" de transmissão (o vídeo,
       com título, privacidade, horário).
    2. liveStreams().insert — cria o "cano" de ingestão: aqui é onde o
       YouTube gera o servidor RTMP + a stream key que vão para o OBS.
    3. liveBroadcasts().bind — liga o broadcast (passo 1) ao stream
       (passo 2), para que o vídeo do passo 1 efetivamente receba o que
       chegar pelo cano do passo 2.
    """

    # escopo mínimo necessário para gerenciar transmissões ao vivo
    SCOPES = ["https://www.googleapis.com/auth/youtube"]

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._youtube = None  # criado sob demanda (é objeto síncrono)

    def _get_client(self):
        """
        Monta o client síncrono do google-api-python-client, autenticado
        via refresh_token (não precisa de login interativo — o refresh
        token já foi obtido uma vez, manualmente, autorizando o canal).
        """
        if self._youtube is not None:
            return self._youtube

        # imports aqui dentro (não no topo do arquivo) para não exigir as
        # libs do Google instaladas quando só o MockYoutubeClient é usado
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=None,  # será renovado automaticamente a partir do refresh_token
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES,
        )

        self._youtube = build("youtube", "v3", credentials=credentials)
        return self._youtube

    def _create_broadcast_sync(self, title: str) -> YoutubeBroadcastInfo:
        """
        A parte síncrona/bloqueante de verdade — roda dentro de uma thread
        (ver create_broadcast, que despacha esta função via deferToThread).
        """
        youtube = self._get_client()

        # scheduledStartTime é obrigatório para o YouTube, mesmo quando a
        # transmissão vai começar imediatamente (a API não aceita "agora"
        # implícito — precisa de um timestamp ISO 8601 em UTC).
        scheduled_start_time = (
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        )

        # 1. cria o "evento" de transmissão
        broadcast_response = youtube.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body={
                "snippet": {
                    "title": title,
                    "scheduledStartTime": scheduled_start_time,
                },
                "status": {
                    # "unlisted": não aparece em busca pública, mas quem tem
                    # o link assiste. Ajustar para "public" ou "private"
                    # conforme a decisão de produto sobre visibilidade.
                    "privacyStatus": "unlisted",
                },
                "contentDetails": {
                    "enableAutoStart": True,
                    "enableAutoStop": True,
                },
            },
        ).execute()

        broadcast_id = broadcast_response["id"]

        # 2. cria o "cano" de ingestão (gera servidor + stream key)
        stream_response = youtube.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": f"{title} (stream)",
                },
                "cdn": {
                    "frameRate": "variable",
                    "ingestionType": "rtmp",
                    "resolution": "variable",
                },
            },
        ).execute()

        stream_id = stream_response["id"]
        ingestion_info = stream_response["cdn"]["ingestionInfo"]

        # 3. liga o broadcast ao stream
        youtube.liveBroadcasts().bind(
            id=broadcast_id,
            part="id,contentDetails",
            streamId=stream_id,
        ).execute()

        return YoutubeBroadcastInfo(
            broadcast_id=broadcast_id,
            watch_url=f"https://www.youtube.com/watch?v={broadcast_id}",
            ingestion_address=ingestion_info["ingestionAddress"],
            stream_key=ingestion_info["streamName"],
        )

    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        logger.info("RealYoutubeClient: creating broadcast title=%s", title)

        # Synapse roda sobre o reactor do Twisted, não o event loop puro do
        # asyncio — run_in_executor não é confiável nesse ambiente ("await
        # wasn't used with future"). deferToThread é o jeito nativo do
        # Twisted de rodar código bloqueante numa thread; o Synapse sabe
        # dar await num Deferred normalmente.
        from twisted.internet.threads import deferToThread

        try:
            info = await deferToThread(self._create_broadcast_sync, title)
        except Exception:
            logger.exception("RealYoutubeClient: failed to create broadcast title=%s", title)
            raise

        logger.info(
            "RealYoutubeClient: broadcast created id=%s",
            info.broadcast_id,
        )
        return info