/*
 * 0000024.sql
 * Copyright (C) 2021 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */


DROP INDEX IF EXISTS entries_read_idx2;
DROP INDEX IF EXISTS entries_idx2;
DROP INDEX IF EXISTS entries_up_star_idx;
DROP INDEX IF EXISTS source_states_next_update_idx;
DROP INDEX IF EXISTS scoring_sett_idx1;

CREATE INDEX IF NOT EXISTS entries_idx3 ON entries USING btree (source_id) WHERE read_mark = 0;
CREATE INDEX IF NOT EXISTS entries_idx4 ON entries USING btree (user_id) WHERE read_mark = 0;
CREATE INDEX IF NOT EXISTS entries_up_star_idx2 ON public.entries USING btree (user_id, updated) WHERE star_mark = 1;
CREATE INDEX IF NOT EXISTS entries_read_idx2 ON entries USING btree (updated) WHERE read_mark = 0;
CREATE INDEX IF NOT EXISTS scoring_sett_idx2 ON scoring_sett USING btree (user_id) WHERE active;

DROP INDEX IF EXISTS source_state_source_id_idx;
CREATE UNIQUE INDEX IF NOT EXISTS source_state_source_id_idx ON source_state USING btree (next_update, source_id);

DROP INDEX IF EXISTS source_state_src_icon_idx;
CREATE UNIQUE INDEX IF NOT EXISTS source_state_src_icon_idx ON source_state USING btree (icon, source_id);

ANALYZE entries;
ANALYZE scoring_sett;
ANALYZE source_state;

-- vim:et
