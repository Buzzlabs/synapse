def get_vods(txn, channel_id: int, limit: int, offset: int):
    txn.execute(
        """
        SELECT id, stream_id, channel_id, title, category_id,
               recording_path, recording_duration_ms,
               started_at, ended_at
        FROM streams
        WHERE channel_id = ?
          AND ended_at IS NOT NULL
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
        """,
        (channel_id, limit, offset),
    )
    return txn.fetchall()


def count_vods(txn, channel_id: int):
    txn.execute(
        """
        SELECT COUNT(*)
        FROM streams
        WHERE channel_id = ?
          AND ended_at IS NOT NULL
        """,
        (channel_id,),
    )
    row = txn.fetchone()
    return row[0] if row else 0


def get_vod_by_id(txn, stream_id: int):
    txn.execute(
        """
        SELECT id, stream_id, channel_id, title, category_id,
               recording_path, recording_duration_ms,
               started_at, ended_at
        FROM streams
        WHERE id = ?
        """,
        (stream_id,),
    )
    return txn.fetchone()
