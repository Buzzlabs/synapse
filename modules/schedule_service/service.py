# service.py
import logging
import time
from urllib.parse import quote
from datetime import datetime, timezone

from synapse.module_api import ModuleApi
from synapse.api.errors import SynapseError

from . import db

logger = logging.getLogger(__name__)

GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3/calendars"


class ScheduleService:
    """
    Eventos por sala via Google Calendar.

    Cada sala aponta para um calendar_id (tabela room_calendars). O front pede
    os eventos de uma sala; o modulo busca no Google server-side (a API key
    fica no homeserver.yaml e nunca vai para o front) e devolve o resultado.

    Leitura de eventos: qualquer um pode consultar.
    Configurar o calendar da sala: apenas admin global.
    """

    def __init__(
        self,
        api: ModuleApi,
        google_api_key: str,
        timezone_name: str = "America/Sao_Paulo",
    ):
        self.api = api
        self.hs = api._hs
        self.google_api_key = google_api_key
        self.timezone_name = timezone_name

        self.store = self.hs.get_datastores().main
        # cliente HTTP do proprio Synapse (nao usamos requests/fetch)
        self.http_client = self.hs.get_proxied_http_client()

    # ---------------- ADMIN ----------------
    async def assert_is_admin(self, user_id: str) -> None:
        is_admin = await self.api.is_user_admin(user_id)
        if not is_admin:
            raise SynapseError(403, "Only Synapse admins can perform this action")

    # ---------------- CALENDAR CONFIG ----------------
    async def get_calendar(self, room_id: str) -> dict:
        if not room_id:
            raise SynapseError(400, "room_id is required")

        row = await self.store.db_pool.runInteraction(
            "get_room_calendar",
            db.get_calendar,
            room_id,
        )

        return {
            "roomId": room_id,
            "calendarId": row[0] if row else None,
        }

    async def set_calendar(self, *, requester, room_id: str, calendar_id: str) -> dict:
        user_id = requester.user.to_string()
        logger.info(
            "set_calendar: requester=%s room_id=%s calendar_id=%s",
            user_id,
            room_id,
            calendar_id,
        )

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if not calendar_id:
            raise SynapseError(400, "calendar_id is required")

        await self.assert_is_admin(user_id)

        now_ms = int(time.time() * 1000)
        await self.store.db_pool.runInteraction(
            "set_room_calendar",
            db.set_calendar,
            room_id,
            calendar_id,
            now_ms,
        )

        return {"roomId": room_id, "calendarId": calendar_id}

    # ---------------- EVENTS (Google) ----------------
    def _today_start_utc_iso(self) -> str:
        """
        Inicio do dia de hoje em UTC ISO. Porte do luxon startOf('day').toUTC()
        da POC, simplificado para meia-noite UTC.
        """
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.isoformat().replace("+00:00", "Z")

    async def list_events(self, room_id: str, limit: int = 6, time_min: str = None) -> dict:
        logger.info("list_events: room_id=%s limit=%s", room_id, limit)

        if not room_id:
            raise SynapseError(400, "room_id is required")
        if limit < 1 or limit > 50:
            raise SynapseError(400, "limit must be between 1 and 50")

        # descobre o calendar da sala
        row = await self.store.db_pool.runInteraction(
            "get_room_calendar",
            db.get_calendar,
            room_id,
        )
        if not row or not row[0]:
            # sala sem calendar configurado: lista vazia, nao e erro
            return {"roomId": room_id, "items": []}

        calendar_id = row[0]
        effective_time_min = time_min or self._today_start_utc_iso()

        url = (
            f"{GOOGLE_CALENDAR_API}/{quote(calendar_id, safe='')}/events"
            f"?singleEvents=true&orderBy=startTime"
            f"&timeMin={quote(effective_time_min, safe='')}"
            f"&maxResults={limit}"
            f"&key={self.google_api_key}"
        )

        try:
            data = await self.http_client.get_json(url)
        except Exception as e:
            logger.exception("list_events: falha ao chamar Google Calendar")
            raise SynapseError(502, f"Google Calendar request failed: {e}")

        # filtra cancelados e sem start, igual a POC
        items = [
            self._serialize_event(e)
            for e in (data.get("items") or [])
            if e.get("status") != "cancelled" and e.get("start")
        ]

        return {"roomId": room_id, "items": items}

    def _serialize_event(self, e: dict) -> dict:
        return {
            "id": e.get("id"),
            "status": e.get("status"),
            "summary": e.get("summary"),
            "description": e.get("description"),
            "location": e.get("location"),
            "start": e.get("start"),
            "end": e.get("end"),
            "htmlLink": e.get("htmlLink"),
        }