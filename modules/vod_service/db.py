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


def insert_vod(
    txn,
    stream_id: str,
    room_id: str,
    title,
    recording_path: str,
    recording_duration_ms,
    started_at,
    ended_at,
    created_at: int,
    updated_at: int,
):
    """
    Insere um novo VOD (gravacao finalizada) e devolve a linha criada
    no mesmo formato que os SELECTs, para o service serializar.
    """
    txn.execute(
        """
        INSERT INTO streams (
            stream_id, room_id, title, recording_path,
            recording_duration_ms, started_at, ended_at,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id, stream_id, room_id, title, category_id,
                  recording_path, recording_duration_ms,
                  started_at, ended_at
        """,
        (
            stream_id,
            room_id,
            title,
            recording_path,
            recording_duration_ms,
            started_at,
            ended_at,
            created_at,
            updated_at,
        ),
    )
    return txn.fetchone()