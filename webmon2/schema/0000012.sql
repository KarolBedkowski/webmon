/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

INSERT INTO settings (key, value, value_type, description)
VALUES
  ('start_at_unread_group',  'false', 'bool', 'Start at first unread group')
;
-- vim:et
