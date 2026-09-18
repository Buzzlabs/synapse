def get_stream(txn, room_id: str):
    txn.execute(
        """
        SELECT playback_url, provider
        FROM room_streams
        WHERE room_id = ?
        """,
        (room_id,),
    )
    row = txn.fetchone()
    if row is None:
        return None
    return {"room_id": room_id, "playback_url": row[0], "provider": row[1]}
 
def set_stream(txn, room_id: str, playback_url: str, provider: str = "fixed"):
    txn.execute(
        """
        INSERT INTO room_streams (room_id, playback_url, provider, created_at, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (room_id) DO UPDATE SET
            playback_url = excluded.playback_url,
            provider = excluded.provider,
            updated_at = CURRENT_TIMESTAMP
        """,
        (room_id, playback_url, provider),
    )
 
def delete_stream(txn, room_id: str):
    txn.execute(
        """
        DELETE FROM room_streams
        WHERE room_id = ?
        """,
        (room_id,),
    )