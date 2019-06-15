/*
 * 0000002.sql
 *
 * Copyright (c) Karol Będkowski, 2016-2019
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE users (
    id                  serial PRIMARY KEY,
    login               varchar,
    email               varchar,
    password            varchar,
    active              boolean,
    admin               boolean default false
);

CREATE INDEX users_login_idx on users(login);

-- global application settings definition
CREATE TABLE settings (
    key             varchar PRIMARY KEY,
    value_type      varchar,
    description     varchar,
    value           varchar    -- default value
);


CREATE TABLE source_groups (
    id      serial PRIMARY KEY,
    user_id integer REFERENCES users(id),
    name    varchar
);

CREATE INDEX source_groups_user_id_idx ON source_groups(user_id);

-- sources configuration
CREATE TABLE sources (
    id                  serial PRIMARY KEY,
    group_id            integer references source_groups(id) on delete set null,
    user_id             integer REFERENCES users(id),
    kind                varchar not null,   -- source type
    name                varchar not null,   -- source name
    interval            varchar,            -- crone-like expression
    settings            varchar,               -- source kind-specific configuration
    filters             varchar
);

CREATE INDEX sources_group_id_idx ON sources(group_id);
CREATE INDEX sources_user_id_idx ON sources(user_id);

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
    state           text
);

CREATE INDEX source_states_next_update_idx ON source_state(next_update);

CREATE TABLE entries (
    id          serial PRIMARY KEY,
    source_id   integer not null references sources(id) on delete cascade,
    updated     timestamp,
    created     timestamp,
    read_mark   integer default 0, -- 0=unread, 1=read, 2=read/history
    star_mark   integer default 0,
    user_id     integer REFERENCES users(id),
    status      varchar,
    oid         varchar(64) unique,        -- entry hash
    title       varchar,
    url         varchar,
    opts        varchar,
    content     text
);

CREATE INDEX entries_source_id_idx ON entries(source_id);
CREATE INDEX entries_read_idx ON entries(read_mark, updated);
CREATE INDEX entries_star_idx ON entries(star_mark, updated);
CREATE INDEX entries_oid_idx ON entries(oid);
CREATE INDEX entries_updated_idx ON entries(updated);
CREATE INDEX entries_user_id_idx ON entries(user_id);
CREATE INDEX entries_idx1 ON entries(user_id, read_mark);


CREATE TABLE history_oids (
    source_id           integer references sources(id) on delete cascade,
    oid                 varchar not null,
    created             timestamp default CURRENT_TIMESTAMP,
    PRIMARY KEY(source_id, oid)
);

CREATE TABLE filters_state (
    source_id           integer REFERENCES sources(id) ON DELETE CASCADE,
    filter_name         varchar NOT NULL,
    state               varchar,
    PRIMARY KEY(source_id, filter_name)
);

CREATE INDEX filters_state_source_id_idx ON filters_state(source_id);

CREATE TABLE user_settings (
    key                 varchar REFERENCES settings(key) ON DELETE CASCADE,
    user_id             integer REFERENCES users(id) ON DELETE CASCADE,
    value               varchar,
    PRIMARY KEY(key, user_id)
);

CREATE INDEX user_settings_user_idx ON user_settings(user_id);

-- vim:et
