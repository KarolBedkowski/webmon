/*
 * 0000001.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE schema_version (
    version int,
    created timestamp default CURRENT_TIMESTAMP
);



-- vim:et
