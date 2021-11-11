#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2021 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Inputs related to gitlab
"""
import logging
import typing as ty
from datetime import datetime, timedelta

import gitlab
import gitlab.v4.objects as gobj

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
_GITLAB_MAX_AGE = 90  # 90 days
_GITLAB_DEFAULT_URL = "https://gitlab.com/"
_FAVICON = "favicon.ico"
_ = ty


class AbstractGitLabSource(AbstractSource):
    """Support functions for GitLab"""

    # pylint: disable=too-few-public-methods
    params = AbstractSource.params + [
        common.SettingDef(
            "project", "project id; i.e. user/project", required=True
        ),
        common.SettingDef(
            "gitlab_url", "GitLab url", default=_GITLAB_DEFAULT_URL
        ),
        common.SettingDef(
            "gitlab_token",
            "user personal token",
            required=True,
            global_param=True,
        ),
    ]

    def __init__(
        self, source: model.Source, sys_settings: model.ConfDict
    ) -> None:
        super().__init__(source, sys_settings)
        self._update_source()

    @staticmethod
    def _gitlab_check_project_updated(
        project: gobj.projects.Project, last_updated: ty.Optional[datetime]
    ) -> ty.Optional[str]:
        """Verify last repository update date.
        Returns: None when repo is not updated or formatted minimal date
            to load
        """
        if not last_updated:
            min_date = datetime.now() - timedelta(days=_GITLAB_MAX_AGE)
            return min_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        last_activity_at = project.last_activity_at
        if not last_activity_at:
            return None

        last_activity = datetime.strptime(
            project.last_activity_at, "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        if last_activity <= last_updated.replace():
            return None

        return last_updated.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _gitlab_get_project(self) -> ty.Optional[gobj.projects.Project]:
        """Create project object according to configuration."""
        conf = self._conf
        url = conf.get("gitlab_url")
        token = conf.get("gitlab_token")
        if url and token:
            try:
                gitl = gitlab.Gitlab(url, token)  # type: ignore
                _LOG.debug("gitlab: %r", gitl)
                return gitl.projects.get(conf["project"])  # type: ignore

            except Exception as err:
                raise common.InputError(self, "Gitlab auth error: " + str(err))

        return None

    def _get_favicon(self) -> str:
        url: str = self._conf["gitlab_url"]
        if not url.endswith("/"):
            url += "/"

        return url + _FAVICON

    def _update_source(self) -> None:
        """
        Make some updates in source settings (if necessary).
        """
        if not self._source.settings or self._source.settings.get("url"):
            return

        self._updated_source = self._updated_source or self._source.clone()
        self.__class__.before_save(self._updated_source)

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


def _build_entry(
    source: model.Source, project: gobj.projects.Project, content: str
) -> model.Entry:
    entry = model.Entry.for_source(source)
    entry.url = project.web_url
    entry.title = source.name
    entry.status = model.EntryStatus.NEW
    entry.content = content
    entry.created = entry.updated = datetime.now()
    entry.set_opt("content-type", "markdown")
    return entry


class GitLabCommits(AbstractGitLabSource):
    """Load last commits from gitlab."""

    name = "gitlab_commits"
    short_info = "Commit history from GitLab repository"
    long_info = (
        "Source load commits history from configured repository."
        " For work required configured GitLab account with token."
    )
    params = AbstractGitLabSource.params + [
        common.SettingDef(
            "short_list", "show commits as short list", default=True
        ),
        common.SettingDef(
            "full_message", "show commits whole commit body", default=False
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        """Return commits."""
        project = self._gitlab_get_project()
        if not project:
            return state.new_error("Project not found"), []

        data_since = self._gitlab_check_project_updated(
            project, state.last_update
        )
        if not data_since:
            del project
            project = None
            return state.new_not_modified(), []

        commits = project.commits.list(since=data_since)
        _LOG.debug("commits: %r", commits)
        if not commits:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(self._get_favicon()))

            del project
            project = None
            return new_state, []

        short_list = self._conf.get("short_list")
        full_message = bool(self._conf.get("full_message") and not short_list)
        form_fun = (
            _format_gl_commit_short if short_list else _format_gl_commit_long
        )
        try:
            content = "\n\n".join(
                form_fun(commit, full_message) for commit in commits
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("gitlab load error: %s", err)
            return state.new_error(str(err)), []

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(self._get_favicon()))

        entry = _build_entry(self._source, project, content)
        entry.icon = new_state.icon

        del project
        project = None

        return new_state, [entry]

    @classmethod
    def before_save(cls, source: model.Source) -> model.Source:
        """
        Update configuration before save; apply some additional data.
        """
        if source.settings:
            conf = source.settings
            glurl = conf["gitlab_url"]
            if not glurl.endswith("/"):
                conf["gitlab_url"] = glurl = glurl + "/"
            conf["url"] = f"{glurl}{conf['project']}/"

        return source

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


def _format_gl_commit_short(
    commit: gobj.commits.ProjectCommit, _full_message: bool
) -> str:
    return str(
        commit.committed_date
        + " "
        + commit.message.strip().split("\n", 1)[0].rstrip()
    )


def _format_gl_commit_long(
    commit: gobj.commits.ProjectCommit, full_message: bool
) -> str:
    result = [
        "### " + commit.committed_date,
        "Author: " + commit.committer_name,
    ]
    msg = commit.message.strip().split("\n")
    if not full_message:
        msg = msg[:1]

    result.extend(msg)
    return "\n".join(result)


class GitLabTagsSource(AbstractGitLabSource):
    """Load last tags from gitlab."""

    name = "gitlab_tags"
    short_info = "Tags from GitLab repository"
    long_info = (
        "Source load tags from configured repository."
        " For work required configured GitLab account with token."
    )
    params = AbstractGitLabSource.params + [
        common.SettingDef(
            "max_items", "Maximal number of tags to load", default=5
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        """Return commits."""
        project = self._gitlab_get_project()
        if not project:
            return state.new_error("Project not found"), []

        data_since = self._gitlab_check_project_updated(
            project, state.last_update
        )
        if not data_since:
            return state.new_not_modified(), []

        tags = project.tags.list(
            since=data_since, per_page=self._conf["max_items"]
        )
        _LOG.debug("tags: %r", tags)
        if not tags:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(self._get_favicon()))

            del project
            project = None

            return new_state, []

        try:
            content = "\n\n".join(filter(None, map(_format_gl_tag, tags)))
        except Exception as err:
            _LOG.exception("gitlab load error: %s", err)
            raise common.InputError(self, str(err))

        new_state = state.new_ok()
        self._state_update_icon(new_state)

        entry = _build_entry(self._source, project, content)
        entry.icon = new_state.icon

        del project
        project = None

        return new_state, [entry]

    def _state_update_icon(self, new_state: model.SourceState) -> None:
        if not new_state.icon:
            new_state.set_icon(self._load_binary(self._get_favicon()))

    @classmethod
    def before_save(cls, source: model.Source) -> model.Source:
        """
        Update configuration before save; apply some additional data.
        """
        if source.settings:
            conf = source.settings
            glurl = conf["gitlab_url"]
            if not glurl.endswith("/"):
                conf["gitlab_url"] = glurl = glurl + "/"
            conf["url"] = f"{glurl}{conf['project']}/-/tags"

        return source

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


def _format_gl_tag(tag: gobj.tags.ProjectTag) -> str:
    res: str = tag.name
    commit_date = tag.commit.get("committed_date")
    if commit_date:
        res += " " + commit_date

    if tag.message:
        res += " " + tag.message

    return res


class GitLabReleasesSource(AbstractGitLabSource):
    """Load last releases from gitlab."""

    name = "gitlab_releases"
    short_info = "Releases from GitLab repository"
    long_info = (
        "Source load releases history from configured repository."
        " For work required configured GitLab account with token."
    )
    params = AbstractGitLabSource.params + [
        common.SettingDef(
            "max_items", "Maximal number of tags to load", value_type=int
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        """Return releases."""

        project = self._gitlab_get_project()
        if not project:
            return state.new_error("Project not found"), []

        data_since = self._gitlab_check_project_updated(
            project, state.last_update
        )
        if not data_since:
            del project
            project = None

            return state.new_not_modified(), []

        releases = project.releases.list(
            since=data_since, per_page=self._conf["max_items"]
        )
        _LOG.debug("releases: %r", releases)

        if not releases:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(self._get_favicon()))

            del project
            project = None

            return new_state, []

        entries = [
            _build_gl_release_entry(self._source, project, release)
            for release in releases
        ]

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(self._get_favicon()))

        for entry in entries:
            entry.icon = new_state.icon

        del project
        project = None

        return new_state, entries

    @classmethod
    def before_save(cls, source: model.Source) -> model.Source:
        """
        Update configuration before save; apply some additional data.
        """
        if source.settings:
            conf = source.settings
            glurl = conf["gitlab_url"]
            if not glurl.endswith("/"):
                conf["gitlab_url"] = glurl = glurl + "/"
            conf["url"] = f"{glurl}{conf['project']}/-/releases"

        return source

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


def _build_gl_release_entry(
    source: model.Source,
    project: gobj.projects.Project,
    release: gobj.releases.ProjectRelease,
) -> model.Entry:
    res = [
        "### ",
        release.name,
        " ",
        release.tag_name,
        "\n\nDate: ",
        release.created_at,
    ]
    links = release.attributes.get("_links")
    if links:
        slink = links.get("self")
        if slink:
            res.extend(("\n", slink))

    if release.description:
        res.append("\n")
        res.extend(
            line.strip() + "\n"
            for line in release.description.strip().split("\n")
        )

    content = "".join(map(str, res))
    return _build_entry(source, project, content)
