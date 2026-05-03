/*
 * 0000035.sql
 * Copyright (C) 2026 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */


-- add default user admin with password admin when no other users exists.
INSERT INTO users (login, email, password, active, admin)
SELECT 'admin', 'admin@localhost.local',
    'c0426fbbaad0457910a53171622035162e0918990c25f9f24b683db1dc0c9149cb8829499bd38e51298c24112a7ed0fc3a1e9b4828fbd8bca815d10d66dbbc8c54b0940b3c963080a6555d7c12236fa9',
    TRUE, TRUE
WHERE NOT EXISTS (SELECT NULL FROM users);


-- vim:et
