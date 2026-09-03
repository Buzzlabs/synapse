
def get_stream(txn, room_id: str):
    txn.execute(
        """
        SELECT playback_url
        FROM room_streams
        WHERE room_id = ?
        """,
        (room_id,),
    )
    row = txn.fetchone()
    if row is None:
        return None
    return {"room_id": room_id, "playback_url": row[0]}


def set_stream(txn, room_id: str, playback_url: str):
    txn.execute(
        """
        INSERT INTO room_streams (room_id, playback_url, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (room_id) DO UPDATE SET
            playback_url = excluded.playback_url,
            updated_at = CURRENT_TIMESTAMP
        """,
        (room_id, playback_url),
    )


def delete_stream(txn, room_id: str):
    txn.execute(
        """
        DELETE FROM room_streams
        WHERE room_id = ?
        """,
        (room_id,),
    )
