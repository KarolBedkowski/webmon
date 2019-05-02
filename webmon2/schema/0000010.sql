/*
 * 0000004.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */


PRAGMA foreign_keys=off;

alter table settings rename to _settings;

CREATE TABLE settings (
    key         varchar PRIMARY KEY,
    value       json,
    value_type  varchar,
    description varchar,
    user_id     integer
);

INSERT INTO settings select * from _settings;

DROP TABLE _settings;

ALTER TABLE user_settings RENAME TO _user_settings;

CREATE TABLE user_settings (
    key                 varchar REFERENCES settings(key) ON DELETE CASCADE,
    user_id             integer REFERENCES users(id) ON DELETE CASCADE,
    value               json,
    PRIMARY KEY(key, user_id)
);

INSERT INTO user_settings
SELECT * FROM _user_settings;

DROP TABLE _user_settings;


PRAGMA foreign_keys=on;
