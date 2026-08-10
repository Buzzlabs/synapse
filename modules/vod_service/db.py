def get_vods(txn, room_id: str, limit: int, offset: int):
    txn.execute(
        """
        SELECT id, stream_id, room_id, title, category_id,
               recording_path, recording_duration_ms,
               started_at, ended_at
        FROM streams
        WHERE room_id = ?
          AND ended_at IS NOT NULL
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
        """,
        (room_id, limit, offset),
    )
    return txn.fetchall()


def count_vods(txn, room_id: str):
    txn.execute(
        """
        SELECT COUNT(*)
        FROM streams
        WHERE room_id = ?
          AND ended_at IS NOT NULL
        """,
        (room_id,),
    )
    row = txn.fetchone()
    return row[0] if row else 0


def get_vod_by_id(txn, stream_id: int):
    txn.execute(
        """
        SELECT id, stream_id, room_id, title, category_id,
               recording_path, recording_duration_ms,
               started_at, ended_at
        FROM streams
        WHERE id = ?
        """,
        (stream_id,),
    )
    return txn.fetchone()