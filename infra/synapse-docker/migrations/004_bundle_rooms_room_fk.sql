-- 004_bundle_rooms_room_fk.sql
--
-- bundle_rooms.room_id nao tinha chave estrangeira: ao apagar uma sala, o
-- vinculo com os pacotes ficava para tras. Agora apaga junto (CASCADE),
-- igual as outras tabelas que dependem de room_business.
--
-- Falha de proposito se existir linha apontando para sala inexistente:
-- limpe essas linhas antes de rodar.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bundle_rooms_room_id_fkey'
    ) THEN
        ALTER TABLE public.bundle_rooms
            ADD CONSTRAINT bundle_rooms_room_id_fkey
            FOREIGN KEY (room_id)
            REFERENCES public.room_business(room_id)
            ON DELETE CASCADE;
    END IF;
END $$;

-- a chave primaria e (bundle_id, room_id): buscar por room_id sozinho nao a
-- aproveita. Esse indice evita varrer a tabela inteira ao apagar uma sala.
CREATE INDEX IF NOT EXISTS bundle_rooms_room_idx ON public.bundle_rooms (room_id);