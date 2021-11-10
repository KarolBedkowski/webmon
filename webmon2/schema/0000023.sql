/*
 * 0000023.sql
 * Copyright (C) 2021
 *
 * Distributed under terms of the GPLv3 license.
 */


ALTER TABLE source_state ADD COLUMN last_check timestamp;
COMMENT ON COLUMN source_state.last_check IS 'source last check time';

-- vim:et
