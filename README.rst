WebMon ver 0.x
==============

Monitor changes on web pages, command results.
Write result to local file or send mail.

Inspired by https://github.com/thp/urlwatch

Dependences
-----------

* requests 
* yaml
* html2text (for html2text filter)
* docutils (for html output/reports/mails)
* ElementTree (for get-elements-* filters)

Usage
-----

1. create two config files:
   config.yaml - define outputs, smtp etc
   inputs.yaml - list of website / commands to monitor

2. launch `webmon.py`

Options
^^^^^^^
-h, --help              display help
-v                      verbose mode
-s, --silent            silent mode
-i FILE, --inputs FILE  file with definition of sources; default inputs.yaml
-c FILE, --config FILE  global configuration, default config.yaml
--log FILE              save log to file
--cache-dir DIR         path to store last version of pages; default 
                        ~/.cache/webmon/cache
--force                 force update all sources; ignore `interval` parameter
--diff-mode MODE        diff mode (unified, ndiff, context)


Configuration
-------------

config.yaml
^^^^^^^^^^^
::

  output:
      text:                   # plain text file output
          file: report.txt    # file name
      html:                   # html file output
          file: report.html   # filename
      console:                # send report to console
      email:                  # send mail
          enabled: false      # toggle enabled/disabled
          to: foo@bar.com     # recipient
          from: foo@bar.com   # sender
          subject: "WebMon"   # mail subject
          smtp_host: smtp.foo.bar   
          smtp_port: 465            
          smtp_login: login         
          smtp_password: password      
          smtp_ssl: true      # use ssl/tls
          #smtp_tls: true     # use starttls
          html: true          # send multipart mail with html 
          encrypt: gpg        # optional encrypt email with gpg
  defaults:                   # optional default parameters for inputs
      interval: 10m
      report_unchanged: false

inputs.yaml
^^^^^^^^^^^

Web sources::

  kind: url
  url: https://lobste.rs/           # url to monitor; required
  name: date                        # name of input

Command sources::

  kind: cmd
  cmd: date       # command to launch
  name: date

Common options::

  filters:                          # list of filters
      - name: get-elements-by-css   # name of filter
        sel: .link a                # filter parameters
      - name: html2text             # other filter
      - name: strip
  interval: 1h                      # min update interval; optional
  report_unchanged: false           # skip in report when no changes
  diff_mode: ndiff                  # diff mode (unified, ndiff, context)

Interval
^^^^^^^^
Interval can be defined as:

* number = seconds 
* number with prefix:

  * "m" = minutes
  * "h" = hours
  * "d" = days
  * "w" = weeks

Filters
^^^^^^^

`html2text`
  Convert html to plain text; options:

  * `width` - maximum text width (wrapping)

`strip`
  Remove white spaces from beginning and ending of each line; remove blank
  lines

`get-elements-by-xpath`
  Find all elements in html/xml by xpath defined in parameter `xpath`.

`get-elements-by-css`
  Find all elements in html/xml by css selector defined in parameter `sel`.

`get-elements-by-id`
  Find all elements in html/xml by ID defined in parameter `sel`.


Licence
-------

Copyright (c) Karol Będkowski, 2016

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

For details please see COPYING file.
