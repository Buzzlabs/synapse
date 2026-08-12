def get_feature(txn, room_id: str, feature: str):
    txn.execute(
        """
        SELECT enabled
        FROM room_features
        WHERE room_id = ? AND feature = ?
        """,
        (room_id, feature),
    )
    return txn.fetchone()


def list_features(txn, room_id: str):
    txn.execute(
        """
        SELECT feature, enabled
        FROM room_features
        WHERE room_id = ?
        """,
        (room_id,),
    )
    return txn.fetchall()


def set_feature(txn, room_id: str, feature: str, enabled: bool, now_ms: int):
    """
    Upsert: liga/desliga a feature da sala. Cria a linha se nao existir.
    """
    txn.execute(
        """
        INSERT INTO room_features (room_id, feature, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (room_id, feature)
        DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = EXCLUDED.updated_at
        """,
        (room_id, feature, enabled, now_ms, now_ms),
    )