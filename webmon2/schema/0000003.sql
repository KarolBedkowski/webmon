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
  ('workers', '4', 'int', 'Loading workers'),
  ('jamendo_client_id', '', 'str', 'Jamendo client ID');


insert into source_groups (name) values ("main");

insert into sources (group_id, kind, name, interval, settings, filters)
values (1, 'url', 'hn', 10, '{"url": "https://news.ycombinator.com/"}',
    '[{"name": "get-elements-by-css", "sel": ".title"}, {"name": "html2text"}, {"name": "strip"}, {"name": "grep", "invert": true, "pattern": "^\\d+\\.$"}, {"name": "remove_visited"}, {"name": "join"}]'
);

insert into source_state(source_id, next_update) values (1, datetime('now'));

-- vim:et
