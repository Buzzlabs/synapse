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


def get_room_by_keyword(txn, keyword: str):
    txn.execute(
        """
        SELECT room_id
        FROM room_business
        WHERE keyword = ? AND visible = TRUE
        """,
        (keyword,),
    )
    return txn.fetchone()


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
