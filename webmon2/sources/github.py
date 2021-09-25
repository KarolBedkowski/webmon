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
from datetime import datetime, timedelta

import github3
from dateutil import tz

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
_GITHUB_MAX_AGE = 90  # 90 days
_GITHUB_ICON = "https://github.com/favicon.ico"
_ = ty


class GitHubMixin:
    """Support functions for GitHub"""

    # pylint: disable=too-few-public-methods

    @staticmethod
    def _github_check_repo_updated(
        repository, last_updated: ty.Optional[datetime]
    ) -> ty.Optional[str]:
        """Verify last repository update date.
        Returns: None when repo is not updated or formatted minimal date
            to load
        """
        if not last_updated:
            min_date = datetime.now() - timedelta(days=_GITHUB_MAX_AGE)
            return min_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        if repository.updated_at <= last_updated.replace(tzinfo=tz.tzlocal()):
            return None

        return last_updated.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _github_get_repository(self, conf: dict):
        """Create repository object according to configuration."""
        github = None
        if conf.get("github_user") and conf.get("github_token"):
            try:
                github = github3.login(
                    username=conf.get("github_user"),
                    token=conf.get("github_token"),
                )
            except Exception as err:
                raise common.InputError(self, "Github auth error: " + str(err))
        if not github:
            github = github3.GitHub()
        repository = github.repository(conf["owner"], conf["repository"])
        return repository


def _build_entry(
    source: model.Source, repository, content: str
) -> model.Entry:
    entry = model.Entry.for_source(source)
    entry.url = repository.html_url
    entry.title = source.name
    entry.status = "new"
    entry.content = content
    entry.created = entry.updated = datetime.now()
    entry.set_opt("content-type", "markdown")
    return entry


class GithubInput(AbstractSource, GitHubMixin):
    """Load last commits from github."""

    name = "github_commits"
    short_info = "Commit history from Github repository"
    long_info = (
        "Source load commits history from configured repository."
        " For work required configured Github account with token."
    )
    params = AbstractSource.params + [
        common.SettingDef("owner", "repository owner", required=True),
        common.SettingDef("repository", "repository name", required=True),
        common.SettingDef(
            "github_user", "user login", required=True, global_param=True
        ),
        common.SettingDef(
            "github_token",
            "user personal token",
            required=True,
            global_param=True,
        ),
        common.SettingDef(
            "short_list", "show commits as short list", default=True
        ),
        common.SettingDef(
            "full_message", "show commits whole commit body", default=False
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return commits."""
        repository = self._github_get_repository(self._conf)
        data_since = self._github_check_repo_updated(
            repository, state.last_update
        )
        if not data_since:
            return state.new_not_modified(etag=repository.etag), []

        etag = state.get_state("etag")
        if hasattr(repository, "commits"):
            commits = list(repository.commits(since=data_since))
        else:
            commits = list(
                repository.iter_commits(since=data_since, etag=etag)
            )

        if not commits:
            new_state = state.new_not_modified(etag=repository.etag)
            if not new_state.icon:
                new_state.set_icon(self._load_binary(_GITHUB_ICON))
            return new_state, []

        short_list = self._conf.get("short_list")
        full_message = bool(self._conf.get("full_message") and not short_list)
        form_fun = (
            _format_gh_commit_short if short_list else _format_gh_commit_long
        )
        try:
            content = "\n\n".join(
                form_fun(commit, full_message) for commit in commits
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("github load error: %s", err)
            return state.new_error(str(err)), []

        new_state = state.new_ok(etag=repository.etag)
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_GITHUB_ICON))

        entry = _build_entry(self._source, repository, content)
        entry.icon = new_state.icon
        return new_state, [entry]


def _format_gh_commit_short(commit, _full_message: bool) -> str:
    cmt = commit.commit
    return (
        cmt.committer["date"]
        + " "
        + cmt.message.strip().split("\n", 1)[0].rstrip()
    )


def _format_gh_commit_long(commit, full_message: bool) -> str:
    cmt = commit.commit
    result = ["### " + cmt.committer["date"], "Author: " + cmt.author["name"]]
    msg = cmt.message.strip().split("\n")
    if not full_message:
        msg = msg[:1]
    result.extend(msg)
    return "\n".join(result)


class GithubTagsSource(AbstractSource, GitHubMixin):
    """Load last tags from github."""

    name = "github_tags"
    short_info = "Tags from Github repository"
    long_info = (
        "Source load tags from configured repository."
        " For work required configured Github account with token."
    )
    params = AbstractSource.params + [
        common.SettingDef("owner", "repository owner", required=True),
        common.SettingDef("repository", "repository name", required=True),
        common.SettingDef(
            "github_user", "user login", required=True, global_param=True
        ),
        common.SettingDef(
            "github_token",
            "user personal token",
            required=True,
            global_param=True,
        ),
        common.SettingDef(
            "max_items", "Maximal number of tags to load", default=5
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return commits."""
        conf = self._conf
        repository = self._github_get_repository(conf)
        if not self._github_check_repo_updated(repository, state.last_update):
            return state.new_not_modified(etag=repository.etag), []

        tags = _load_tags(
            repository, self._conf["max_items"], state.get_state("etag")
        )

        if state.last_update:
            tags = _filter_tags(tags, repository, state.last_update)

        tags = list(tags)

        if not tags:
            new_state = state.new_not_modified(etag=repository.etag)
            self._state_update_icon(new_state)
            return new_state, []

        try:
            content = "\n\n".join(filter(None, map(_format_gh_tag, tags)))
        except Exception as err:
            _LOG.exception("github load error: %s", err)
            raise common.InputError(self, err)

        new_state = state.new_ok(etag=repository.etag)
        self._state_update_icon(new_state)

        entry = _build_entry(self._source, repository, content)
        entry.icon = new_state.icon
        return new_state, [entry]

    def _state_update_icon(self, new_state):
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_GITHUB_ICON))


def _filter_tags(tags, repository, min_date: datetime):
    """For each tag in tags load commit informations from repo and compare
    commit last update date with min_date; return only tags with date after
    than min_date"""
    for tag in tags:
        try:
            commit = repository.commit(tag.commit.sha)
            if commit:
                commit_date = common.parse_http_date(commit.last_modified)
                if commit_date and commit_date > min_date:
                    tag.ex_commit_date = commit_date
                    yield tag
        except github3.exceptions.NotFoundError:
            pass


def _load_tags(repository, max_items, etag):
    if hasattr(repository, "tags"):
        return repository.tags(max_items, etag=etag)
    return repository.iter_tags(max_items, etag=etag)


def _format_gh_tag(tag) -> str:
    if hasattr(tag, "ex_commit_date"):
        return tag.name + " " + str(tag.ex_commit_date)
    return tag.name


class GithubReleasesSource(AbstractSource, GitHubMixin):
    """Load last releases from github."""

    name = "github_releases"
    short_info = "Releases from Github repository"
    long_info = (
        "Source load releases history from configured repository."
        " For work required configured Github account with token."
    )
    params = AbstractSource.params + [
        common.SettingDef("owner", "repository owner", required=True),
        common.SettingDef("repository", "repository name", required=True),
        common.SettingDef(
            "github_user", "user login", required=True, global_param=True
        ),
        common.SettingDef(
            "github_token",
            "user personal token",
            required=True,
            global_param=True,
        ),
        common.SettingDef(
            "max_items", "Maximal number of tags to load", value_type=int
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return releases."""
        repository = self._github_get_repository(self._conf)
        if not self._github_check_repo_updated(repository, state.last_update):
            new_state = state.new_not_modified(etag=repository.etag)
            return new_state, []

        etag = state.get_state("etag")
        max_items = self._conf["max_items"] or 100
        if hasattr(repository, "releases"):
            releases = list(repository.releases(max_items, etag=etag))
        else:
            releases = list(repository.iter_releases(max_items, etag=etag))

        if state.last_update:
            last_update = state.last_update.replace(tzinfo=tz.tzlocal())
            releases = [
                release
                for release in releases
                if not release.created_at or release.created_at > last_update
            ]

        if not releases:
            new_state = state.new_not_modified(etag=repository.etag)
            if not new_state.icon:
                new_state.set_icon(self._load_binary(_GITHUB_ICON))
            return new_state, []

        try:
            entries = [
                _build_gh_release_entry(self._source, repository, release)
                for release in releases
            ]
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("github load error %s", err)
            return state.new_error(str(err)), []

        new_state = state.new_ok(etag=repository.etag)
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_GITHUB_ICON))

        for entry in entries:
            entry.icon = new_state.icon
        return new_state, entries


def _build_gh_release_entry(
    source: model.Source, repository, release
) -> model.Entry:
    res = [
        "### ",
        release.name,
        " ",
        release.tag_name,
        "\n\nDate: ",
        release.created_at.astimezone(tz.tzlocal()).strftime("%x %X"),
    ]
    if release.html_url:
        res.extend(("\n", release.html_url))
    if release.body:
        res.append("\n")
        res.extend(
            line.strip() + "\n" for line in release.body.strip().split("\n")
        )
    content = "".join(map(str, res))
    return _build_entry(source, repository, content)
