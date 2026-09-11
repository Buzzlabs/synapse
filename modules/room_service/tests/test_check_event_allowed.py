import pytest
from unittest.mock import Mock

from synapse.api.errors import SynapseError
from room_service.module import RoomServiceModule


@pytest.fixture
def module(tmp_path):
    api = Mock()
    # o module.py le admin_token_file, entao criamos um arquivo temporario
    token_file = tmp_path / "admin_token.txt"
    token_file.write_text("token")
    config = {
        "admin_user_id": "@admin:test",
        "admin_token_file": str(token_file),
        "homeserver": "http://localhost",
    }

    return RoomServiceModule(config=config, api=api)


# ---------------- CHECK EVENT ALLOWED ----------------

@pytest.mark.asyncio
async def test_allow_space_creation(module):
    """
    Spaces are now allowed (previously blocked with 403).
    """
    event = Mock()
    event.type = "m.room.create"
    event.content = {"type": "m.space"}

    allowed, _ = await module.check_event_allowed(event, state_events={})

    assert allowed is True


@pytest.mark.asyncio
async def test_allow_normal_room_creation(module):
    """
    Should allow normal room creation.
    """
    event = Mock()
    event.type = "m.room.create"
    event.content = {"type": "m.room"}

    allowed, _ = await module.check_event_allowed(event, state_events={})

    assert allowed is True


@pytest.mark.asyncio
async def test_allow_other_event_types(module):
    """
    Should allow events that are not room creation.
    """
    event = Mock()
    event.type = "m.room.message"
    event.content = {}

    allowed, _ = await module.check_event_allowed(event, state_events={})

    assert allowed is True