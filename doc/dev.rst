webmon ver 2.x - dev doc
========================


Model
-----

`Source` - source configuration; not modified (usually) when loading data.

`SourceState` - source state updated after every data loading.

`SourceGroup` - group sources; every source must belong to one and only on
group.

`Entry` - one entry created by `Source`.

`Settings` - user settings applied over global settings.

`User` - system user

`ScoringSett` - user configuration - score rules



Source
------

`Source.settings[web_url]` or `Source.settings['url']` is used as "Page URL"
and presented in entries and sources;
