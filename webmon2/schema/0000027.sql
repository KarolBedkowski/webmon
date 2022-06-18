/*
 * 0000027.sql
 * Copyright (C) 2022 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */


ALTER TABLE public.entries ALTER COLUMN updated TYPE timestamptz USING updated::timestamptz;
ALTER TABLE public.entries ALTER COLUMN created TYPE timestamptz USING created::timestamptz;
ALTER TABLE public.history_oids ALTER COLUMN created TYPE timestamptz USING created::timestamptz;
ALTER TABLE public.schema_version ALTER COLUMN created TYPE timestamptz USING created::timestamptz;
ALTER TABLE public.source_group_state ALTER COLUMN last_modified TYPE timestamptz USING last_modified::timestamptz;
ALTER TABLE public.source_state ALTER COLUMN next_update TYPE timestamptz USING next_update::timestamptz;
ALTER TABLE public.source_state ALTER COLUMN last_error TYPE timestamptz USING last_error::timestamptz;
ALTER TABLE public.source_state ALTER COLUMN last_update TYPE timestamptz USING last_update::timestamptz;
ALTER TABLE public.source_state ALTER COLUMN last_check TYPE timestamptz USING last_check::timestamptz;


-- vim:et
