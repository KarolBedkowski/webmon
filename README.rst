webmon ver 2.5.x
================

Monitor changes on web pages, command results, GitHub repositories, Jamendo
albums, RSS channels.
With web ui and optionally sending report by mail.

Inspired by https://github.com/thp/urlwatch and http://miniflux.app/ (webmon2
gui)

Dependences
-----------

* Python 3.0+
* Postgresql 10+
* requests
* yaml
* html2text (for html2text filter)
* markdown2 (for HTML output/reports/mails)
* defusedxml / ElementTree (for get-elements-* filters)
* feedparser (for rss input)
* github3py (for GitHub api; pip install --pre github3.py)
* cssselect & python3-lxml (for elements filtering)
* readability-lxml
* flask, Werkzeug, gevent and optional Flask_Minify
* python-gitlab (for gitlab api; pip install python-gitlab)
* pyotp, pyqrcode for TOTP 2FA
* sdnotify (optional for systemd service)


Installation
------------

1. `pip3 install webmon2<version>.whl`
2. create database (`createuser -P webmon2; createdb -O webmon2 webmon2`)
3. create configuration file (see below)
4. update schema: `webmon2 update-schema`



Usage
-----

1. launch `webmon2 -h` to see help

Global Options
^^^^^^^^^^^^^^
::

   usage: webmon2.py [-h] [-s] [-v] [-d] [--log LOG] [-c CONF] [--database DATABASE] {abilities,update-schema,migrate,users,serve,write-config} ...

   webmon2 2.5.1

   positional arguments:
     {abilities,update-schema,migrate,users,serve,write-config}
                           Commands
       abilities           show available filters/sources/comparators
       update-schema       update database schema
       migrate             migrate sources from file
       users               manage users
       serve               Start application
       write-config        write default configuration file

   optional arguments:
     -h, --help            show this help message and exit
     -s, --silent          show only errors and warnings
     -v, --verbose         show additional information
     -d, --debug           print debug information
     --log LOG             log file name
     -c CONF, --conf CONF  configuration file name
     --database DATABASE   database connection string


Start server
^^^^^^^^^^^^
::

   usage: webmon2.py serve [-h] [--app-root WEB_APP_ROOT] [--workers WORKERS]
                           [--address WEB_ADDRESS] [--port WEB_PORT]
                           [--smtp-server-address SMTP_SERVER_ADDRESS]
                           [--smtp-server-port SMTP_SERVER_PORT]
                           [--smtp-server-ssl] [--smtp-server-starttls]
                           [--smtp-server-from SMTP_SERVER_FROM]
                           [--smtp-server-login SMTP_SERVER_LOGIN]
                           [--smtp-server-password SMTP_SERVER_PASSWORD]

   optional arguments:
     -h, --help            show this help message and exit
     --app-root WEB_APP_ROOT
                           root for url patch (for reverse proxy)
     --workers WORKERS     number of background workers
     --address WEB_ADDRESS
                           web interface listen address
     --port WEB_PORT       web interface listen port
     --smtp-server-address SMTP_SERVER_ADDRESS
                           smtp server address
     --smtp-server-port SMTP_SERVER_PORT
                           smtp server port
     --smtp-server-ssl     enable ssl for smtp serve
     --smtp-server-starttls
                           enable starttls for smtp serve
     --smtp-server-from SMTP_SERVER_FROM
                           email address for webmon
     --smtp-server-login SMTP_SERVER_LOGIN
                           login for smtp authentication
     --smtp-server-password SMTP_SERVER_PASSWORD
                           password for smtp authentication


Manage users
^^^^^^^^^^^^
::

   usage: webmon2.py users [-h] {add,passwd,remove_totp} ...

   positional arguments:
     {add,passwd,remove_totp}
                           user commands
       add                 add user
       passwd              change user password
       remove_totp         remove two factor authentication for user

   optional arguments:
     -h, --help            show this help message and exit


Database
^^^^^^^^

Webmon2 requre Posrgresql database.

DATABASE - connection string in form:
`postgresql://<user>:<pass>@<host>:<port>/<database>`


Configuration file
^^^^^^^^^^^^^^^^^^

Some options may be configured globally in configuration file  selected by
`-c` `--config` argument. When no file is selected application try load
configuration file from `~/.config/webmon2/webmon2.ini`.

See `webmon2.ini` for example / defaults.

See `write-config` for write default configuration file.


Customizations
--------------
User my define own filters, inputs, outputs and comparators by creating .py
file in ~/.local/share/webmon2 and creating subclass of:

* webmon2.filters.AbstractFilter
* webmon2.sources.AbstractSource


Licence
-------

Copyright (c) Karol Będkowski, 2016-2021

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

For details please see COPYING file.
