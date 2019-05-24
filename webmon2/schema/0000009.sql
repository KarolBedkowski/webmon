/*
 * 0000008.sql
 * Copyright (C) 2019 Karol Będkowski
 *
 * Distributed under terms of the GPLv3 license.
 */

ALTER TABLE sources ADD COLUMN mail_report INTEGER DEFAULT 1;
COMMENT ON COLUMN sources.mail_report IS '0=no reporting; 1=as group; 2=yes';

ALTER TABLE source_groups ADD COLUMN mail_report INTEGER DEFAULT 1;
COMMENT ON COLUMN source_groups.mail_report IS '0=no reporting; 1=as source; 2=yes';

UPDATE sources SET mail_report = 1;
UPDATE source_groups SET mail_report = 1;


-- vim:et
