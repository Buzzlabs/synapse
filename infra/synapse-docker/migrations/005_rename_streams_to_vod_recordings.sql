-- 005_rename_streams_to_vod_recordings.sql
-- A tabela streams guarda o historico de gravacoes (VODs) e se confundia
-- com room_streams (canal atual da sala). Passa a se chamar vod_recordings,
-- e a coluna stream_id (texto "vod_<uuid>") passa a se chamar vod_id.
-- Renomeia tambem a sequencia, a chave primaria, a chave estrangeira e os
-- indices, que nao acompanham o rename da tabela. Pode rodar mais de uma vez.

DO $$
BEGIN
    IF to_regclass('public.streams') IS NOT NULL
       AND to_regclass('public.vod_recordings') IS NULL THEN
        ALTER TABLE public.streams RENAME TO vod_recordings;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'vod_recordings'
          AND column_name = 'stream_id'
    ) THEN
        ALTER TABLE public.vod_recordings RENAME COLUMN stream_id TO vod_id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'streams_room_id_fkey'
          AND conrelid = 'public.vod_recordings'::regclass
    ) THEN
        ALTER TABLE public.vod_recordings
            RENAME CONSTRAINT streams_room_id_fkey TO vod_recordings_room_id_fkey;
    END IF;
END $$;

ALTER SEQUENCE IF EXISTS public.streams_id_seq RENAME TO vod_recordings_id_seq;
ALTER INDEX IF EXISTS public.streams_pkey RENAME TO vod_recordings_pkey;
ALTER INDEX IF EXISTS public.streams_room_started_idx RENAME TO vod_recordings_room_started_idx;
ALTER INDEX IF EXISTS public.streams_stream_id_idx RENAME TO vod_recordings_vod_id_idx;
