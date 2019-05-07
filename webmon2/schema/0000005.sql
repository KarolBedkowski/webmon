/*
 * 0000005.sql
 *
 * Copyright (c) Karol Będkowski, 2016-2019
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE source_group_state (
    group_id        integer PRIMARY KEY
                    REFERENCES source_groups(id) ON DELETE CASCADE,
    last_modified   timestamp,
    etag            varchar
);



-- vim:et
