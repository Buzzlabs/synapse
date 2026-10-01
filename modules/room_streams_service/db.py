def get_stream(txn, room_id):
    txn.execute(
        """
        SELECT playback_url, provider, youtube_broadcast_id, youtube_watch_url
        FROM room_streams WHERE room_id = ?
        """,
        (room_id,),
    )
    row = txn.fetchone()
    if row is None:
        return None
    return {
        "room_id": room_id,
        "playback_url": row[0],
        "provider": row[1],
        "youtube_broadcast_id": row[2],
        "youtube_watch_url": row[3],
    }


def set_stream(txn, room_id, playback_url, provider="fixed"):
    txn.execute(
        """
        INSERT INTO room_streams
            (room_id, playback_url, provider, youtube_broadcast_id, youtube_watch_url,
             created_at, updated_at)
        VALUES (?, ?, ?, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (room_id) DO UPDATE SET
            playback_url = excluded.playback_url,
            provider = excluded.provider,
            youtube_broadcast_id = NULL,
            youtube_watch_url = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (room_id, playback_url, provider),
    )


def set_youtube_broadcast(txn, room_id, broadcast_id, watch_url):
    """Grava o broadcast do YouTube recém-criado na sala (já validada como
    existente e provider='youtube' pelo service antes de chamar isto)."""
    txn.execute(
        """
        UPDATE room_streams
        SET youtube_broadcast_id = ?, youtube_watch_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE room_id = ?
        """,
        (broadcast_id, watch_url, room_id),
    )

def clear_youtube_broadcast(txn, room_id):
    """Chamado ao encerrar uma live: zera os campos sem mexer em
    playback_url/provider (diferente de set_stream, que muda a config)."""
    txn.execute(
        """
        UPDATE room_streams
        SET youtube_broadcast_id = NULL, youtube_watch_url = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE room_id = ?
        """,
        (room_id,),
    )
