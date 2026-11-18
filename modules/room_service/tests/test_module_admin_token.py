from unittest.mock import MagicMock

from modules.room_service import module as room_module
from modules.room_service.module import RoomServiceModule


def test_admin_token_is_awaited_for_30_seconds(monkeypatch):
    calls = []

    def fake_read(path, *, wait_seconds=0):
        calls.append((path, wait_seconds))
        return "tok"

    monkeypatch.setattr(room_module, "read_secret_file", fake_read)
    config = {
        "admin_user_id": "@admin:test",
        "admin_token_file": "/secrets/admin",
        "homeserver": "http://synapse",
    }
    api = MagicMock()
    RoomServiceModule(config, api)

    assert calls == [("/secrets/admin", 30)]
    assert api._hs.room_service.admin_token == "tok"
