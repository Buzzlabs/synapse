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

def keyword_exists(txn, keyword: str) -> bool:
    txn.execute(
        """
        SELECT 1
        FROM room_business
        WHERE keyword = ?
        """,
        (keyword,),
    )
    return txn.fetchone() is not None

def get_room_access_type(txn, room_id: str):
    txn.execute(
        """
        SELECT access_type
        FROM room_business
        WHERE room_id = ?
        """,
        (room_id,),
    )
    row = txn.fetchone()
    return row[0] if row else None

def get_room_visibility(txn, room_id: str):
    txn.execute(
        """
        SELECT visible, price, access_type
        FROM room_business
        WHERE room_id = ?
        """,
        (room_id,),
    )
    return txn.fetchone()

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

def update_room_visibility(txn, room_id: str, visible: bool, price: int):
    txn.execute(
        """
        UPDATE room_business
        SET visible = ?, price = ?
        WHERE room_id = ?
        """,
        (visible, price, room_id),
    )


def get_room_price_info(txn, room_id):
    txn.execute(
        """
        SELECT visible, access_type, price
        FROM room_business
        WHERE room_id = ?
        """,
        (room_id,),
    )
    return txn.fetchone()


def update_room_price(txn, room_id, price: int):
    txn.execute(
        """
        UPDATE room_business
        SET price = ?
        WHERE room_id = ?
        """,
        (price, room_id),
    )
