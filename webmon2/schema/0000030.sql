/*
 * 0000030.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE sessions (
    id              varchar(36) PRIMARY KEY,
    expiry          timestamptz,
    data            bytea
);

-- vim:et
