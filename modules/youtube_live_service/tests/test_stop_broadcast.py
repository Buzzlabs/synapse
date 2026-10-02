import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.api.errors import SynapseError
from modules.youtube_live_service.service import YoutubeLiveService
from modules.youtube_live_service.youtube_client import YoutubeNotConfiguredError


def make_service(is_admin=True, stream=None):
    api = MagicMock()
    api.is_user_admin = AsyncMock(return_value=is_admin)

    room_streams_service = MagicMock()
    room_streams_service.get_stream = AsyncMock(
        return_value=stream
        if stream is not None
        else {
            "room_id": "!room:localhost",
            "provider": "youtube",
            "youtube_broadcast_id": "abc123XYZ_9",
            "youtube_watch_url": "https://www.youtube.com/watch?v=abc123XYZ_9",
        }
    )
    room_streams_service.clear_youtube_broadcast = AsyncMock()

    youtube_client = MagicMock()
    youtube_client.end_broadcast = AsyncMock()

    service = YoutubeLiveService(api=api, youtube_client=youtube_client, room_streams_service=room_streams_service)
    return service, room_streams_service, youtube_client


@pytest.mark.asyncio
async def test_requires_admin():
    service, _, _ = make_service(is_admin=False)

    with pytest.raises(SynapseError) as exc:
        await service.stop_broadcast(user_id="@user:localhost", room_id="!room:localhost")

    assert exc.value.code == 403


@pytest.mark.asyncio
async def test_missing_room_id():
    service, _, _ = make_service(is_admin=True)

    with pytest.raises(SynapseError) as exc:
        await service.stop_broadcast(user_id="@admin:localhost", room_id=None)

    assert exc.value.code == 400


@pytest.mark.asyncio
async def test_no_active_broadcast_returns_400_without_calling_youtube():
    service, _, youtube_client = make_service(
        is_admin=True,
        stream={"room_id": "!room:localhost", "provider": "fixed", "youtube_broadcast_id": None, "youtube_watch_url": None},
    )

    with pytest.raises(SynapseError) as exc:
        await service.stop_broadcast(user_id="@admin:localhost", room_id="!room:localhost")

    assert exc.value.code == 400
    youtube_client.end_broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_success_calls_youtube_then_clears_db():
    service, room_streams_service, youtube_client = make_service(is_admin=True)

    result = await service.stop_broadcast(user_id="@admin:localhost", room_id="!room:localhost")

    youtube_client.end_broadcast.assert_awaited_once_with("abc123XYZ_9")
    room_streams_service.clear_youtube_broadcast.assert_awaited_once_with(
        user_id="@admin:localhost", room_id="!room:localhost"
    )
    assert result == {"room_id": "!room:localhost", "broadcast_id": "abc123XYZ_9", "stopped": True}


@pytest.mark.asyncio
async def test_youtube_failure_does_not_clear_db():
    """
    Decisão: se o YouTube recusar o encerramento, o registro local NÃO é
    limpo -- ao contrário de start_broadcast, aqui "falhar silenciosamente"
    deixaria o Element achar que a live acabou quando ela continua no ar.
    """
    service, room_streams_service, youtube_client = make_service(is_admin=True)
    youtube_client.end_broadcast.side_effect = RuntimeError("YouTube API down")

    with pytest.raises(SynapseError) as exc:
        await service.stop_broadcast(user_id="@admin:localhost", room_id="!room:localhost")

    assert exc.value.code == 502
    room_streams_service.clear_youtube_broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_youtube_not_configured_returns_503_and_does_not_clear_db():
    service, room_streams_service, youtube_client = make_service(is_admin=True)
    youtube_client.end_broadcast.side_effect = YoutubeNotConfiguredError("missing config")

    with pytest.raises(SynapseError) as exc:
        await service.stop_broadcast(user_id="@admin:localhost", room_id="!room:localhost")

    assert exc.value.code == 503
    room_streams_service.clear_youtube_broadcast.assert_not_awaited()


class FakeHttpError:
    """Simula googleapiclient.errors.HttpError o suficiente para testar
    _is_already_ended_error sem depender da lib do Google instalada."""

    def __init__(self, reason: str = "", message: str = ""):
        body = {"error": {"errors": [{"reason": reason}] if reason else [], "message": message}}
        self.content = json.dumps(body).encode("utf-8")

    def __str__(self):
        return self.content.decode("utf-8")


class TestIsAlreadyEndedError:
    def _check(self, reason="", message=""):
        from modules.youtube_live_service.youtube_client import RealYoutubeClient

        return RealYoutubeClient._is_already_ended_error(FakeHttpError(reason=reason, message=message))

    def test_invalid_transition_is_already_ended(self):
        """
        Regressão: o reason real devolvido pela API (confirmado em
        produção, synapse#20) é "invalidTransition", sem o prefixo "error"
        que tínhamos presumido inicialmente ("errorInvalidTransition").
        Com o reason errado, este caso nunca batia e o Element mostrava um
        502 ao tentar encerrar um broadcast que já tinha acabado fora do
        Element (OBS fechado, encerrado manualmente no YouTube Studio).
        """
        assert self._check(reason="invalidTransition", message="Invalid transition") is True

    def test_broadcast_not_found_reason_is_already_ended(self):
        assert self._check(reason="liveBroadcastNotFound") is True

    def test_redundant_transition_reason_is_already_ended(self):
        assert self._check(reason="redundantTransition") is True

    def test_message_mentioning_already_is_already_ended(self):
        assert self._check(message="The broadcast is already in the complete state.") is True

    def test_unrelated_quota_error_is_not_already_ended(self):
        assert self._check(reason="quotaExceeded", message="Quota exceeded") is False

    def test_unrelated_permission_error_is_not_already_ended(self):
        assert self._check(reason="forbidden", message="Insufficient permission") is False

    def test_malformed_error_body_does_not_crash(self):
        from modules.youtube_live_service.youtube_client import RealYoutubeClient

        class BrokenError:
            content = b"not json"

            def __str__(self):
                return "not json"

        assert RealYoutubeClient._is_already_ended_error(BrokenError()) is False