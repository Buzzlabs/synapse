# service.py

import uuid

from synapse.api.errors import SynapseError

from . import db
import logging

logger = logging.getLogger(__name__)

class BundleService:
    def __init__(self, api):
        self.api = api
        self.store = api._hs.get_datastores().main

    # ---------------- LIST BUNDLES ----------------
    async def list_bundles(self, user_id):
        logger.info("list_bundles: start for user %s", user_id)

        try:
            bundles = await self.store.db_pool.runInteraction(
                "list_bundles",
                db.list_bundles,
            )
        except Exception:
            logger.exception("list_bundles: DB error")
            raise

        logger.info("list_bundles: %d bundles found in DB", len(bundles))

        try:
            is_admin = await self._is_admin(user_id)
            logger.info("list_bundles: user %s admin=%s", user_id, is_admin)
        except Exception:
            logger.exception("list_bundles: failed to check admin status")
            is_admin = False

        result = []

        for bundle in bundles:

            if bundle["status"] == "draft":
                if bundle["created_by"] != user_id and not is_admin:
                    logger.info(
                        "list_bundles: skipping draft %s (not owner/admin)",
                        bundle["bundle_id"],
                    )
                    continue

            room_ids = bundle.get("rooms", [])

            try:
                room_business_rows = await self.store.db_pool.runInteraction(
                    "get_room_business_by_ids",
                    db.get_room_business_by_ids,
                    room_ids,
                )
            except Exception:
                logger.exception(
                    "list_bundles: failed to fetch room business for bundle %s",
                    bundle["bundle_id"],
                )
                room_business_rows = []

            room_keywords = {row[0]: row[1] for row in room_business_rows}

            rooms = []
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
                    logger.warning(
                        "list_bundles: failed to fetch name for room %s",
                        room_id,
                    )
                    name = "Sem nome"

                # guarda room_id + name
                rooms.append({
                    "room_id": room_id,
                    "name": name
                })

                if room_id in room_keywords:
                    keywords.append(room_keywords[room_id])

            result.append({
                "bundle_id": bundle["bundle_id"],
                "bundle_name": bundle["bundle_name"],
                "price": bundle["price"],
                "rooms": rooms,
                "keywords": keywords,
                "status": bundle["status"],
            })

        logger.info("list_bundles: finished, %d bundles returned", len(result))

        return result


    async def _is_admin(self, user_id: str) -> bool:
        try:
            return await self.api.is_user_admin(user_id)
        except Exception:
            logger.exception("_is_admin: error checking admin for %s", user_id)
            return False
    

    # ---------------- CREATE BUNDLES ----------------
    async def create_bundle(self, bundle_name, price, created_by, rooms):
        logger.info(
            "create_bundle: start | name=%s | price=%s | created_by=%s | rooms_count=%d",
            bundle_name,
            price,
            created_by,
            len(rooms) if rooms else 0,
        )

        try:
            bundle_id = await self.store.db_pool.runInteraction(
                "create_bundle",
                db.create_bundle,
                bundle_name,
                price,
                created_by,
                rooms,
            )

            logger.info(
                "create_bundle: success | bundle_id=%s | created_by=%s",
                bundle_id,
                created_by,
            )

            return bundle_id

        except Exception as e:
            logger.exception(
                "create_bundle: failed | name=%s | created_by=%s",
                bundle_name,
                created_by,
            )
            raise
        
    # ---------------- PUBLISH BUNDLES ----------------
    async def publish_bundle(self, bundle_id: str, user_id: str):
        logger.info("Publishing bundle %s", bundle_id)

        is_admin = await self._is_admin(user_id)

        if not is_admin:
            logger.warning(
                "publish_bundle: permission denied | user=%s | bundle_id=%s",
                user_id,
                bundle_id,
            )
            raise SynapseError(403, "Only admins can publish bundles")


        exists = await self.store.db_pool.runInteraction(
            "bundle_exists",
            db.bundle_exists,
            bundle_id,
        )

        if not exists:
            raise SynapseError(404, "Bundle not found")

        await self.store.db_pool.runInteraction(
            "publish_bundle",
            db.publish_bundle,
            bundle_id,
        )

        return {"status": "published"}

    # ---------------- DELETE BUNDLE ----------------
    async def delete_bundle(self, bundle_id: str, user_id: str):
        logger.info("delete_bundle: start | bundle_id=%s | user=%s", bundle_id, user_id)

        is_admin = await self._is_admin(user_id)

        if not is_admin:
            logger.warning(
                "delete_bundle: permission denied | user=%s | bundle_id=%s",
                user_id,
                bundle_id,
            )
            raise SynapseError(403, "Only admins can delete bundles")

        exists = await self.store.db_pool.runInteraction(
            "bundle_exists",
            db.bundle_exists,
            bundle_id,
        )

        if not exists:
            logger.warning(
                "delete_bundle: bundle not found | bundle_id=%s",
                bundle_id,
            )
            raise SynapseError(404, "Bundle not found")

        await self.store.db_pool.runInteraction(
            "delete_bundle",
            db.delete_bundle,
            bundle_id,
        )

        logger.info(
            "delete_bundle: success | bundle_id=%s | deleted_by=%s",
            bundle_id,
            user_id,
        )

        return {"status": "deleted"}