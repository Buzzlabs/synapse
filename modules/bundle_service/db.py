import uuid


# ---------------- CREATE BUNDLE ----------------

def create_bundle(txn, bundle_name: str, price: int, created_by: str, rooms: list):
    bundle_id = str(uuid.uuid4())

    txn.execute(
        """
        INSERT INTO bundles
        (bundle_id, bundle_name, price, created_by, status)
        VALUES (%s, %s, %s, %s, 'draft')
        """,
        (
            bundle_id,
            bundle_name,
            price,
            created_by,
        ),
    )

    # inserir salas se existirem
    for room_id in rooms:
        txn.execute(
            """
            INSERT INTO bundle_rooms (bundle_id, room_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (bundle_id, room_id),
        )

    return bundle_id


# ---------------- LIST BUNDLES ----------------

def list_bundles(txn):
    txn.execute(
        """
        SELECT 
            b.bundle_id, 
            b.bundle_name, 
            b.price,
            b.status,
            b.created_by,
            br.room_id
        FROM bundles b
        LEFT JOIN bundle_rooms br
            ON b.bundle_id = br.bundle_id
        ORDER BY b.bundle_name
        """
    )

    rows = txn.fetchall()
    result = {}

    for bundle_id, name, price, status, created_by, room_id in rows:
        if bundle_id not in result:
            result[bundle_id] = {
                "bundle_id": bundle_id,
                "bundle_name": name,
                "price": int(price),
                "status": status,
                "created_by": created_by,
                "rooms": [],
            }

        if room_id:
            result[bundle_id]["rooms"].append(room_id)

    return list(result.values())

# ---------------- PUBLISH ----------------

def publish_bundle(txn, bundle_id: str):
    txn.execute(
        """
        UPDATE bundles
        SET status = 'published',
            updated_at = now()
        WHERE bundle_id = %s
        """,
        (bundle_id,),
    )
    
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

def get_bundle_by_id(txn, bundle_id):
    txn.execute(
        """
        SELECT bundle_id, created_by
        FROM bundles
        WHERE bundle_id = ?
        """,
        (bundle_id,),
    )

    columns = [col[0] for col in txn.description]

    return [
        dict(zip(columns, row))
        for row in txn.fetchall()
    ]

def update_bundle(txn, bundle_id, bundle_name, price, rooms):

    txn.execute(
        """
        UPDATE bundles
        SET bundle_name = ?, price = ?, updated_at = CURRENT_TIMESTAMP
        WHERE bundle_id = ?
        """,
        (bundle_name, price, bundle_id),
    )

    txn.execute(
        """
        DELETE FROM bundle_rooms
        WHERE bundle_id = ?
        """,
        (bundle_id,),
    )

    for room_id in rooms:
        txn.execute(
            """
            INSERT INTO bundle_rooms (bundle_id, room_id)
            VALUES (?, ?)
            """,
            (bundle_id, room_id),
        )

# ---------------- DELETE ----------------

def delete_bundle(txn, bundle_id: str):
    txn.execute(
        """
        DELETE FROM bundle_rooms
        WHERE bundle_id = %s
        """,
        (bundle_id,),
    )

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


# ------------- GET KEYWORD ----------------

def get_room_business_by_ids(txn, room_ids):
    if not room_ids:
        return []

    sql = """
        SELECT room_id, keyword
        FROM room_business
        WHERE room_id = ANY(%s)
    """

    txn.execute(sql, (room_ids,))
    return txn.fetchall()