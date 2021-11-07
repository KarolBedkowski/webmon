/*
 * 0000022.sql
 * Copyright (C) 2021
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE INDEX IF NOT EXISTS entries_idx2 ON public.entries USING btree (source_id, read_mark);

ALTER TABLE source_state RENAME COLUMN state TO props;

-- vim:et
