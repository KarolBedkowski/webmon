WebMon ver 2.x
==============

Monitor changes on web pages, command results, GitHub repositories, Jamendo
albums, RSS channels.
With web ui and optionally sending report by mail.

Inspired by https://github.com/thp/urlwatch and http://miniflux.app/ (webmon2
gui)

Dependences
-----------

* Python 3.0+
* requests
* yaml
* html2text (for html2text filter)
* markdown2 (for html output/reports/mails)
* ElementTree (for get-elements-* filters)
* feedparser (for rss input)
* github3py (for github api; pip install --pre github3.py)
* cssselect & python3-lxml (for elements filtering)
* readability-lxml
* flask, Werkzeug, gevent
* python-gitlab (for gitlab api; pip install python-gitlab)


Usage
-----

1. launch `webmon2.py`

Options
^^^^^^^
-h, --help            show this help message and exit
-s, --silent          show only errors and warnings
-v, --verbose         show additional informations
-d, --debug           print debug informations
--log LOG             log file name
--abilities           show available filters/sourcescomparators
--database DATABASE   database connection string
--migrate MIGRATE_FILENAME
                      migrate sources from file (old configuration)
--add-user ADD_USER   add user; arguments in form <login>:<password>[:admin]
--change-user-password CHANGE_USER_PASS
                      change user password; arguments in form
                      <login>:<password>
--web-app-root WEB_APP_ROOT
                      root for url patch (for reverse proxy)
--workers WORKERS     number of background workers
--web-address WEB_ADDRESS
                      web interface listen address (default: 127.0.0.1:5000)


DATABASE - connection string in form:
`postgresql://<user>:<pass>@<host>:<port>/<database>`


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
