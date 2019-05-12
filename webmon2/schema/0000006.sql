/*
 * 0000003.sql
 * Copyright (C) 2019
 *
 * Distributed under terms of the GPLv3 license.
 */

INSERT INTO settings (key, value, value_type, description)
VALUES
  ('mail_enabled',  'false',    'bool', 'enable mail reports'),
  ('mail_interval', '"1h"',     'str',  'send mail interval'),
  ('mail_to',       '',         'str',  'email recipient'),
  ('mail_from',     '',         'str',  'email sender'),
  ('mail_subject',  '"WebMail Report"', 'str', 'email subject'),
  ('smtp_host',     '',         'str',  'SMTP server address'),
  ('smtp_port',     '',         'int',  'SMTP server port'),
  ('smtp_login',    '',         'str',  'SMTP user login'),
  ('smtp_password', '',         'str',  'SMTP user password'),
  ('smtp_tls',      'true',     'bool', 'Enable TLS'),
  ('smtp_ssl',      'false',    'bool', 'Enable SSL'),
  ('mail_encrypt',  'false',    'bool', 'Encrypt email'),
  ('mail_html',     'false',    'bool', 'Send miltipart email with html content')
;


CREATE TABLE users_state
(
    user_id         integer     NOT NULL
                                REFERENCES users(id) ON DELETE CASCADE,
    key             varchar     NOT NULL,
    value           varchar,
    PRIMARY KEY(user_id, key)
);


-- vim:et
