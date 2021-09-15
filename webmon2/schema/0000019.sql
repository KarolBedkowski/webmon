/*
 * 0000019.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

-- delete global setting moved to config file

DELETE FROM settings WHERE "key" = 'smtp_host';
DELETE FROM settings WHERE "key" = 'smtp_port';
DELETE FROM settings WHERE "key" = 'smtp_login';
DELETE FROM settings WHERE "key" = 'smtp_password';
DELETE FROM settings WHERE "key" = 'smtp_tls';
DELETE FROM settings WHERE "key" = 'smtp_ssl';
DELETE FROM settings WHERE "key" = 'mail_from';

DELETE FROM user_settings WHERE "key" = 'mail_from';
DELETE FROM user_settings WHERE "key" = 'smtp_host';
DELETE FROM user_settings WHERE "key" = 'smtp_port';
DELETE FROM user_settings WHERE "key" = 'smtp_login';
DELETE FROM user_settings WHERE "key" = 'smtp_password';
DELETE FROM user_settings WHERE "key" = 'smtp_tls';
DELETE FROM user_settings WHERE "key" = 'smtp_ssl';

-- vim:et
