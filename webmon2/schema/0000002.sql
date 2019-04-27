/*
 * 0000002.sql
 * Copyright (C) 2019  <@K-HP>
 *
 * Distributed under terms of the GPLv3 license.
 */

-- global application settings
CREATE TABLE settings (
    key         varchar not null PRIMARY KEY,
    value       json,
    value_type  varchar,
    description varchar
);


CREATE TABLE source_groups (
    id      integer PRIMARY KEY autoincrement,
    name    varchar
);

-- sources configuration
CREATE TABLE sources (
    id                  integer PRIMARY KEY autoincrement,
    group_id            integer references source_groups(id) on delete set null,
    kind                varchar not null,   -- source type
    name                varchar not null,   -- source name
    interval            varchar,            -- crone-like expression
    settings            json,               -- source kind-specific configuration
    filters             json
);

CREATE INDEX source_group_id_idx ON sources(group_id);

-- source state
CREATE TABLE source_state (
    source_id       integer PRIMARY KEY references sources(id) on delete cascade,
    next_update     timestamp,          -- next update
    last_update     timestamp,
    last_error      timestamp,
    error_counter   integer default 0,
    success_counter integer default 0,
    status          varchar,
    error           varchar,
    state           json
);

CREATE INDEX source_states_next_update_idx ON source_state(next_update);

CREATE TABLE entries (
    id          integer PRIMARY KEY autoincrement,
    source_id   integer not null references sources(id) on delete cascade,
    updated     timestamp,
    created     timestamp,
    read_mark   boolean default 0,
    star_mark   boolean default 0,
    status      varchar,
    oid         varchar(64) unique,        -- entry hash
    title       varchar,
    url         varchar,
    opts        json,
    content     text
);

CREATE INDEX entries_source_id_idx ON entries(source_id);
CREATE INDEX entries_read_idx ON entries(read_mark, updated);
CREATE INDEX entries_star_idx ON entries(star_mark, updated);
CREATE INDEX entries_oid_idx ON entries(oid);
CREATE INDEX entries_updated_idx ON entries(updated);



-- vim:et
