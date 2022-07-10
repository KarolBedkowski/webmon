/*
 * 0000033.sql
 * Copyright (C) 2022 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE user_logs (
    user_id         integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ts              timestamptz NOT NULL DEFAULT now(),
    content         text,
    related         text
);

CREATE INDEX user_logs_idx ON user_logs(user_id, ts);

-- vim:et
