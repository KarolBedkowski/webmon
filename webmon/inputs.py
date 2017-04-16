#!/usr/bin/python3
"""
Standard inputs classes.
Input generate some content according to given configuration (i.e. download it
from internet).

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import email.utils
import json
import subprocess
import time
import typing as ty

import requests
# import typecheck as tc

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

_GITHUB_MAX_AGE = 86400 * 90  # 90 days
_JAMENDO_MAX_AGE = 86400 * 90  # 90 days


class AbstractInput(object):
    """ Abstract/Base class for all inputs """

    # name used in configuration
    name = None  # type: ty.Optional[str]
    # parameters - list of tuples (name, description, default, required)
    params = [
        ("name", "input name", None, False),
        ("interval", "update interval", None, False),
        ("report_unchanged", "report data even is not changed", False, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def __init__(self, ctx: common.Context) -> None:
        super().__init__()
        assert isinstance(ctx, common.Context)
        self._ctx = ctx
        self._conf = common.apply_defaults(
            {key: val for key, _name, val, _req in self.params},
            ctx.input_conf)

    def dump_debug(self):
        return " ".join(("<", self.__class__.__name__, self.name,
                         repr(self._conf), ">"))

    def validate(self):
        """ Validate input configuration """
        for name, _, _, required in self.params or []:
            val = self._conf.get(name)
            if required and val is None:
                raise common.ParamError("missing parameter " + name)

    def load(self) -> common.Result:
        """ Load data; return list of items (Result).  """
        raise NotImplementedError()

    def need_update(self) -> bool:
        """ Check last update time and return True if input need update."""
        if not self._ctx.last_updated:
            return True

        # default - check interval
        interval = self._conf["interval"]
        if not interval:
            return True

        interval = common.parse_interval(interval)
        return self._ctx.last_updated + interval < time.time()

    def next_update(self) -> int:
        if not self._ctx.last_updated:
            return 0

        interval = self._conf["interval"]
        if not interval:
            return 0

        interval = common.parse_interval(interval)
        return self._ctx.last_updated + interval


class WebInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "url"
    params = AbstractInput.params + [
        ("url", "Web page url", None, True),
        ("timeout", "loading timeout", 30, True),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def load(self) -> common.Result:
        """ Return one part - page content. """
        ctx = self._ctx
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if ctx.last_updated:
            headers['If-Modified-Since'] = email.utils.formatdate(
                float(ctx.last_updated))
        url = self._conf['url']
        ctx.log_debug("WebInput: loading url: %s; headers: %r", url, headers)
        result = common.Result(ctx.oid, ctx.input_idx)
        result.link = url
        response = None
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers,
                                        timeout=self._conf['timeout'])
            if not response:
                result.set_error("no result")
                return result
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            result.set_error("timeout")
            if response:
                response.close()
            return result
        except Exception as err:
            result.set_error(err)
            if response:
                response.close()
            return result

        if response.status_code == 304:
            result.set_no_modified("304 code")
            response.close()
            return result

        if response.status_code != 200:
            msg = "Response code: %d" % response.status_code
            if response.text:
                msg += "\n" + response.text
            response.close()
            result.set_error(msg)
            return result

        result.append(response.text)
        response.close()
        ctx.log_debug("WebInput: load done")
        return result


_RSS_DEFAULT_FIELDS = "title, updated_parsed, published_parsed, link, author"


class RssInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "rss"
    params = AbstractInput.params + [
        ("url", "RSS xml url", None, True),
        ("max_items", "Maximal number of articles to load", None, False),
        ("html2text", "Convert html content to plain text", False, False),
        ("fields", "Fields to load from rss", _RSS_DEFAULT_FIELDS, True),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def load(self):
        """ Return rss items as one or many parts; each part is on article. """
        try:
            import feedparser
        except ImportError:
            raise common.InputError(self, "feedparser module not found")
        ctx = self._ctx
        feedparser.PARSE_MICROFORMATS = 0
        feedparser.USER_AGENT = "Mozilla/5.0 (X11; Linux i686; rv:45.0) " \
                                "Gecko/20100101 Firefox/45.0"
        modified = time.localtime(ctx.last_updated) \
            if ctx.last_updated else None
        url = self._conf['url']
        result = common.Result(ctx.oid, ctx.input_idx)
        result.link = url
        etag = result.meta['etag'] = ctx.metadata.get('etag')
        ctx.log_debug("RssInput: loading from %s, etag=%r, modified=%r",
                      url, etag, modified)
        doc = feedparser.parse(url, etag=etag, modified=modified)
        status = doc.get('status') if doc else 400
        if status == 304:
            result.set_no_modified("304 code")
            return result
        if status == 301:  # permanent redirects
            result.append('Permanently redirects: ' + doc.href)
            return result
        if status == 302:
            result.append('Temporary redirects: ' + doc.href)
            return result
        if status != 200:
            ctx.log_error("load document error %s: %s", status, doc)
            summary = "Loading page error: %s" % status
            feed = doc.get('feed')
            if feed:
                summary = feed.get('summary') or summary
            result.set_error(summary)
            return result

        entries = doc.get('entries')

        if len(entries) == 0 and ctx.last_updated:
            result.set_no_modified("no items")
            return result

        # limit number of entries
        max_items = self._conf["max_items"]
        limited = False
        if max_items and len(entries) > max_items:
            entries = entries[:max_items]
            limited = True

        fields, add_content = self._get_fields_to_load()
        # parse entries
        result.items.extend(self._load_entry(entry, fields, add_content)
                            for entry in entries)

        result.footer = ("Loaded only last %d items" % max_items
                         if limited else "All items loaded")

        # update metadata
        result.meta['etag'] = doc.get('etag')
        ctx.log_debug("RssInput: loading done")
        return result

    def _load_entry(self, entry, fields, add_content):
        res = list(_get_val_from_rss_entry(entry, fields))
        if add_content:
            content = _get_content_from_rss_entry(entry)
            if content:
                if self._conf["html2text"]:
                    try:
                        import html2text as h2t
                        content = h2t.HTML2Text(bodywidth=74).handle(content)
                    except ImportError:
                        self._ctx.log_error(
                            "RssInput: loading HTML2Text error "
                            "(module not found)")
                res.append("")
                res.extend("    " + line.strip()
                           for line in content.strip().split("\n"))
        self._ctx.log_debug(repr(res))
        return "\n".join(res).strip()

    def _get_fields_to_load(self) -> ty.Tuple[ty.Iterable[str], bool]:
        add_content = False
        cfields = (field.strip() for field in self._conf["fields"].split(","))
        fields = [field for field in cfields if field]
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
    first_val = True
    for key in keys:
        if not key:
            continue
        val = entry.get(key)
        if val:
            name = key.split("_", 1)[0].capitalize().strip()
            if not first_val:
                name = "    " + name
            if isinstance(val, time.struct_time):
                yield name + ": " + time.strftime("%x %X", val)
            else:
                yield name + ": " + str(val).strip()
            yield ""
            first_val = False


class CmdInput(AbstractInput):
    """Load data from command"""

    name = "cmd"
    params = AbstractInput.params + [
        ("cmd", "Command to run", None, True),
        ("split", "Split content", False, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def load(self) -> common.Result:
        """ Return command output as one part
        Returns:
            result: command.Result
        """
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
            errstr = errstr.strip()
            return common.Result(ctx.oid, ctx.input_idx).set_error(errstr)

        inp_result = common.Result(ctx.oid, ctx.input_idx)
        if conf['split']:
            inp_result.items = stdout.decode('utf-8').split("\n")
        else:
            inp_result.append(stdout.decode('utf-8'))
        ctx.log_debug("CmdInput: loading done")
        return inp_result


def get_input(ctx):
    """ Get input class according to configuration """
    kind = ctx.input_conf.get("kind") or "url"
    scls = common.find_subclass(AbstractInput, kind)
    if scls:
        inp = scls(ctx)
        inp.validate()
        return inp

    ctx.log_error("unknown input kind: %s; skipping input", kind)


class GitHubMixin(object):
    """Support functions for GitHub"""

    @staticmethod
    def _github_check_repo_updated(repository,
                                   last_updated: ty.Union[int, float, None]) \
            -> ty.Tuple[str, bool]:
        """Verify last repository update date.
        Returns: (
            formatted minimal date to load,
            true when repo is updated
        )
        """
        min_date = time.time() - _GITHUB_MAX_AGE
        updated = True
        if last_updated:
            updated = repository.updated_at.timestamp() > last_updated
            min_date = last_updated

        return (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(min_date)),
                updated)

    def _github_get_repository(self, conf: dict):
        """Create repository object according to configuration. """
        try:
            import github3
        except ImportError:
            raise common.InputError(self, "github3 module not found")
        github = None
        if conf.get("github_user") and conf.get("github_token"):
            try:
                github = github3.login(username=conf.get("github_user"),
                                       token=conf.get("github_token"))
            except Exception as err:
                raise common.InputError(self, "Github auth error: " + str(err))
        if not github:
            github = github3.GitHub()
        repository = github.repository(conf["owner"], conf["repository"])
        return repository


class GithubInput(AbstractInput, GitHubMixin):
    """Load last commits from github."""

    name = "github_commits"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("short_list", "show commits as short list", True, False),
        ("full_message", "show commits whole commit body", False, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def load(self) -> common.Result:
        """Return commits."""
        conf = self._conf
        ctx = self._ctx
        result = common.Result(ctx.oid, ctx.input_idx)
        etag = result.meta['etag'] = ctx.metadata.get('etag')
        repository = self._github_get_repository(conf)
        result.link = repository.html_url
        data_since, updated = self._github_check_repo_updated(
            repository, ctx.last_updated)
        if ctx.debug:
            result.debug['data_since'] = data_since
            result.debug['last_updated'] = ctx.last_updated
            result.debug['repo_updated_at'] = str(repository.updated_at)

        if not updated:
            ctx.log_debug("GithubInput: not updated - co commits")
            result.set_no_modified("not updated")
            return result

        if hasattr(repository, "commits"):
            commits = list(repository.commits(since=data_since))
        else:
            commits = list(repository.iter_commits(since=data_since,
                                                   etag=etag))

        if len(commits) == 0:
            ctx.log_debug("GithubInput: not updated - co commits")
            result.set_no_modified("no items")
            return result

        short_list = conf.get("short_list")
        full_message = conf.get("full_message") and not short_list
        form_fun = _format_gh_commit_short if short_list else \
            _format_gh_commit_long
        try:
            result.items = [form_fun(commit, full_message)
                            for commit in commits]
        except Exception as err:
            result.set_error(err)
            return result

        # add header
        result.meta['etag'] = repository.etag
        ctx.log_debug("GithubInput: loading done")
        return result


def _format_gh_commit_short(commit, _full_message: bool) -> str:
    return (commit.commit.committer['date'] + " " +
            commit.commit.message.strip().split("\n", 1)[0].rstrip())


def _format_gh_commit_long(commit, full_message: bool) -> str:
    cmt = commit.commit
    result = [cmt.committer['date'],
              "\n\n    Author: ", cmt.author['name'], "\n'n"]
    msg = cmt.message.strip()
    if not full_message:
        msg = msg.split("\n", 1)[0].strip()
    result.extend("   " + line + "\n" for line in msg.split("\n"))
    return "".join(result)


class GithubTagsInput(AbstractInput, GitHubMixin):
    """Load last tags from github."""

    name = "github_tags"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("max_items", "Maximal number of tags to load", None, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def load(self):
        """Return commits."""
        conf = self._conf
        ctx = self._ctx
        result = common.Result(ctx.oid, ctx.input_idx)
        etag = result.meta['etag'] = ctx.metadata.get('etag')
        repository = self._github_get_repository(conf)
        result.link = repository.html_url
        data_since, updated = self._github_check_repo_updated(
            repository, ctx.last_updated)
        if ctx.debug:
            result.debug['data_since'] = data_since
            result.debug['last_updated'] = ctx.last_updated
            result.debug['repo_updated_at'] = str(repository.updated_at)

        if not updated:
            ctx.log_debug("GithubInput: not updated - co commits")
            result.set_no_modified("not updated")
            return result

        max_items = self._conf["max_items"] or 100
        if hasattr(repository, "tags"):
            tags = list(repository.tags(max_items, etag=etag))
        else:
            tags = list(repository.iter_tags(max_items, etag=etag))

        if len(tags) == 0:
            ctx.log_debug("GithubInput: not updated - no new tags")
            result.set_no_modified("no items")
            return result

        try:
            result.items.extend(_format_gh_tag(tag) for tag in tags)
        except Exception as err:
            raise common.InputError(self, err)

        # add header
        result.meta['etag'] = repository.etag
        ctx.log_debug("GithubTagsInput: loading done")
        return result


def _format_gh_tag(tag):
    if tag.last_modified:
        return tag.name + " " + str(tag.last_modified)
    return tag.name


class GithubReleasesInput(AbstractInput, GitHubMixin):
    """Load last releases from github."""

    name = "github_releases"
    params = AbstractInput.params + [
        ("owner", "repository owner", None, True),
        ("repository", "repository name", None, False),
        ("github_user", "user login", None, False),
        ("github_token", "user personal token", None, False),
        ("max_items", "Maximal number of releases to load", None, False),
        ("full_message", "show commits whole commit body", False, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def load(self):
        """Return releases."""
        conf = self._conf
        ctx = self._ctx
        result = common.Result(ctx.oid, ctx.input_idx)
        etag = result.meta['etag'] = ctx.metadata.get('etag')
        repository = self._github_get_repository(conf)
        result.link = repository.html_url
        data_since, updated = self._github_check_repo_updated(
            repository, ctx.last_updated)
        if ctx.debug:
            result.debug['data_since'] = data_since
            result.debug['last_updated'] = ctx.last_updated
            result.debug['repo_updated_at'] = str(repository.updated_at)

        if not updated:
            ctx.log_debug("GithubInput: not updated - co commits")
            result.set_no_modified("not updated")
            return result

        max_items = self._conf["max_items"] or 100
        if hasattr(repository, "releases"):
            releases = list(repository.releases(max_items, etag=etag))
        else:
            releases = list(repository.iter_releases(max_items, etag=etag))

        if len(releases) == 0:
            ctx.log_debug("GithubInput: not updated - no new releases")
            result.set_no_modified("no items")
            return result

        short_list = conf.get("short_list")
        full_message = conf.get("full_message") and not short_list
        try:
            form_fun = _format_gh_release_short if short_list else \
                _format_gh_release_long
            result.items.extend(form_fun(release, full_message)
                                for release in releases)
        except Exception as err:
            result.set_error(err)
            return result

        # add header
        result.meta['etag'] = repository.etag
        ctx.log_debug("GithubTagsInput: loading done")
        return result


def _format_gh_release_short(release, _full_message):
    res = [release.name, release.created_at.strftime("%x %X")]
    if release.html_url:
        res.append(release.html_url)
    if release.body:
        res.append(release.body().strip().split('\n', 1)[0].rstrip())
    return " ".join(res)


def _format_gh_release_long(release, full_message):
    res = [release.name,
           '\n\n    Date: ', release.created_at.strftime("%x %X")]
    if release.html_url:
        res.append('\n\n    ')
        res.append(release.html_url)
    if release.body and full_message:
        res.append('\n\n')
        res.extend('   ' + line.strip()
                   for line in release.body.strip().split('\n'))
    return "".join(res)


class JamendoAlbumsInput(AbstractInput):
    """Load data from jamendo - new albums"""

    name = "jamendo_albums"
    params = AbstractInput.params + [
        ("artist_id", "artist id", None, False),
        ("artist", "artist name", None, False),
        ("jamendo_client_id", "jamendo client id", None, True),
        ("short_list", "show compact list", True, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

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

        result = common.Result(ctx.oid, ctx.input_idx)
        ctx.log_debug("JamendoAlbumsInput: loading url: %s", url)
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            response.set_error("timeout")
            return
        except Exception as err:
            response.set_error(err)
            return

        if response.status_code == 304:
            response.close()
            result.set_no_modified("304 code")
            return result

        if response.status_code != 200:
            msg = "Response code: %d" % response.status_code
            if response.text:
                msg += "\n" + response.text
            response.close()
            response.set_error(msg)
            return response

        res = json.loads(response.text)

        if res['headers']['status'] != 'success':
            response.close()
            raise common.InputError(self, res['headers']['error_message'])

        if conf.get('short_list'):
            result.items.extend(_jamendo_format_short_list(res['results']))
        else:
            result.items.extend(_jamendo_format_long_list(res['results']))

        response.close()
        ctx.log_debug("JamendoAlbumsInput: load done")
        return result


def _jamendo_build_service_url(conf, last_updated):
    last_updated = time.strftime("%Y-%m-%d",
                                 time.localtime(last_updated))
    today = time.strftime("%Y-%m-%d")
    artist = (("name=" + conf["artist"]) if conf.get('artist')
              else ("id=" + str(conf["artist_id"])))
    url = 'https://api.jamendo.com/v3.0/artists/albums?'
    url += '&'.join(("client_id=" + conf.get('jamendo_client_id', ''),
                     "format=json&order=album_releasedate_desc",
                     artist,
                     "album_datebetween=" + last_updated + "_" + today))
    return url


def _jamendo_album_to_url(album_id):
    if not album_id:
        return ''
    return 'https://www.jamendo.com/album/{}/'.format(album_id)


def _jamendo_format_short_list(results):
    for result in results:
        yield "\n".join(
            " ".join((album['releasedate'], album["name"],
                      _jamendo_album_to_url(album['id'])))
            for album in result.get('albums') or [])


def _jamendo_format_long_list(results):
    for result in results:
        for album in result.get('albums') or []:
            yield " ".join((album['releasedate'], album["name"],
                            _jamendo_album_to_url(album['id'])))


class JamendoTracksInput(AbstractInput):
    """Load data from jamendo - new tracks for artists"""

    name = "jamendo_tracks"
    params = AbstractInput.params + [
        ("artist_id", "artist id", None, False),
        ("artist", "artist name", None, False),
        ("jamendo_client_id", "jamendo client id", None, True),
        ("short_list", "show compact list", True, False),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

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

        url = _jamendo_build_service_url_tracks(conf, last_updated)

        result = common.Result(ctx.oid, ctx.input_idx)
        ctx.log_debug("JamendoTracksInput: loading url: %s", url)
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            response.set_error("timeout")
            return
        except Exception as err:
            response.set_error(err)
            return

        if response.status_code == 304:
            response.close()
            result.set_no_modified("304 code")
            return result

        if response.status_code != 200:
            msg = "Response code: %d" % response.status_code
            if response.text:
                msg += "\n" + response.text
            response.close()
            response.set_error(msg)
            return response

        res = json.loads(response.text)

        if res['headers']['status'] != 'success':
            response.close()
            raise common.InputError(self, res['headers']['error_message'])

        if conf.get('short_list'):
            result.items.extend(
                _jamendo_track_format_short_list(res['results']))
        else:
            result.items.extend(
                _jamendo_track_format_long_list(res['results']))

        response.close()
        ctx.log_debug("JamendoTrackInput: load done")
        return result


def _jamendo_build_service_url_tracks(conf, last_updated):
    last_updated = time.strftime("%Y-%m-%d",
                                 time.localtime(last_updated))
    today = time.strftime("%Y-%m-%d")
    artist = (("name=" + conf["artist"]) if conf.get('artist')
              else ("id=" + str(conf["artist_id"])))
    url = 'https://api.jamendo.com/v3.0/artists/tracks?'
    url += '&'.join(("client_id=" + conf.get('jamendo_client_id', ''),
                     "format=json&order=track_releasedate_desc",
                     artist,
                     "album_datebetween=" + last_updated + "_" + today))
    return url


def _jamendo_track_to_url(track_id):
    if not track_id:
        return ''
    return 'https://www.jamendo.com/track/{}/'.format(track_id)


def _jamendo_track_format_short_list(results):
    for result in results:
        yield "\n".join(
            " ".join((track['releasedate'], track["name"],
                      _jamendo_track_to_url(track['id'])))
            for track in result.get('tracks') or [])


def _jamendo_track_format_long_list(results):
    for result in results:
        for track in result.get('tracks') or []:
            res_track = [track['releasedate'], track["name"],
                         _jamendo_track_to_url(track['id'])]
            album = track.get('album_id')
            if album:
                res_track.append(" (" + track['album_name'] +
                                 _jamendo_album_to_url(track['album_id']))

            yield " ".join(res_track)
