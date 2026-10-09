import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class YoutubeBroadcastInfo:
    broadcast_id: str
    watch_url: str
    ingestion_address: str
    stream_key: str


class YoutubeClient(ABC):
    @abstractmethod
    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        ...

    @abstractmethod
    async def end_broadcast(self, broadcast_id: str) -> None:
        ...


class YoutubeNotConfiguredError(Exception):
    pass


class UnconfiguredYoutubeClient(YoutubeClient):
    def __init__(self, reason: str):
        self.reason = reason

    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        raise YoutubeNotConfiguredError(self.reason)

    async def end_broadcast(self, broadcast_id: str) -> None:
        raise YoutubeNotConfiguredError(self.reason)


class MockYoutubeClient(YoutubeClient):
    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        fake_id = uuid.uuid4().hex[:11]
        logger.warning(
            "MockYoutubeClient: create_broadcast is FAKE. title=%s fake_id=%s", title, fake_id
        )
        return YoutubeBroadcastInfo(
            broadcast_id=fake_id,
            watch_url=f"https://www.youtube.com/watch?v={fake_id}",
            ingestion_address="rtmp://a.rtmp.youtube.com/live2",
            stream_key=f"mock-{uuid.uuid4().hex}",
        )

    async def end_broadcast(self, broadcast_id: str) -> None:
        logger.warning("MockYoutubeClient: end_broadcast is FAKE. broadcast_id=%s", broadcast_id)


class RealYoutubeClient(YoutubeClient):
    SCOPES = ["https://www.googleapis.com/auth/youtube"]

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, *, api):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.api = api

    def _build_client(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES,
        )
        return build("youtube", "v3", credentials=credentials)

    def _create_broadcast_sync(self, title: str) -> YoutubeBroadcastInfo:
        youtube = self._build_client()

        scheduled_start_time = (
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        )

        broadcast_response = youtube.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body={
                "snippet": {"title": title, "scheduledStartTime": scheduled_start_time},
                "status": {"privacyStatus": "unlisted"},
                "contentDetails": {"enableAutoStart": True, "enableAutoStop": True},
            },
        ).execute()

        broadcast_id = broadcast_response["id"]

        stream_response = youtube.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {"title": f"{title} (stream)"},
                "cdn": {"frameRate": "variable", "ingestionType": "rtmp", "resolution": "variable"},
            },
        ).execute()

        stream_id = stream_response["id"]
        ingestion_info = stream_response["cdn"]["ingestionInfo"]

        youtube.liveBroadcasts().bind(
            id=broadcast_id, part="id,contentDetails", streamId=stream_id
        ).execute()

        return YoutubeBroadcastInfo(
            broadcast_id=broadcast_id,
            watch_url=f"https://www.youtube.com/watch?v={broadcast_id}",
            ingestion_address=ingestion_info["ingestionAddress"],
            stream_key=ingestion_info["streamName"],
        )

    @staticmethod
    def _is_already_ended_error(error) -> bool:
        """
        True se o YouTube recusou encerrar o broadcast por causa do estado em
        que ele está (reason "invalidTransition"), em vez de uma falha real.

        Confirmado contra a API real (synapse#20): 403 "Invalid transition",
        reason "invalidTransition". A documentação o define apenas como "a
        transmissão não pode passar do estado atual para o solicitado", então
        ele cobre tanto "já encerrada" (OBS fechado, YouTube Studio,
        enableAutoStop) quanto "nunca foi ao ar" (nenhum encoder conectou).
        Nos dois casos não há nada no ar e limpar o registro local é correto;
        no segundo, o broadcast permanece no canal em estado pré-live.

        Qualquer outro erro (cota, permissão, "not found"...) NÃO é tratado
        como sucesso: sobe como falha e o registro local é mantido. Corpo de
        erro ilegível também conta como falha.
        """
        try:
            content = json.loads(error.content.decode("utf-8"))
            reasons = {
                e.get("reason", "").lower()
                for e in content.get("error", {}).get("errors", [])
            }
        except Exception:
            return False

        return "invalidtransition" in reasons

    def _end_broadcast_sync(self, broadcast_id: str) -> None:
        """
        Marca o broadcast como encerrado do lado do YouTube. Sem isso,
        "Encerrar transmissão" no Element só esconde o widget -- a
        transmissão continua ativa de verdade até o encoder parar ou
        alguém encerrar manualmente no YouTube Studio.

        Se o broadcast já estiver encerrado por fora do Element (OBS
        fechado, encerrado manualmente no YouTube Studio), o YouTube recusa
        a transição -- tratamos isso como sucesso (ver
        _is_already_ended_error), não como falha.
        """
        from googleapiclient.errors import HttpError

        youtube = self._build_client()
        try:
            youtube.liveBroadcasts().transition(
                broadcastStatus="complete",
                id=broadcast_id,
                part="id,status",
            ).execute()
        except HttpError as e:
            if self._is_already_ended_error(e):
                logger.info(
                    "RealYoutubeClient: broadcast id=%s was already ended outside Element, treating as success",
                    broadcast_id,
                )
                return
            raise

    async def create_broadcast(self, title: str) -> YoutubeBroadcastInfo:
        logger.info("RealYoutubeClient: creating broadcast title=%s", title)
        try:
            info = await self.api.defer_to_thread(self._create_broadcast_sync, title)
        except Exception:
            logger.exception("RealYoutubeClient: failed to create broadcast title=%s", title)
            raise
        logger.info("RealYoutubeClient: broadcast created id=%s", info.broadcast_id)
        return info

    async def end_broadcast(self, broadcast_id: str) -> None:
        logger.info("RealYoutubeClient: ending broadcast id=%s", broadcast_id)
        try:
            await self.api.defer_to_thread(self._end_broadcast_sync, broadcast_id)
        except Exception:
            logger.exception("RealYoutubeClient: failed to end broadcast id=%s", broadcast_id)
            raise
        logger.info("RealYoutubeClient: broadcast ended id=%s", broadcast_id)