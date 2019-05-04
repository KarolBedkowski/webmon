/*
 * 0000003.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

insert into settings (key, value, value_type, description)
values ('github_user', '', 'str', 'Github user name'),
  ('github_token', '', 'str', 'Guthub access token'),
  ('interval', '"1h"', 'str', 'Default refresh interval'),
  ('jamendo_client_id', '', 'str', 'Jamendo client ID'),
  ('keep_entries_days', '30', 'int', 'Keep read entries by given days');


-- vim:et
