/*
 * 0000003.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */


insert into source_groups (name) values ("main");

insert into sources (group_id, kind, name, interval, settings, filters)
values (1, 'url', 'hn', 10, '{"url": "https://news.ycombinator.com/"}',
    '[{"name": "get-elements-by-css", "sel": ".title"}, {"name": "html2text"}, {"name": "strip"}, {"name": "grep", "invert": true, "pattern": "^\\d+\\.$"}]'
);

insert into sources (group_id, kind, name, interval, settings, filters)
values (1, 'file', 'test', 10, '{"filename": "test.txt"}',
    '[{"name": "strip"}, {"name": "ndiff", "threshold": 0.2}]'
);

insert into sources (group_id, kind, name, interval, settings, filters)
values (1, 'rss', 'golangweekly', 10, '{"url": "https://golangweekly.com/rss/18196260"}', null);

insert into sources (group_id, kind, name, interval, settings, filters)
values (1, 'github_commits', 'prometheus', 10,
'{"owner": "prometheus", "repository": "prometheus", "github_user": "KarolBedkowski", "github_token": "670a14085fe18307c56eff95462218c668d527ff"}',
null);


insert into source_state(source_id, next_update) values (1, datetime('now'));
insert into source_state(source_id, next_update) values (2, datetime('now'));
insert into source_state(source_id, next_update) values (3, datetime('now'));
insert into source_state(source_id, next_update) values (4, datetime('now'));
-- vim:et
