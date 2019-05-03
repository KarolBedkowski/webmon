#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Inputs related to github
"""
import logging
import typing as ty
from datetime import timezone, datetime, timedelta

import github3

from webmon2 import common, model

from .abstract import AbstractSource


_LOG = logging.getLogger(__file__)
_GITHUB_MAX_AGE = 90  # 90 days
_ = ty


class GitHubMixin:
    """Support functions for GitHub"""
    # pylint: disable=too-few-public-methods

    @staticmethod
    def _github_check_repo_updated(
            repository, last_updated: ty.Optional[datetime]) \
            -> ty.Optional[str]:
        """Verify last repository update date.
        Returns: None when repo is not updated or formatted minimal date
            to load
        """
        if not last_updated:
            min_date = datetime.now() - timedelta(days=_GITHUB_MAX_AGE)
            return min_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        if repository.updated_at <= last_updated.replace(tzinfo=timezone.utc):
            return None

        return last_updated.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _github_get_repository(self, conf: dict):
        """Create repository object according to configuration. """
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


class GithubInput(AbstractSource, GitHubMixin):
    """Load last commits from github."""

    name = "github_commits"
    short_info = "Commit history from Github repository"
    long_info = 'Source load commits history from configured repository.' \
        ' For work required configured Github account with token.'
    params = AbstractSource.params + [
        common.SettingDef("owner", "repository owner", required=True),
        common.SettingDef("repository", "repository name", required=True),
        common.SettingDef("github_user", "user login", required=True,
                          global_param=True),
        common.SettingDef("github_token", "user personal token", required=True,
                          global_param=True),
        common.SettingDef("short_list", "show commits as short list",
                          default=True),
        common.SettingDef("full_message", "show commits whole commit body",
                          default=False),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return commits."""
        repository = self._github_get_repository(self._conf)
        data_since = self._github_check_repo_updated(
            repository, state.last_update)
        if not data_since:
            new_state = state.new_not_modified()
            new_state.set_state('etag', repository.etag)
            return new_state, []

        etag = state.get_state('etag')
        if hasattr(repository, "commits"):
            commits = list(repository.commits(since=data_since))
        else:
            commits = list(repository.iter_commits(
                since=data_since, etag=etag))

        if not commits:
            new_state = state.new_not_modified()
            new_state.set_state('etag', repository.etag)
            return new_state, []

        short_list = self._conf.get("short_list")
        full_message = bool(self._conf.get("full_message") and not short_list)
        form_fun = _format_gh_commit_short if short_list else \
            _format_gh_commit_long
        try:
            content = '\n\n'.join(form_fun(commit, full_message)
                                  for commit in commits)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("github load error: %s", err)
            return state.new_error(str(err)), []

        new_state = state.new_ok()
        new_state.set_state('etag', repository.etag)

        entry = model.Entry.for_source(self._source)
        entry.url = repository.html_url
        entry.title = self._source.name
        entry.status = 'new'
        entry.content = content
        entry.created = entry.updated = datetime.now()
        return new_state, [entry]


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


class GithubTagsSource(AbstractSource, GitHubMixin):
    """Load last tags from github."""

    name = "github_tags"
    short_info = "Tags from Github repository"
    long_info = 'Source load tags from configured repository.' \
        ' For work required configured Github account with token.'
    params = AbstractSource.params + [
        common.SettingDef("owner", "repository owner", required=True),
        common.SettingDef("repository", "repository name", required=True),
        common.SettingDef("github_user", "user login", required=True,
                          global_param=True),
        common.SettingDef("github_token", "user personal token", required=True,
                          global_param=True),
        common.SettingDef("max_items", "Maximal number of tags to load",
                          default=100),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return commits."""
        conf = self._conf
        repository = self._github_get_repository(conf)
        if not self._github_check_repo_updated(repository, state.last_update):
            new_state = state.new_not_modified()
            new_state.set_state('etag', repository.etag)
            return new_state, []

        etag = state.get_state('etag')
        max_items = self._conf["max_items"]
        if hasattr(repository, "tags"):
            tags = list(repository.tags(max_items, etag=etag))
        else:
            tags = list(repository.iter_tags(max_items, etag=etag))

        tags = [tag for tag in tags if not tag.last_modified or
                tag.last_modified > state.last_update.replace(
                    tzinfo=timezone.utc)]
        if not tags:
            new_state = state.new_not_modified()
            new_state.set_state('etag', repository.etag)
            return new_state, []

        try:
            content = '\n\n'.join(filter(None, map(_format_gh_tag, tags)))
        except Exception as err:
            _LOG.exception("github load error: %s", err)
            raise common.InputError(self, err)

        new_state = state.new_ok()
        new_state.set_state('etag', repository.etag)

        entry = model.Entry.for_source(self._source)
        entry.url = repository.html_url
        entry.title = self._source.name
        entry.status = 'new'
        entry.content = content
        entry.created = entry.updated = datetime.now()
        return new_state, [entry]


def _format_gh_tag(tag) -> str:
    if tag.last_modified:
        return tag.name + " " + str(tag.last_modified)
    return tag.name


class GithubReleasesSource(AbstractSource, GitHubMixin):
    """Load last releases from github."""

    name = "github_releases"
    short_info = "Releases from Github repository"
    long_info = 'Source load releases history from configured repository.' \
        ' For work required configured Github account with token.'
    params = AbstractSource.params + [
        common.SettingDef("owner", "repository owner", required=True),
        common.SettingDef("repository", "repository name", required=True),
        common.SettingDef("github_user", "user login", required=True,
                          global_param=True),
        common.SettingDef("github_token", "user personal token", required=True,
                          global_param=True),
        common.SettingDef("max_items", "Maximal number of tags to load",
                          value_type=int),
        common.SettingDef("full_message", "show commits whole commit body",
                          default=False),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return releases."""
        repository = self._github_get_repository(self._conf)
        if not self._github_check_repo_updated(
                repository, state.last_update):
            new_state = state.new_not_modified()
            new_state.set_state('etag', repository.etag)
            return new_state, []

        etag = state.get_state('etag')
        max_items = self._conf["max_items"] or 100
        if hasattr(repository, "releases"):
            releases = list(repository.releases(max_items, etag=etag))
        else:
            releases = list(repository.iter_releases(max_items, etag=etag))

        releases = [
            release for release in releases
            if release.created_at > state.last_update.replace(
                tzinfo=timezone.utc)
        ]

        if not releases:
            new_state = state.new_not_modified()
            new_state.set_state('etag', repository.etag)
            return new_state, []

        short_list = self._conf.get("short_list")
        full_message = bool(self._conf.get("full_message") and not short_list)
        try:
            form_fun = _format_gh_release_short if short_list else \
                _format_gh_release_long
            content = '\n\n'.join(form_fun(release, full_message)
                                  for release in releases)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("github load error %s", err)
            return state.new_error(str(err)), []

        new_state = state.new_ok()
        new_state.set_state('etag', repository.etag)

        entry = model.Entry.for_source(self._source)
        entry.url = repository.html_url
        entry.title = self._source.name
        entry.status = 'new'
        entry.content = content
        entry.created = entry.updated = datetime.now()
        return new_state, [entry]


def _format_gh_release_short(release, _full_message) -> str:
    res = [release.name, release.tag_name,
           release.created_at.strftime("%x %X")]
    if release.html_url:
        res.append(release.html_url)
    if release.body:
        res.append(release.body().strip().split('\n', 1)[0].rstrip())
    return " ".join(map(str, filter(None, res)))


def _format_gh_release_long(release, full_message: bool) -> str:
    res = [release.name, release.tag_name,
           '\n\n    Date: ', release.created_at.strftime("%x %X")]
    if release.html_url:
        res.append('\n\n    ')
        res.append(release.html_url)
    if release.body and full_message:
        res.append('\n\n')
        res.extend('   ' + line.strip()
                   for line in release.body.strip().split('\n'))
    return " ".join(map(str, filter(None, res)))
