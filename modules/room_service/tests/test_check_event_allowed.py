import pytest
from unittest.mock import Mock

from synapse.api.errors import SynapseError
from room_service.module import RoomServiceModule


@pytest.fixture
def module():
    api = Mock()
    config = {
        "admin_user_id": "@admin:test",
        "admin_token": "token",
        "homeserver": "http://localhost",
    }

    return RoomServiceModule(config=config, api=api)


# ---------------- CHECK EVENT ALLOWED ----------------

@pytest.mark.asyncio
async def test_block_space_creation(module):
    """
    Should reject creation of spaces (m.space).
    """
    event = Mock()
    event.type = "m.room.create"
    event.content = {"type": "m.space"}

    with pytest.raises(SynapseError) as err:
        await module.check_event_allowed(event, state_events={})

    assert err.value.code == 403


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