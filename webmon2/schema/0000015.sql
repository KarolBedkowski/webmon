/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE INDEX IF NOT EXISTS entries_title_idx
    ON entries
    USING GIN (to_tsvector('pg_catalog.simple', title));

CREATE INDEX IF NOT EXISTS entries_content_title_idx
    ON entries
    USING gin (to_tsvector('pg_catalog.simple', content || ' ' || title));

-- vim:et
