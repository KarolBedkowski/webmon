WebMon ver 0.x
==============

Monitor changes on web pages, command results.
Write result to local file or send mail.

Inspired by https://github.com/thp/urlwatch

Dependences
-----------

* Python 3.0+
* requests 
* yaml
* html2text (for html2text filter)
* docutils (for html output/reports/mails)
* ElementTree (for get-elements-* filters)
* feedparser (for rss input)

Usage
-----

1. create two config files:
   config.yaml - define outputs, smtp etc;
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
--abilities             show available inputs, outputs, filters, comparators


Configuration
-------------
Configuration files may me placed in current dir, ~/.config/webmon/ direcrtory
or direct specified by appropriate option.

config.yaml
^^^^^^^^^^^
Define program configuration and global / common options.
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
Define one or more data sources (each source separated by `---` line)

Web sources::

  kind: url
  url: https://foo.bar/           # url to monitor; required
  name: date                        # name of input

Command sources::

  kind: cmd
  cmd: date       # command to launch
  name: date

Rss sources::

  kind: rss
  url: http://foo.bar/rss.xml
  name: foo bar rss feed
  max_items: 100   # optionally limit numbers of items
  html2text: true  # optionally clean content from html tags
  field: title, updated_parsed, published_parsed, link, author, content
     # optionally specify fields to show
  

Common options::

  filters:                          # list of filters
      - name: get-elements-by-css   # name of filter
        sel: .link a                # filter parameters
      - name: html2text             # other filter
      - name: strip
  interval: 1h                      # min update interval; optional
  report_unchanged: false           # skip in report when no changes
  diff_mode: ndiff                  # diff mode (unified, ndiff, etc.)

**Interval**
Interval can be defined as:

* number = seconds 
* number with prefix:

  * "m" = minutes
  * "h" = hours
  * "d" = days
  * "w" = weeks

**diff_mode**
Available modes:

* `context_diff` - context diff
* `unified_diff` - unified diff
* `ndiff`   - ndiff (default)
* `added`   - show only new items
* `deleted` - show only deleted items
* `modified`- make diff and return only modified items
* `last`    - return last (current) items

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

`sort`
  Sort elements.

`grep`
  Grep elements by `pattern` - regular expressions.

`wrap`
  Wrap long lines to `width` characters (default 76) and optionally limit 
  number of lines to `max_lines`.

`split`
  Split input to lines on `separator` and (optioanl) `max_split` lines.

`de-csv`
  Convert lines in csv-format to lines. Options: `delimiter`, `quote_char`,
  `strip` (remove whitespaces) and `generate_parts` (generate parts instead
  of lines)


**Common options**

`mode`
  Apply filter to given item:

  * parts - apply filter for each part from input (default)
  * lines - for each part - split into lines and apply filter for each line.

    
Customizations
--------------
User my define own filters, inputs, outputs and comparators by creating .py
file in ~/.local/share/webmon and creating subclass of:

* webmon.filters.AbstractFilter
* webmon.inputs.AbstractInput
* webmon.outputs.AbstractOutput
* webmon.comparators.AbstractComparator


Licence
-------

Copyright (c) Karol Będkowski, 2016

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

For details please see COPYING file.
