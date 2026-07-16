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
