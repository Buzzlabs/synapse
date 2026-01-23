import time

def save_room_metadata(txn, room_id, data):
    now = int(time.time() * 1000)
    txn.execute(
        """
        INSERT INTO room_business
        (room_id, room_kind, access_type, visible, price, keyword, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            room_id,
            data["room_kind"],
            data["access_type"],
            data["visible"],
            data.get("price", 0),
            data.get("keyword"),
            now,
        ),
    )


def get_visible_rooms(txn):
    txn.execute(
        """
        SELECT room_id, room_kind, access_type, price, keyword
        FROM room_business
        WHERE visible = TRUE
          AND room_kind IN ('group', 'space')
        """
    )
    return txn.fetchall()


def resolve_keyword(txn, keyword):
    txn.execute(
        """
        SELECT room_id, room_kind, access_type
        FROM room_business
        WHERE keyword = ?
        """,
        (keyword,),
    )
    return txn.fetchone()

def update_room_visibility(txn, room_id, *, visible: bool, price: int | None):
    txn.execute(
        """
        UPDATE room_business
        SET visible = ?, price = ?
        WHERE room_id = ?
        """,
        (
            visible,
            price if price is not None else 0,
            room_id,
        ),
    )

def get_room_access_type(txn, room_id):
    txn.execute(
        """
        SELECT access_type, visible
        FROM room_business
        WHERE room_id = ?
        """,
        (room_id,),
    )
    return txn.fetchone()
