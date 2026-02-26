import time
import uuid


# ---------------- CREATE BUNDLE ----------------

def create_bundle(txn, bundle_name: str, price: float):
    bundle_id = str(uuid.uuid4())
    now = int(time.time() * 1000)

    txn.execute(
        """
        INSERT INTO bundles
        (bundle_id, bundle_name, price, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            bundle_id,
            bundle_name,
            price,
            now,
            now,
        ),
    )

    return bundle_id


# ---------------- LIST BUNDLES ----------------

def list_bundles(txn):
    txn.execute(
        """
        SELECT b.bundle_id, b.bundle_name, b.price, br.room_id
        FROM bundles b
        LEFT JOIN bundle_rooms br
            ON b.bundle_id = br.bundle_id
        ORDER BY b.bundle_name
        """
    )

    rows = txn.fetchall()
    result = {}

    for bundle_id, name, price, room_id in rows:
        if bundle_id not in result:
            result[bundle_id] = {
                "bundle_id": bundle_id,
                "bundle_name": name,
                "price": float(price),
                "rooms": [],
            }

        if room_id:
            result[bundle_id]["rooms"].append(room_id)

    return list(result.values())


# ---------------- ADD ROOMS ----------------

def add_rooms_to_bundle(txn, bundle_id: str, room_ids: list):
    for room_id in room_ids:
        txn.execute(
            """
            INSERT INTO bundle_rooms (bundle_id, room_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (bundle_id, room_id),
        )


# ---------------- UPDATE ----------------

def update_bundle(txn, bundle_id: str, bundle_name: str, price: float):
    now = int(time.time() * 1000)

    txn.execute(
        """
        UPDATE bundles
        SET bundle_name = %s,
            price = %s,
            updated_at = %s
        WHERE bundle_id = %s
        """,
        (bundle_name, price, now, bundle_id),
    )


# ---------------- DELETE ----------------

def delete_bundle(txn, bundle_id: str):
    txn.execute(
        """
        DELETE FROM bundles
        WHERE bundle_id = %s
        """,
        (bundle_id,),
    )


# ---------------- GET ROOMS ----------------

def get_rooms_by_bundle(txn, bundle_id: str):
    txn.execute(
        """
        SELECT room_id
        FROM bundle_rooms
        WHERE bundle_id = %s
        """,
        (bundle_id,),
    )

    rows = txn.fetchall()
    return [row[0] for row in rows]


# ---------------- EXISTS ----------------

def bundle_exists(txn, bundle_id: str) -> bool:
    txn.execute(
        """
        SELECT 1
        FROM bundles
        WHERE bundle_id = %s
        """,
        (bundle_id,),
    )

    return txn.fetchone() is not None