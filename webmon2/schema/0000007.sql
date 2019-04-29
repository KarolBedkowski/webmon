/*
 * 0000003.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

DELETE FROM settings
WHERE key = 'workers';

ALTER TABLE settings ADD COLUMN user_id REFERENCES users(id);
CREATE INDEX settings_user_id_idx ON settings(user_id);

-- copy settings
INSERT INTO settings (key, value, value_type, description, user_id)
SELECT s.key, s.value, s.value_type, s.description, u.id
FROM settings s, users u
WHERE s.user_id IS NULL;

UPDATE settings
SET value = ''
WHERE key in ('github_token', 'github_user', 'jamendo_client_id')
    AND user_id IS NULL;


ALTER TABLE sources ADD COLUMN user_id REFERENCES users(id);
CREATE INDEX sources_user_id_idx ON sources(user_id);
UPDATE sources
SET user_id = (select min(id) from users)
WHERE user_id is NULL;

ALTER TABLE entries ADD COLUMN user_id REFERENCES users(id);
CREATE INDEX entries_user_id_idx ON entries(user_id);
UPDATE entries
SET user_id = (select min(id) from users)
WHERE user_id is NULL;

ALTER TABLE source_groups ADD COLUMN user_id REFERENCES users(id);
CREATE INDEX source_groups_user_id_idx ON source_groups(user_id);
UPDATE source_groups
SET user_id = (select min(id) from users)
WHERE user_id is NULL;



-- vim:et
