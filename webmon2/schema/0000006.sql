/*
 * 0000003.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

insert into settings (key, value, value_type, description)
values ('keep_entries_days', '30', 'int', 'Keep read entries by given days');


-- vim:et
