# Room Streams Service Module for Matrix Synapse

Stores the live streaming channel (Live) for each room.

## Model: fixed channel

Each room can have **one streaming channel** associated with it, represented by a single `playback_url` — the public (HLS) URL the audience uses to watch. The admin registers this URL once, in the room's settings.

The module **does not talk to any streaming service** (IVS, MediaMTX or
otherwise). It only stores the URL that has already been configured on some
external channel, and makes it available to the frontend to build the live
widget. Which streaming service is chosen, and how the streamer configures the encoder (OBS or similar) to stream to that channel, is decided and done outside Synapse — Synapse only stores and returns the playback URL.

This keeps the feature independent of whichever streaming service is chosen:
switching from IVS to MediaMTX (or vice versa) doesn't change anything in this module, only the registered URL.

## Endpoints

All under `/_synapse/room_streams_service/*`, POST method.

### `get_stream`
Returns the `playback_url` registered for the room, or `null` if no channel is configured. Public endpoint (any authenticated user) — knowing the URL is
required to build the widget and watch the stream.

**Body:** `{ "room_id": "!room:example.com" }`

**Response:** `{ "room_id": "...", "playback_url": "..." | null }`

### `set_stream`
Registers or updates the room's `playback_url`. Admin-only.

**Body:** `{ "room_id": "!room:example.com", "playback_url": "https://.../live.m3u8" }`

**Errors:** `400` missing `room_id`/`playback_url`; `403` if the requester is
not an admin.

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

`room_streams` table (see `room_streams.sql`): `room_id` (PK, FK to
`room_business` with `ON DELETE CASCADE`), `playback_url`, `created_at`,
`updated_at`. Follows the same pattern as `room_calendars`.

## Tests

`PYTHONPATH=. pytest modules/room_streams_service/tests/` — 7 tests covering
get/set, required-field validation, and the admin check.