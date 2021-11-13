/*
 * 0000024.sql
 * Copyright (C) 2021 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */

DROP INDEX IF EXISTS entries_icon;
DROP INDEX IF EXISTS entries_oid_idx;
DROP INDEX IF EXISTS entries_source_id_idx;
DROP INDEX IF EXISTS entries_star_idx;
DROP INDEX IF EXISTS entries_updated_idx;
DROP INDEX IF EXISTS entries_user_id_idx;
DROP INDEX IF EXISTS filters_state_source_id_idx;
DROP INDEX IF EXISTS scoring_sett_user_id;
DROP INDEX IF EXISTS source_state_icon;
DROP INDEX IF EXISTS sources_status_idx;

CREATE INDEX IF NOT EXISTS entries_up_star_idx ON entries USING btree (updated, user_id, star_mark);
CREATE INDEX IF NOT EXISTS entries_usr_icon_idx ON entries USING btree (icon, user_id);
CREATE INDEX IF NOT EXISTS scoring_sett_idx1 ON scoring_sett USING btree (user_id, active);
CREATE INDEX IF NOT EXISTS source_state_src_icon_idx ON source_state USING btree (icon, source_id);

ANALYZE entries;
ANALYZE filters_state;
ANALYZE scoring_sett;
ANALYZE sources;
ANALYZE source_state;

-- vim:et
