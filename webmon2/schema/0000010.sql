/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

ALTER TABLE entries ADD COLUMN icon varchar(64);
COMMENT ON COLUMN entries.icon IS 'icon hash';


CREATE TABLE binaries (
    datahash        varchar(64),
    user_id         integer REFERENCES users(id),
    data            bytea,
    content_type    text,
    PRIMARY KEY(datahash, user_id)
);

CREATE INDEX binaries_user_id ON binaries (user_id);


-- vim:et
