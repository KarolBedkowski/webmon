/*
 * 0000026.sql
 * Copyright (C) 2022 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */

ALTER TABLE entries ALTER COLUMN oid SET DATA TYPE CHARACTER VARYING(32);
ALTER TABLE source_state ALTER COLUMN icon SET DATA TYPE CHARACTER VARYING(64);
ALTER TABLE source_state ALTER COLUMN status SET DATA TYPE CHARACTER VARYING(16);
ALTER TABLE sources ALTER COLUMN mail_report SET DEFAULT 1;
CREATE UNIQUE INDEX sources_status_idx2 ON public.sources USING btree (status, id);

DROP INDEX IF EXISTS entries_idx1;

ANALYZE sources;
ANALYZE source_state;
ANALYZE entries;



-- vim:et
