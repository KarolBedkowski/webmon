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
        common.SettingDef("project", "project id; i.e. user/project",
                          required=True),
        common.SettingDef("gitlab_url", "GitLab url", required=True,
                          default=_GITLAB_DEFAULT_URL),
        common.SettingDef("gitlab_token", "user personal token", required=True,
                          global_param=True),
    ]

    @staticmethod
    def _gitlab_check_project_updated(
            project, last_updated: ty.Optional[datetime]) \
            -> ty.Optional[str]:
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

        last_activity = datetime.strptime(project.last_activity_at,
                                          '%Y-%m-%dT%H:%M:%S.%fZ')
        if last_activity <= last_updated.replace():
            return None

        return last_updated.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _gitlab_get_project(self):
        """Create project object according to configuration. """
        conf = self._conf
        if conf.get("gitlab_url") and conf.get("gitlab_token"):
            try:
                gitl = gitlab.Gitlab(conf.get("gitlab_url"),
                                     conf.get("gitlab_token"))
                _LOG.debug("gitlab: %r", gitl)
                return gitl.projects.get(conf["project"])
            except Exception as err:
                raise common.InputError(self, "Gitlab auth error: " + str(err))
        return None

    def _get_favicon(self):
        url = self._conf['gitlab_url']
        if not url.endswith('/'):
            url += '/'
        return url + _FAVICON


def _build_entry(source: model.Source, project, content: str) \
        -> model.Entry:
    entry = model.Entry.for_source(source)
    entry.url = project.web_url
    entry.title = source.name
    entry.status = 'new'
    entry.content = content
    entry.created = entry.updated = datetime.now()
    entry.set_opt("content-type", "markdown")
    return entry


class GitLabCommits(AbstractGitLabSource):
    """Load last commits from gitlab."""

    name = "gitlab_commits"
    short_info = "Commit history from GitLab repository"
    long_info = 'Source load commits history from configured repository.' \
        ' For work required configured GitLab account with token.'
    params = AbstractGitLabSource.params + [
        common.SettingDef("short_list", "show commits as short list",
                          default=True),
        common.SettingDef("full_message", "show commits whole commit body",
                          default=False),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return commits."""
        project = self._gitlab_get_project()
        if not project:
            return state.new_error("Project not found"), []

        data_since = self._gitlab_check_project_updated(
            project, state.last_update)
        if not data_since:
            return state.new_not_modified(), []

        commits = project.commits.list(since=data_since)
        _LOG.debug("commits: %r", commits)
        if not commits:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(
                    self._get_favicon()))
            return new_state, []

        short_list = self._conf.get("short_list")
        full_message = bool(self._conf.get("full_message") and not short_list)
        form_fun = _format_gl_commit_short if short_list else \
            _format_gl_commit_long
        try:
            content = '\n\n'.join(form_fun(commit, full_message)
                                  for commit in commits)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("gitlab load error: %s", err)
            return state.new_error(str(err)), []

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(
                self._get_favicon()))

        entry = _build_entry(self._source, project, content)
        entry.icon = new_state.icon
        return new_state, [entry]


def _format_gl_commit_short(commit, _full_message: bool) -> str:
    return (commit.committed_date + " " +
            commit.message.strip().split("\n", 1)[0].rstrip())


def _format_gl_commit_long(commit, full_message: bool) -> str:
    result = ['### ' + commit.committed_date,
              "Author: " + commit.committer_name]
    msg = commit.message.strip().split('\n')
    if not full_message:
        msg = msg[:1]
    result.extend(msg)
    return "\n".join(result)


class GitLabTagsSource(AbstractGitLabSource):
    """Load last tags from gitlab."""

    name = "gitlab_tags"
    short_info = "Tags from GitLab repository"
    long_info = 'Source load tags from configured repository.' \
        ' For work required configured GitLab account with token.'
    params = AbstractGitLabSource.params + [
        common.SettingDef("max_items", "Maximal number of tags to load",
                          default=5),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return commits."""
        project = self._gitlab_get_project()
        if not project:
            return state.new_error("Project not found"), []

        data_since = self._gitlab_check_project_updated(
            project, state.last_update)
        if not data_since:
            return state.new_not_modified(), []

        tags = project.tags.list(since=data_since)
        _LOG.debug("tags: %r", tags)
        if not tags:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(
                    self._get_favicon()))
            return new_state, []

        try:
            content = '\n\n'.join(filter(None, map(_format_gl_tag, tags)))
        except Exception as err:
            _LOG.exception("gitlab load error: %s", err)
            raise common.InputError(self, err)

        new_state = state.new_ok()
        self._state_update_icon(new_state)

        entry = _build_entry(self._source, project, content)
        entry.icon = new_state.icon
        return new_state, [entry]

    def _state_update_icon(self, new_state):
        if not new_state.icon:
            new_state.set_icon(self._load_binary(self._get_favicon()))


def _format_gl_tag(tag) -> str:
    res = tag.name
    commit_date = tag.commit.get('committed_date')
    if commit_date:
        res += " " + commit_date
    if tag.message:
        res += " " + tag.message
    return res
