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
import time
import json

import requests

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

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

    def __init__(self, ctx: common.Context):
        super(AbstractInput, self).__init__()
        assert isinstance(ctx, common.Context)
        self._ctx = ctx
        self._conf = common.apply_defaults(
            {key: val for key, _, val, _ in self.params},
            ctx.conf)

    def validate(self):
        """ Validate input configuration """
        for name, _, _, required in self.params or []:
            val = self._conf.get(name)
            if required and val is None:
                raise common.ParamError("missing parameter " + name)

    def load(self):
        """ Load data; return list/generator of items (parts).  """
        raise NotImplementedError()

    def need_update(self):
        """ Check last update time and return True if input need update."""
        if not self._ctx.last_updated:
            return True

        # default - check interval
        interval = self._conf["interval"]
        if not interval:
            return True

        interval = common.parse_interval(interval)
        return self._ctx.last_updated + interval < time.time()


class WebInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "url"
    params = AbstractInput.params + [
        ("url", "Web page url", None, True),
        ("timeout", "loading timeout", 30, True),
    ]

    def load(self):
        """ Return one part - page content. """
        ctx = self._ctx
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if ctx.last_updated:
            headers['If-Modified-Since'] = email.utils.formatdate(
                ctx.last_updated)
        url = self._conf['url']
        ctx.log_debug("WebInput: loading url: %s; headers: %r", url, headers)
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers,
                                        timeout=self._conf['timeout'])
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
        ctx.log_debug("WebInput: load done")


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
        ctx = self._ctx
        feedparser.PARSE_MICROFORMATS = 0
        feedparser.USER_AGENT = "Mozilla/5.0 (X11; Linux i686; rv:45.0) " \
                                 "Gecko/20100101 Firefox/45.0"
        modified = time.localtime(ctx.last_updated) \
            if ctx.last_updated else None
        url = self._conf['url']
        etag = ctx.metadata.get('etag')
        ctx.log_debug("RssInput: loading from %s, etag=%r, modified=%r",
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
            ctx.log_error("load document error %s: %s", status, doc)
            summary = "Loading page error: %s" % status
            feed = doc.get('feed')
            if feed:
                summary = feed.get('summary') or summary
            raise common.InputError(summary)

        entries = doc.get('entries')

        # limit number of entries
        max_items = self._conf["max_items"]
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
            ctx.metadata['etag'] = etag
        ctx.log_debug("RssInput: loading done")

    def _load_entry(self, entry, fields, add_content):
        res = "\n\n".join(_get_val_from_rss_entry(entry, fields))
        if add_content:
            content = _get_content_from_rss_entry(entry)
            if content:
                if self._conf["html2text"]:
                    try:
                        import html2text as h2t
                        content = h2t.HTML2Text(bodywidth=9999999)\
                            .handle(content)
                    except ImportError:
                        self._ctx.log_error(
                            "RssInput: loading HTML2Text error "
                            "(module not found)")
                res += "\n\n" + content.strip()
        return res

    def _get_fields_to_load(self):
        add_content = False
        fields = (field.strip() for field in self._conf["fields"].split(","))
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
        conf = self._conf
        ctx = self._ctx
        ctx.log_debug("CmdInput: execute: %r", conf['cmd'])
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
        ctx.log_debug("CmdInput: loading done")


def get_input(ctx):
    """ Get input class according to configuration """
    kind = ctx.conf.get("kind") or "url"
    scls = common.find_subclass(AbstractInput, kind)
    if scls:
        inp = scls(ctx)
        inp.validate()
        return inp

    ctx.log_error("unknown input kind: %s; skipping input", kind)


def _github_check_repo_updated(repository, last_updated):
    modified = time.time() - _GITHUB_MAX_AGE
    if last_updated:
        if repository.updated_at.timestamp() < last_updated:
            raise common.NotModifiedError()
        if last_updated > modified:
            modified = last_updated

    modified = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                             time.localtime(modified))
    return modified


def _github_get_repository(conf):
    try:
        import github3
    except ImportError:
        raise common.InputError("github3 module not found")
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
    return repository


class GithubInput(AbstractInput):
    """Load last commits from github."""

    name = "github_commits"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("short_list", "show commits as short list", True, False),
        ("full_message", "show commits whole commit body", False, False),
    ]

    def load(self):
        """Return commits."""
        conf = self._conf
        ctx = self._ctx
        repository = _github_get_repository(conf)
        modified = _github_check_repo_updated(repository, ctx.last_updated)
        if hasattr(repository, "commits"):
            commits = list(repository.commits(since=modified))
        else:
            etag = ctx.metadata.get('etag')
            commits = list(repository.iter_commits(since=modified,
                                                   etag=etag))
        if len(commits) == 0:
            ctx.log_debug("GithubInput: not updated - co commits")
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

        # add header
        ctx.metadata['etag'] = repository.etag
        ctx.opt['header'] = "https://www.github.com/{}/{}/".format(
            conf["owner"], conf["repository"])
        ctx.log_debug("GithubInput: loading done")


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


class GithubTagsInput(AbstractInput):
    """Load last tags from github."""

    name = "github_tags"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("max_items", "Maximal number of tags to load", None, False),
        ("short_list", "show commits as short list", True, False),
    ]

    def load(self):
        """Return commits."""
        conf = self._conf
        ctx = self._ctx
        repository = _github_get_repository(conf)
        _github_check_repo_updated(repository, ctx.last_updated)

        etag = ctx.metadata.get('etag')
        max_items = self._conf["max_items"] or 100
        if hasattr(repository, "tags"):
            tags = list(repository.tags(max_items, etag=etag))
        else:
            tags = list(repository.iter_tags(max_items, etag=etag))
        if len(tags) == 0:
            ctx.log_debug("GithubInput: not updated - no new tags")
            raise common.NotModifiedError()
        short_list = conf.get("short_list")
        try:
            if short_list:
                yield '\n'.join(_format_gh_tag(tag) for tag in tags)
            else:
                for tag in tags:
                    yield _format_gh_tag(tag)
        except Exception as err:
            raise common.InputError(err)

        # add header
        ctx.metadata['etag'] = repository.etag
        ctx.opt['header'] = "https://www.github.com/{}/{}/".format(
            conf["owner"], conf["repository"])
        ctx.log_debug("GithubTagsInput: loading done")


def _format_gh_tag(tag):
    if tag.last_modified:
        return tag.name + " " + str(tag.last_modified)
    return tag.name


class GithubReleasesInput(AbstractInput):
    """Load last releases from github."""

    name = "github_releases"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("max_items", "Maximal number of releases to load", None, False),
        ("short_list", "show commits as short list", True, False),
        ("full_message", "show commits whole commit body", False, False),
    ]

    def load(self):
        """Return releases."""
        conf = self._conf
        ctx = self._ctx
        repository = _github_get_repository(conf)
        _github_check_repo_updated(repository, ctx.last_updated)
        etag = ctx.metadata.get('etag')
        max_items = self._conf["max_items"] or 100
        if hasattr(repository, "releases"):
            releases = list(repository.releases(max_items, etag=etag))
        else:
            releases = list(repository.iter_releases(max_items, etag=etag))
        if len(releases) == 0:
            ctx.log_debug("GithubInput: not updated - no new releases")
            raise common.NotModifiedError()
        short_list = conf.get("short_list")
        full_message = conf.get("full_message") and not short_list
        try:
            if short_list:
                yield '\n'.join(_format_gh_release(release, False)
                                for release in releases)
            else:
                for release in releases:
                    yield _format_gh_release(release, full_message)
        except Exception as err:
            raise common.InputError(err)

        # add header
        ctx.metadata['etag'] = repository.etag
        ctx.opt['header'] = "https://www.github.com/{}/{}/".format(
            conf["owner"], conf["repository"])
        ctx.log_debug("GithubTagsInput: loading done")


def _format_gh_release(release, full_message):
    res = [release.name, '  ',
           release.created_at.strftime("%x %X")]
    if release.body and full_message:
        res.append("\n")
        res.append(release.body.strip())
    return "".join(res)


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
        ctx = self._ctx
        conf = self._conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if not (conf.get("artist_id") or conf.get("artist")):
            raise common.ParamError(
                "missing parameter 'artist' or 'artist_id'")

        last_updated = time.time() - _JAMENDO_MAX_AGE
        if ctx.last_updated and ctx.last_updated > last_updated:
            last_updated = ctx.last_updated

        url = _jamendo_build_service_url(conf, last_updated)

        ctx.log_debug("JamendoAlbumsInput: loading url: %s", url)
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

        if res['headers']['status'] != 'success':
            response.close()
            raise common.InputError(res['headers']['error_message'])

        if conf.get('short_list'):
            yield from _jamendo_format_short_list(res['results'])
        else:
            yield from _jamendo_format_long_list(res['results'])

        response.close()
        ctx.log_debug("JamendoAlbumsInput: load done")


def _jamendo_build_service_url(conf, last_updated):
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
    return url


def _jamendo_album_to_url(album):
    return 'https://www.jamendo.com/album/{}/'.format(album['id'])


def _jamendo_format_short_list(results):
    for result in results:
        yield "\n".join(
            " ".join((album['releasedate'], album["name"],
                      _jamendo_album_to_url(album)))
            for album in result.get('albums') or [])


def _jamendo_format_long_list(results):
    for result in results:
        for album in result.get('albums') or []:
            yield " ".join((album['releasedate'], album["name"],
                            _jamendo_album_to_url(album)))
