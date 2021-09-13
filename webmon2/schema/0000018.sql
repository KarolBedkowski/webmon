/*
 * 0000018.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

insert into settings (key, value, value_type, description)
values ('silent_hours_from', '', 'int', 'Begin of silent hours');

insert into settings (key, value, value_type, description)
values ('silent_hours_to', '', 'int', 'End of silent hours');

-- vim:et
