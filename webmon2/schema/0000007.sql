/*
 * 0000003.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

INSERT INTO settings (key, value, value_type, description)
VALUES
  ('mail_mark_read', 'true',    'bool', 'mark reported entries read')
;
-- vim:et
