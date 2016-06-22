#!/usr/bin/python3
"""
Standard inputs classes.
Input generate some content according to given configuration (i.e. download it
from internet).

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import subprocess
import email.utils
import logging
import time
import json

import requests

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

_LOG = logging.getLogger("inputs")
_GITHUB_MAX_AGE = 86400 * 90  # 90 days
_JAMENDO_MAX_AGE = 86400 * 90  # 90 days


class AbstractInput(object):
    """ Abstract/Base class for all inputs """

    # name used in configuration
    name = None
    # parameters - list of tuples (name, description, default, required)
    params = [
        ("name", "input name", None, False),
        ("interval", "update interval", None, False),
        ("report_unchanged", "report data even is not changed", False, False),
    ]

    def __init__(self, conf):
        super(AbstractInput, self).__init__()
        self.conf = {key: val for key, _, val, _ in self.params}
        self.conf.update(conf)

    @property
    def last_updated(self):
        """ Helper - get last_updated from context """
        return self.conf.get('_last_updated')

    def validate(self):
        """ Validate input configuration """
        for name, _, _, required in self.params or []:
            val = self.conf.get(name)
            if required and not val:
                raise common.ParamError("missing parameter " + name)

    def load(self):
        """ Load data; return list/generator of items (parts).  """
        raise NotImplementedError()

    def need_update(self):
        """ Check last update time and return True if input need update."""
        last = self.last_updated
        if not last:
            return True
        # default - check interval
        interval = self.conf["interval"]
        if not interval:
            return True
        interval = common.parse_interval(interval)
        return last + interval < time.time()


class WebInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "url"
    params = AbstractInput.params + [
        ("url", "Web page url", None, True),
        ("timeout", "loading timeout", 30, True),
    ]

    def load(self):
        """ Return one part - page content. """
        conf = self.conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if self.last_updated:
            headers['If-Modified-Since'] = email.utils.formatdate(
                self.last_updated)
        url = conf['url']
        _LOG.debug("WebInput: loading url: %s; headers: %r", url, headers)
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers,
                                        timeout=conf['timeout'])
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            raise common.InputError("timeout")
        except Exception as err:
            raise common.InputError(err)
        if response.status_code == 304:
            response.close()
            raise common.NotModifiedError()
        if response.status_code != 200:
            err = "Response code: %d" % response.status_code
            if response.text:
                err += "\n" + response.text
            response.close()
            raise common.InputError(err)
        yield response.text
        response.close()
        _LOG.debug("WebInput: load done")


_RSS_DEFAULT_FIELDS = "title, updated_parsed, published_parsed, link, author"


class RssInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "rss"
    params = AbstractInput.params + [
        ("url", "RSS xml url", None, True),
        ("max_items", "Maximal number of articles to load", None, False),
        ("html2text", "Convert html content to plain text", False, False),
        ("fields", "Fields to load from rss", _RSS_DEFAULT_FIELDS, True),
    ]

    def load(self):
        """ Return rss items as one or many parts; each part is on article. """
        try:
            import feedparser
        except ImportError:
            raise common.InputError("feedparser module not found")
        feedparser.PARSE_MICROFORMATS = 0
        feedparser.USER_AGENT = "Mozilla/5.0 (X11; Linux i686; rv:45.0) " \
                                 "Gecko/20100101 Firefox/45.0"
        conf = self.conf
        modified = time.localtime(self.last_updated) \
            if self.last_updated else None
        url = conf['url']
        etag = self.conf['_metadata'].get('etag')
        _LOG.debug("RssInput: loading from %s, etag=%r, modified=%r",
                   url, etag, modified)
        doc = feedparser.parse(url, etag=etag, modified=modified)
        status = doc.get('status') if doc else 400
        if status == 304:
            raise common.NotModifiedError()
        if status == 301:  # permanent redirects
            yield 'Permanently redirects: ' + doc.href
            return
        if status == 302:
            yield 'Temporary redirects: ' + doc.href
            return
        if status != 200:
            _LOG.error("load document error %s: %s", status, doc)
            summary = "Loading page error: %s" % status
            feed = doc.get('feed')
            if feed:
                summary = feed.get('summary') or summary
            raise common.InputError(summary)

        entries = doc.get('entries')

        # limit number of entries
        max_items = self.conf["max_items"]
        limited = False
        if max_items and len(entries) > max_items:
            entries = entries[:max_items]
            limited = True

        fields, add_content = self._get_fields_to_load()
        # parse entries
        yield from (self._load_entry(entry, fields, add_content)
                    for entry in entries)

        yield "Loaded only last %d items" % max_items if limited \
            else "All items loaded"

        # update metadata
        etag = doc.get('etag')
        if etag:
            self.conf['_metadata']['etag'] = etag
        _LOG.debug("RssInput: loading done")

    def _load_entry(self, entry, fields, add_content):
        res = "\n\n".join(_get_val_from_rss_entry(entry, fields))
        if add_content:
            content = _get_content_from_rss_entry(entry)
            if content:
                if self.conf["html2text"]:
                    try:
                        import html2text as h2t
                        content = h2t.HTML2Text(bodywidth=9999999)\
                            .handle(content)
                    except ImportError:
                        _LOG.warning("RssInput: loading HTML2Text error "
                                     "(module not found)")
                res += "\n\n" + content.strip()
        return res

    def _get_fields_to_load(self):
        add_content = False
        fields = (field.strip() for field in self.conf["fields"].split(","))
        fields = [field for field in fields if field]
        if 'content' in fields:
            fields.remove('content')
            add_content = True
        return fields, add_content


def _get_content_from_rss_entry(entry):
    content = entry.get('summary')
    if not content:
        content = entry['content'][0].value if 'content' in entry \
            else entry.get('value')
    return content


def _get_val_from_rss_entry(entry, keys):
    for key in keys:
        if not key:
            continue
        val = entry.get(key)
        if val:
            name = key.split("_", 1)[0].capitalize()
            if isinstance(val, time.struct_time):
                yield name + ": " + time.strftime("%x %X", val)
            else:
                yield name + ": " + str(val)


class CmdInput(AbstractInput):
    """Load data from command"""

    name = "cmd"
    params = AbstractInput.params + [
        ("cmd", "Command to run", None, True),
        ("split", "Split content", False, False),
    ]

    def load(self):
        """ Return command output as one part """
        conf = self.conf
        _LOG.debug("CmdInput: execute: %r", conf['cmd'])
        process = subprocess.Popen(conf['cmd'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   shell=True)
        stdout, stderr = process.communicate()
        result = process.wait(60)
        if result != 0:
            err = ("Err: " + str(result), (stdout or b"").decode("utf-8"),
                   (stderr or b"").decode('utf-8'))
            errstr = "\n".join(line.strip() for line in err if line)
            raise common.InputError(errstr.strip())

        if conf['split']:
            yield from stdout.decode('utf-8').split("\n")
        else:
            yield stdout.decode('utf-8')
        _LOG.debug("CmdInput: loading done")


def get_input(conf):
    """ Get input class according to configuration """
    kind = conf.get("kind") or "url"
    scls = common.find_subclass(AbstractInput, kind)
    if scls:
        inp = scls(conf)
        inp.validate()
        return inp

    _LOG.warning("unknown input kind: %s; skipping input", kind)


class GithubInput(AbstractInput):
    """Load last commits from github."""

    name = "github_commits"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("short_list", "show commits as short list", True, False),
    ]

    def load(self):
        """Return commits."""
        try:
            import github3
        except ImportError:
            raise common.InputError("github3 module not found")
        conf = self.conf
        github = None
        if conf.get("github_user") and conf.get("github_token"):
            try:
                github = github3.login(username=conf.get("github_user"),
                                       token=conf.get("github_token"))
            except Exception as err:
                raise common.InputError("Github auth error: " + err)
        if not github:
            github = github3.GitHub()
        repository = github.repository(conf["owner"], conf["repository"])
        modified = time.time() - _GITHUB_MAX_AGE
        if self.last_updated:
            if repository.updated_at.timestamp() < self.last_updated:
                _LOG.debug("GithubInput: not updated - repository timestamp")
                raise common.NotModifiedError()
            if self.last_updated > modified:
                modified = self.last_updated
        modified = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                 time.localtime(modified))

        commits = list(repository.commits(since=modified))
        if len(commits) == 0:
            _LOG.debug("GithubInput: not updated - co commits")
            raise common.NotModifiedError()
        short_list = conf.get("short_list")
        full_message = conf.get("full_message") and not short_list
        try:
            if short_list:
                result = [commit.commit.committer['date'] + " " +
                          _format_gh_commit(commit.commit.message, False)
                          for commit in commits]
                yield "\n".join(result)
            else:
                for commit in commits:
                    cmt = commit.commit
                    msg = _format_gh_commit(cmt.message, full_message)
                    yield "".join((cmt.committer['date'], '\n',
                                   msg, '\nAuthor: ',
                                   cmt.author['name'],
                                   cmt.author['date']))
        except Exception as err:
            raise common.InputError(err)

        _LOG.debug("GithubInput: loading done")


def _format_gh_commit(message, full_message):
    msg = message.strip()
    if full_message:
        msg_parts = msg.split("\n", 1)
        msg = msg_parts[0].strip()
        if len(msg_parts) > 1:
            msg += '\n' + msg_parts[1].strip().replace("\n", "")
    else:
        msg = msg.split("\n", 1)[0].strip()
    return msg


class JamendoAlbumsInput(AbstractInput):
    """Load data from jamendo - new albums"""

    name = "jamendo_albums"
    params = AbstractInput.params + [
        ("artist_id", "artist id", None, False),
        ("artist", "artist name", None, False),
        ("jamendo_client_id", "jamendo client id", None, True),
        ("short_list", "show compact list", True, False),
    ]

    def load(self):
        """ Return one part - page content. """
        conf = self.conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if not (conf.get("artist_id") or conf.get("artist")):
            raise common.ParamError("missing parameter 'artist' or 'artist_id'")
        last_updated = time.time() - _JAMENDO_MAX_AGE
        if self.last_updated and self.last_updated > last_updated:
            last_updated = self.last_updated
        last_updated = time.strftime("%Y-%m-%d",
                                     time.localtime(last_updated))
        today = time.strftime("%Y-%m-%d")
        artist = (("name=" + conf["artist"]) if conf.get('artist')
                  else ("id=" + str(conf["artist_id"])))
        url = 'https://api.jamendo.com/v3.0/artists/albums?'
        url += '&'.join(("client_id=" + conf.get('client_id', '56d30c95'),
                         "format=json&order=album_releasedate_desc",
                         artist,
                         "album_datebetween=" + last_updated + "_" + today))
        _LOG.debug("JamendoAlbumsInput: loading url: %s", url)
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            raise common.InputError("timeout")
        except Exception as err:
            raise common.InputError(err)
        if response.status_code == 304:
            response.close()
            raise common.NotModifiedError()
        if response.status_code != 200:
            err = "Response code: %d" % response.status_code
            if response.text:
                err += "\n" + response.text
            response.close()
            raise common.InputError(err)
        res = json.loads(response.text)
        if res['headers']['status'] == 'success':
            if conf.get('short_list'):
                for result in res['results']:
                    yield "\n".join(
                        album['releasedate'] + " " + album["name"]
                        for album in result.get('albums') or [])
            else:
                for result in res['results']:
                    for album in result.get('albums') or []:
                        yield album['releasedate'] + " " + album["name"]
        else:
            response.close()
            raise common.InputError(res['headers']['error_message'])

        response.close()
        _LOG.debug("JamendoAlbumsInput: load done")
