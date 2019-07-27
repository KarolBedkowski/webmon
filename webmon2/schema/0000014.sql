/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

CREATE TABLE scoring_sett (
    id              serial PRIMARY KEY,
    user_id         integer 
                    REFERENCES users(id) ON DELETE CASCADE,
    pattern         text,
    active          boolean default true,
    score_change    integer
);

CREATE INDEX scoring_sett_user_id ON scoring_sett(user_id);

-- vim:et
