# service.py
from . import db
import logging

logger = logging.getLogger(__name__)

class BundleService:
    def __init__(self, api):
        self.api = api
        self.store = api._hs.get_datastores().main

  # ---------------- LIST BUNDLES ----------------
    async def list_bundles(self):
        bundles = await self.store.db_pool.runInteraction(
            "list_bundles",
            db.list_bundles,
        )

        result = []

        for bundle in bundles:
            room_ids = bundle["rooms"]

            room_business_rows = await self.store.db_pool.runInteraction(
                "get_room_business_by_ids",
                db.get_room_business_by_ids,
                room_ids,
            )

            room_keywords = {row[0]: row[1] for row in room_business_rows}

            room_names = []
            keywords = []

            for room_id in room_ids:

                try:
                    state_events = await self.api.get_state_events_in_room(
                        room_id,
                        [("m.room.name", "")]
                    )

                    name = "Sem nome"
                    for ev in state_events:
                        name = ev.content.get("name", "Sem nome")
                        break

                except Exception:
                    name = "Sem nome"

                room_names.append(name)

                if room_id in room_keywords:
                    keywords.append(room_keywords[room_id])

            result.append({
                "bundle_id": bundle["bundle_id"],
                "bundle_name": bundle["bundle_name"],
                "price": bundle["price"],
                "rooms": room_names,
                "keywords": keywords,
            })

        return result