import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError
from modules.youtube_live_service.service import YoutubeLiveService
from modules.youtube_live_service.youtube_client import (
    MockYoutubeClient,
    UnconfiguredYoutubeClient,
)


def make_service(is_admin=True, room_streams_service=None):
    api = MagicMock()
    api.is_user_admin = AsyncMock(return_value=is_admin)
    if room_streams_service is None:
        room_streams_service = MagicMock()
        room_streams_service.require_youtube_room = AsyncMock()
        room_streams_service.set_youtube_broadcast = AsyncMock()
    return YoutubeLiveService(
        api=api,
        youtube_client=MockYoutubeClient(),
        room_streams_service=room_streams_service,
    ), room_streams_service


@pytest.mark.asyncio
async def test_start_broadcast_requires_admin():
    service, _ = make_service(is_admin=False)

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(
            user_id="@user:localhost",
            room_id="!room:localhost",
            title="Minha live",
        )

    assert exc.value.code == 403


@pytest.mark.asyncio
async def test_start_broadcast_with_mock_returns_expected_shape():
    service, _ = make_service(is_admin=True)

    result = await service.start_broadcast(
        user_id="@admin:localhost",
        room_id="!room:localhost",
        title="Minha live de teste",
    )

    assert result["room_id"] == "!room:localhost"
    assert result["watch_url"].startswith("https://www.youtube.com/watch?v=")
    assert result["ingestion_address"] == "rtmp://a.rtmp.youtube.com/live2"
    assert result["stream_key"].startswith("mock-")
    assert len(result["broadcast_id"]) == 11


@pytest.mark.asyncio
async def test_start_broadcast_missing_room_id():
    service, _ = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(user_id="@admin:localhost", room_id=None, title="x")

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_start_broadcast_missing_title():
    service, _ = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(user_id="@admin:localhost", room_id="!r:localhost", title="   ")

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_start_broadcast_returns_503_when_integration_not_configured():
    """
    Antes, o except NotImplementedError do service era inalcançável (nada
    lançava essa exceção) e config incompleta virava mock com HTTP 200.
    """
    room_streams_service = MagicMock()
    room_streams_service.require_youtube_room = AsyncMock()
    api = MagicMock()
    api.is_user_admin = AsyncMock(return_value=True)
    service = YoutubeLiveService(
        api=api,
        youtube_client=UnconfiguredYoutubeClient("missing or unreadable config: youtube_client_id"),
        room_streams_service=room_streams_service,
    )

    with pytest.raises(SynapseError) as exc:
        await service.start_broadcast(
            user_id="@admin:localhost",
            room_id="!room:localhost",
            title="Minha live",
        )

    assert exc.value.code == 503
    assert "not configured" in exc.value.msg


class TestRoomValidationAndPersistence:
    """
    Regressão do review: start_broadcast não validava a sala nem persistia
    broadcast_id/watch_url em room_streams. Sem isso, a live nunca ficava
    associada à sala do lado do servidor (get_stream continuava devolvendo
    playback_url: null mesmo com uma live rolando).
    """

    @pytest.mark.asyncio
    async def test_room_not_configured_propagates_404_before_calling_google(self):
        room_streams_service = MagicMock()
        room_streams_service.require_youtube_room = AsyncMock(
            side_effect=SynapseError(404, "Room has no stream configuration; configure it first")
        )
        service, _ = make_service(is_admin=True, room_streams_service=room_streams_service)

        with pytest.raises(SynapseError) as exc:
            await service.start_broadcast(
                user_id="@admin:localhost", room_id="!room:localhost", title="Minha live"
            )

        assert exc.value.code == 404

    @pytest.mark.asyncio
    async def test_wrong_provider_propagates_400_before_calling_google(self):
        room_streams_service = MagicMock()
        room_streams_service.require_youtube_room = AsyncMock(
            side_effect=SynapseError(400, "room is configured with provider='fixed', not 'youtube'")
        )
        service, _ = make_service(is_admin=True, room_streams_service=room_streams_service)

        with pytest.raises(SynapseError) as exc:
            await service.start_broadcast(
                user_id="@admin:localhost", room_id="!room:localhost", title="Minha live"
            )

        assert exc.value.code == 400

    @pytest.mark.asyncio
    async def test_room_validated_before_creating_broadcast(self):
        """A ordem importa: validar a sala é barato, criar o broadcast não."""
        room_streams_service = MagicMock()
        room_streams_service.require_youtube_room = AsyncMock(
            side_effect=SynapseError(404, "not configured")
        )
        service, _ = make_service(is_admin=True, room_streams_service=room_streams_service)
        service.youtube_client = MagicMock()
        service.youtube_client.create_broadcast = AsyncMock()

        with pytest.raises(SynapseError):
            await service.start_broadcast(
                user_id="@admin:localhost", room_id="!room:localhost", title="Minha live"
            )

        service.youtube_client.create_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_persists_broadcast_id_and_watch_url(self):
        service, room_streams_service = make_service(is_admin=True)

        result = await service.start_broadcast(
            user_id="@admin:localhost", room_id="!room:localhost", title="Minha live"
        )

        room_streams_service.set_youtube_broadcast.assert_awaited_once_with(
            "!room:localhost", result["broadcast_id"], result["watch_url"]
        )

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_fail_the_request(self):
        """
        O broadcast já existe no YouTube nesse ponto; se falhar ao salvar,
        o admin ainda precisa da stream key para poder transmitir agora.
        """
        room_streams_service = MagicMock()
        room_streams_service.require_youtube_room = AsyncMock()
        room_streams_service.set_youtube_broadcast = AsyncMock(side_effect=RuntimeError("db down"))
        service, _ = make_service(is_admin=True, room_streams_service=room_streams_service)

        result = await service.start_broadcast(
            user_id="@admin:localhost", room_id="!room:localhost", title="Minha live"
        )

        assert result["watch_url"].startswith("https://www.youtube.com/watch?v=")