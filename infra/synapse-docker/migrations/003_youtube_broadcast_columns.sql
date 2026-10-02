-- 003_youtube_broadcast_columns.sql
--
-- Guarda o broadcast do YouTube atualmente associado à sala, quando
-- provider = 'youtube'. Sem isso, start_broadcast cria a live no YouTube
-- mas não fica sabendo se a resposta se perde (aba fechada, rede), e
-- get_stream continua devolvendo playback_url: null mesmo com uma live
-- rolando -- ninguém consegue recuperar a URL nem confirmar se está ao
-- vivo a partir do servidor.
--
-- youtube_broadcast_id existe à parte de youtube_watch_url (em vez de só
-- derivar um do outro) porque o broadcast_id é o que outras chamadas da
-- API (ex.: encerrar a transmissão do lado do YouTube) vão precisar no
-- futuro -- guardar os dois agora evita ter que voltar aqui de novo.

ALTER TABLE room_streams
    ADD COLUMN IF NOT EXISTS youtube_broadcast_id TEXT;

ALTER TABLE room_streams
    ADD COLUMN IF NOT EXISTS youtube_watch_url TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'room_streams_youtube_fields_match'
    ) THEN
        ALTER TABLE room_streams
            ADD CONSTRAINT room_streams_youtube_fields_match
            CHECK (
                (youtube_broadcast_id IS NULL) = (youtube_watch_url IS NULL)
            );
    END IF;
END $$;