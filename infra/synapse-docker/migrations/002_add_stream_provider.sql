-- 002_add_stream_provider.sql
--
-- Adiciona suporte ao provider ("fixed" | "youtube") na room_streams, para
-- bancos que já existiam antes dessa mudança (001_init.sql só aplica em
-- banco novo, via /docker-entrypoint-initdb.d -- não roda em bancos já
-- inicializados).


ALTER TABLE room_streams
    ALTER COLUMN playback_url DROP NOT NULL;

ALTER TABLE room_streams
    ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'fixed';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'room_streams_provider_check'
    ) THEN
        ALTER TABLE room_streams
            ADD CONSTRAINT room_streams_provider_check
            CHECK (provider IN ('fixed', 'youtube'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'room_streams_fixed_requires_url'
    ) THEN
        ALTER TABLE room_streams
            ADD CONSTRAINT room_streams_fixed_requires_url
            CHECK (provider != 'fixed' OR playback_url IS NOT NULL);
    END IF;
END $$;