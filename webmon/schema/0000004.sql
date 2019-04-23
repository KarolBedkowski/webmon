/*
 * 0000004.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE history_oids (
    source_id           integer references source(id) on delete cascade,
    oid                 varchar not null,
    created             timestamp default CURRENT_TIMESTAMP,
    PRIMARY KEY(source_id, oid)
);
