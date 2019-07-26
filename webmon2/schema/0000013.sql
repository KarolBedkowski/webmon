/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */


ALTER TABLE sources ADD COLUMN default_score INTEGER DEFAULT 0;
ALTER TABLE entries ADD COLUMN score INTEGER DEFAULT 0;

-- vim:et
