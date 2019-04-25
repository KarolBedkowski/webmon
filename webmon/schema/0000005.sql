/*
 * 0000005.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE users (
    id                  integer PRIMARY KEY AUTOINCREMENT,
    login               varchar,
    email               varchar,
    password            varchar,
    active              boolean,
    admin               boolean default false
);

CREATE INDEX users_login_idx on users(login);
