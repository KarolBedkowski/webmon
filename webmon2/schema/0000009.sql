/*
 * 0000004.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE user_settings (
    key                 varchar REFERENCES settings(key) ON DELETE CASCADE,
    user_id             integer REFERENCES users(id) ON DELETE CASCADE,
    value               json,
    PRIMARY KEY(key, user_id)
);

INSERT INTO user_settings(key, user_id, value)
SELECT key, user_id, value
FROM settings
WHERE user_id IS NOT NULL;

DELETE FROM settings
WHERE user_id IS NOT NULL;
