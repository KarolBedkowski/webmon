/*
 * 0000020.sql
 * Copyright (C) 2021 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */

ALTER TABLE source_groups
DROP CONSTRAINT source_groups_user_id_fkey;

ALTER TABLE source_groups
ADD CONSTRAINT source_groups_user_id_fkey
FOREIGN KEY (user_id) REFERENCES users(id)
ON UPDATE CASCADE ON DELETE CASCADE;


-- vim:et
