/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

ALTER TABLE sources ALTER COLUMN name DROP NOT NULL;
ALTER TABLE sources ADD COLUMN status INTEGER;

UPDATE sources SET status=1;

-- vim:et
