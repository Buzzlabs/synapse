def get_calendar(txn, room_id: str):
    txn.execute(
        """
        SELECT calendar_id
        FROM room_calendars
        WHERE room_id = ?
        """,
        (room_id,),
    )
    return txn.fetchone()


def set_calendar(txn, room_id: str, calendar_id: str, now_ms: int):
    """
    Upsert: define qual Google Calendar a sala usa.
    """
    txn.execute(
        """
        INSERT INTO room_calendars (room_id, calendar_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (room_id)
        DO UPDATE SET calendar_id = EXCLUDED.calendar_id,
                      updated_at = EXCLUDED.updated_at
        """,
        (room_id, calendar_id, now_ms, now_ms),
    )


def delete_calendar(txn, room_id: str):
    txn.execute(
        """
        DELETE FROM room_calendars
        WHERE room_id = ?
        """,
        (room_id,),
    )