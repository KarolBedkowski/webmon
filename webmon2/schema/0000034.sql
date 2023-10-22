/*
 * 0000034.sql
 * Copyright (C) 2023 Karol Będkowski <Karol Będkowski@kkomp>
 *
 * Distributed under terms of the GPLv3 license.
 */

INSERT INTO settings (key, value, value_type)
VALUES ('http_headers', '"DNT: 1\n"', 'text')
    ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type;



-- vim:et
