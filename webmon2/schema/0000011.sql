/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

ALTER TABLE source_state ADD COLUMN icon varchar(40);
COMMENT ON COLUMN source_state.icon IS 'icon hash';


CREATE INDEX source_state_icon ON source_state(icon);
CREATE INDEX entries_icon ON entries(icon);
-- vim:et
