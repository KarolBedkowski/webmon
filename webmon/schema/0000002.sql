/*
 * 0000002.sql
 * Copyright (C) 2019  <@K-HP>
 *
 * Distributed under terms of the GPLv3 license.
 */

-- global application settings
CREATE TABLE settings (
    key     varchar not null,
    value   json
);


CREATE TABLE source_groups (
    id      integer primary key autoincrement,
    name    varchar
);

-- sources configuration
CREATE TABLE sources (
    id                  integer primary key autoincrement,
    group_id            integer references source_groups(id) on delete set null,
    kind                varchar not null,   -- source type
    name                varchar not null,   -- source name
    interval            varchar,            -- crone-like expression
    settings            json,               -- source kind-specific configuration
    filters             json
);

-- source state
CREATE TABLE source_state (
    source_id       integer primary key references sources(id) on delete cascade,
    next_update     timestamp,          -- next update
    last_update     timestamp,
    last_error      timestamp,
    error_counter   integer default 0,
    success_counter integer default 0,
    status          varchar,
    error           varchar,
    state           json
);


CREATE TABLE entries (
    id          integer primary key autoincrement,
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



-- vim:et
