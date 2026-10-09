# Room Streams Service Module for Matrix Synapse

Stores the live streaming configuration for each room, and owns the
`room_streams` table — the only place in the codebase that reads or writes
it. Supports two providers, coexisting per room.

## Model: two providers

- **`fixed`** — a single `playback_url` (public HLS URL), registered
  manually by an admin in the room's settings. The module doesn't talk to
  any streaming service (IVS, MediaMTX or otherwise); it only stores the URL
  that's already configured on some external channel. Switching services
  doesn't change anything here, only the registered URL.
- **`youtube`** — no fixed URL. Broadcasts are created on demand by the
  `youtube_live_service` module every time someone starts a Live.
  `youtube_broadcast_id` and `youtube_watch_url` hold the currently
  associated broadcast, if any (both null when no live is running).

## Cross-module use

`youtube_live_service` doesn't query `room_streams` directly — no other
module does. It calls methods on this module's service instance instead:

- **`require_youtube_room(room_id)`** — raises `404` if the room has no
  stream configuration, `400` if `provider` isn't `youtube`. Called before
  creating a broadcast, so a request against a nonexistent room or a
  `fixed`-provider room fails cheaply instead of creating an orphan
  broadcast on the company's YouTube channel.
- **`set_youtube_broadcast(room_id, broadcast_id, watch_url)`** — persists a
  broadcast just created by `youtube_live_service`, so it survives past the
  single HTTP response (recoverable via `get_stream`, not lost if the
  response never reaches the client).
- **`clear_youtube_broadcast(user_id, room_id)`** — called by the frontend
  when a live is stopped (see the `clear_youtube_broadcast` endpoint below).

This works through `ModuleApi`: `RoomStreamsServiceModule` stores its service
instance at `api._hs.room_streams_service` on load, the same pattern
`room_service` already used (`self.hs.room_service`). **`room_streams_service`
must be listed before `youtube_live_service` in `homeserver.yaml`** —
`YoutubeLiveServiceModule` raises `RuntimeError` at startup otherwise, rather
than failing confusingly later.

`set_stream` clears `youtube_broadcast_id`/`youtube_watch_url` whenever a
room's configuration changes — an old broadcast tied to a superseded config
shouldn't be reported as current.

## Endpoints

All under `/_synapse/room_streams_service/*`, POST method.

### `get_stream`
Returns the room's full stream configuration, or defaults (`provider:
"fixed"`, everything else `null`) if the room isn't configured yet. Public
endpoint (any authenticated user) — knowing the URL is required to build the
widget and watch the stream.

**Body:** `{ "room_id": "!room:example.com" }`

**Response:**
```json
{
    "room_id": "!room:example.com",
    "playback_url": "https://.../live.m3u8" | null,
    "provider": "fixed" | "youtube",
    "youtube_broadcast_id": "abc123XYZ_9" | null,
    "youtube_watch_url": "https://www.youtube.com/watch?v=abc123XYZ_9" | null
}
```

### `set_stream`
Registers or updates the room's provider and, for `fixed`, its
`playback_url`. Admin-only.

**Body:** `{ "room_id": "!room:example.com", "playback_url": "https://.../live.m3u8", "provider": "fixed" }`

`playback_url` is required (non-empty after stripping) when `provider` is
`"fixed"`; ignored (stored as `null`) when `provider` is `"youtube"`. Also
clears `youtube_broadcast_id`/`youtube_watch_url`, if set — a broadcast tied
to a superseded config shouldn't be reported as current.

**Errors:** `400` missing `room_id`, missing `playback_url` for `fixed`, or
invalid `provider`; `403` if the requester is not an admin.

### `clear_youtube_broadcast`
Clears `youtube_broadcast_id`/`youtube_watch_url` back to `null`, without
touching `playback_url`/`provider`. Called by the frontend when a YouTube
live is stopped — `stopLive` only removes the Matrix widget, so without this
call `get_stream` would keep reporting an ended broadcast as current.
Admin-only.

**Body:** `{ "room_id": "!room:example.com" }`

**Errors:** `400` missing `room_id`; `403` if the requester is not an admin.

## Configuration

```yaml
modules:
  - module: modules.room_streams_service.module.RoomStreamsServiceModule
    config:
      admin_user_id: "@admin:localhost"
      admin_token_file: "/data/admin_token.txt"
      homeserver: "http://localhost:3000"
```

## Database

`room_streams` table (`infra/synapse-docker/migrations/001_init.sql` for
fresh databases, `002_add_stream_provider.sql` and
`003_youtube_broadcast_columns.sql` for existing ones): `room_id` (PK, FK to
`room_business` with `ON DELETE CASCADE`), `playback_url`, `provider`
(`fixed` | `youtube`, default `fixed`), `youtube_broadcast_id`,
`youtube_watch_url`, `created_at`, `updated_at`. Two check constraints:
`playback_url` is required when `provider = 'fixed'`
(`room_streams_fixed_requires_url`), and the two YouTube columns are either
both null or both set (`room_streams_youtube_fields_match`).

## Tests

`PYTHONPATH=. pytest modules/room_streams_service/tests/` — 21 tests covering
`get_stream`/`set_stream` for both providers, required-field validation, the
admin check (including that the DB isn't touched when it fails),
`require_youtube_room`'s three outcomes, `set_youtube_broadcast`, and
`clear_youtube_broadcast`.