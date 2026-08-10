-- 001_init.sql

CREATE TABLE public.bundles (
    bundle_id uuid PRIMARY KEY,
    bundle_name text NOT NULL,
    price int4 NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    created_by text NOT NULL,
    status text DEFAULT 'draft' NOT NULL
);

CREATE TABLE public.bundle_rooms (
    bundle_id uuid NOT NULL,
    room_id text NOT NULL,
    PRIMARY KEY (bundle_id, room_id),
    FOREIGN KEY (bundle_id)
        REFERENCES public.bundles(bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE public.room_business (
    room_id text PRIMARY KEY,
    room_kind text NOT NULL,
    access_type text NOT NULL,
    visible bool NOT NULL,
    price int4 DEFAULT 0,
    keyword text UNIQUE,
    created_at int8 NOT NULL
);

CREATE TABLE public.room_features (
    room_id text NOT NULL,
    feature text NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    created_at int8 NOT NULL,
    updated_at int8 NOT NULL,
    PRIMARY KEY (room_id, feature),
    FOREIGN KEY (room_id)
        REFERENCES public.room_business(room_id)
        ON DELETE CASCADE
);

CREATE INDEX room_features_room_idx ON public.room_features (room_id);

CREATE TABLE public.streams (
    id                     BIGSERIAL PRIMARY KEY,
    stream_id              TEXT,
    room_id                TEXT NOT NULL,
    title                  TEXT,
    category_id            BIGINT,
    recording_path         TEXT,
    recording_duration_ms  BIGINT,
    recording_started_at   BIGINT,
    recording_ended_at     BIGINT,
    started_at             BIGINT,
    ended_at               BIGINT,
    created_at             BIGINT,
    updated_at             BIGINT,
    FOREIGN KEY (room_id)
        REFERENCES public.room_business(room_id)
        ON DELETE CASCADE
);

CREATE INDEX streams_room_started_idx ON public.streams (room_id, started_at DESC);
CREATE INDEX streams_stream_id_idx ON public.streams (stream_id);
