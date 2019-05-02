/*
 * 0000004.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE filters_state (
    source_id           integer REFERENCES sources(id) ON DELETE CASCADE,
    filter_name         varchar NOT NULL,
    state               json,
    PRIMARY KEY(source_id, filter_name)
);

CREATE INDEX filters_state_source_id_idx ON filters_state(source_id);
