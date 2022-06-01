#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Sending reports by mail functions
"""

import email.mime.multipart
import email.mime.text
import email.utils
import logging
import re
import smtplib
import subprocess
import typing as ty
from configparser import ConfigParser
from datetime import datetime, timedelta

import html2text as h2t
from prometheus_client import Counter

from webmon2 import common, database, formatters, model

_LOG = logging.getLogger(__name__)
_SENT_MAIL_COUNT = Counter("webmon2_mails_count", "Mail sent count")


def process(db: database.DB, user: model.User, app_conf: ConfigParser) -> None:
    """Process unread entries for user and send report via mail"""
    if not user.id:
        raise ValueError("require existing user")

    conf = database.settings.get_dict(db, user.id)
    if not conf.get("mail_enabled"):
        _LOG.debug("mail not enabled for user %d", user.id)
        return

    if _is_silent_hour(conf):
        return

    # it is time for send mail?
    last_send = database.users.get_state(
        db,
        user.id,
        "mail_last_send",
        conv=lambda x: datetime.fromtimestamp(float(x)),
    )
    if last_send:
        interval = timedelta(
            seconds=common.parse_interval(conf.get("mail_interval", "1h"))
        )
        if last_send + interval > datetime.utcnow():
            _LOG.debug("still waiting for send mail")
            return

    try:
        content = "".join(_process_groups(db, conf, user.id))
    except Exception as err:  # pylint: disable=broad-except
        _LOG.error("prepare mail for user %d error: %s", user.id, err)
        return

    if content and not _send_mail(conf, content, app_conf, user):
        return

    _SENT_MAIL_COUNT.inc()
    database.users.set_state(
        db, user.id, "mail_last_send", datetime.utcnow().timestamp()
    )


def _process_groups(
    db: database.DB, conf: ty.Dict[str, ty.Any], user_id: int
) -> ty.Iterable[str]:
    """
    Iterate over source groups for `user_id` and build mail body.
    """
    for group in database.groups.get_all(db, user_id):
        if group.mail_report == model.MailReportMode.NO_SEND:
            _LOG.debug("group %s skipped", group.name)
            continue

        if not group.unread:
            _LOG.debug("no unread entries in group %s", group.name)
            continue

        assert group.id
        yield from _process_group(db, conf, user_id, group.id)


def _process_group(
    db: database.DB, conf: ty.Dict[str, ty.Any], user_id: int, group_id: int
) -> ty.Iterator[str]:
    """
    Process sources in `group_id` and build mail body part.
    """
    _LOG.debug("processing group %d", group_id)
    sources = [
        source
        for source in database.sources.get_all(db, user_id, group_id)
        if source.unread and source.mail_report != model.MailReportMode.NO_SEND
    ]
    if not sources:
        _LOG.debug("no unread sources in group %d", group_id)
        return

    assert sources[0].group
    group_name = sources[0].group.name
    yield group_name
    yield "\n"
    yield "=" * len(group_name)
    yield "\n\n"

    for source in sources:
        yield from _proces_source(db, conf, user_id, source.id)

    yield "\n\n\n"


def _proces_source(
    db: database.DB, conf: ty.Dict[str, ty.Any], user_id: int, source_id: int
) -> ty.Iterator[str]:
    """
    Build mail content for `source_id`.
    """
    _LOG.debug("processing source %d", source_id)

    entries = [
        entry
        for entry in database.entries.find(db, user_id, source_id=source_id)
        if model.MailReportMode.SEND
        in (entry.source.mail_report, entry.source.group.mail_report)  # type: ignore
    ]

    if not entries:
        _LOG.debug("no entries to send in source %d", source_id)
        return

    assert entries[0].source
    source_name = entries[0].source.name
    yield source_name
    yield "\n"
    yield "-" * len(source_name)
    yield "\n\n"

    for entry in entries:
        _LOG.debug("processing entry id %dd", entry.id)
        yield from _render_entry_plain(entry)

    if conf.get("mail_mark_read"):
        ids = [entry.id for entry in entries]
        database.entries.mark_read(db, user_id, ids=ids)

    yield "\n\n"


def _adjust_header(line: str, prefix: str = "###") -> str:
    if line and re.compile(r"^#+ .+").match(line):
        return prefix + line

    return line


def _render_entry_plain(entry: model.Entry) -> ty.Iterator[str]:
    """
    Render entry as markdown document.
    If entry content type is not plain or markdown try convert it to plain text.
    """
    title = (entry.title or "") + " " + entry.updated.strftime("%x %X")  # type: ignore
    yield "### "
    yield _get_entry_score_mark(entry)
    if entry.url:
        yield "["
        yield title
        yield "]("
        yield entry.url
        yield ")"
    else:
        yield title

    yield "\n"
    if entry.content:
        content_type = entry.content_type
        if content_type in ("plain", "markdown"):
            yield "\n".join(map(_adjust_header, entry.content.split("\n")))
        else:
            conv = h2t.HTML2Text(bodywidth=74)
            conv.protect_links = True
            yield conv.handle(entry.content)

        yield "\n"


def _prepare_msg(
    conf: ty.Dict[str, ty.Any], content: str
) -> email.mime.base.MIMEBase:
    """
    Prepare email message according to `conf` and with `content`.
    If `mail_html` enabled build multi part message (convert `content` using
    markdown -> html converter).
    """
    body_plain = (
        _encrypt(conf, content) if conf.get("mail_encrypt") else content
    )

    if not conf.get("mail_html"):
        return email.mime.text.MIMEText(body_plain, "plain", "utf-8")

    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg.attach(email.mime.text.MIMEText(body_plain, "plain", "utf-8"))

    html = formatters.format_markdown(content)
    if conf.get("mail_encrypt"):
        html = _encrypt(conf, html)

    msg.attach(email.mime.text.MIMEText(html, "html", "utf-8"))
    return msg


def _send_mail(
    conf: ty.Dict[str, ty.Any],
    content: str,
    app_conf: ConfigParser,
    user: model.User,
) -> bool:
    _LOG.debug("send mail: %r", conf)
    mail_to = conf["mail_to"] or user.email

    if not mail_to:
        _LOG.error("email enabled for user %d but no email defined ", user.id)
        return False

    try:
        msg = _prepare_msg(conf, content)
        msg["Subject"] = conf["mail_subject"]
        msg["From"] = app_conf.get("smtp", "from")
        msg["To"] = mail_to
        msg["Date"] = email.utils.formatdate()
        ssl = app_conf.getboolean("smtp", "ssl")
        smtp = smtplib.SMTP_SSL() if ssl else smtplib.SMTP()
        if _LOG.isEnabledFor(logging.DEBUG):
            smtp.set_debuglevel(True)

        host = app_conf.get("smtp", "address")
        port = app_conf.getint("smtp", "port")
        _LOG.debug("host, port: %r, %r", host, port)
        smtp.connect(host, port)
        smtp.ehlo()
        if app_conf.getboolean("smtp", "starttls") and not ssl:
            smtp.starttls()

        login = app_conf.get("smtp", "login")
        if login:
            smtp.login(login, app_conf.get("smtp", "password"))

        smtp.sendmail(msg["From"], [mail_to], msg.as_string())
        _LOG.debug("mail send")
    except (smtplib.SMTPServerDisconnected, ConnectionRefusedError) as err:
        _LOG.error("smtp connection error: %s; user %d", err, user.id)
        return False
    except Exception:  # pylint: disable=broad-except
        _LOG.exception("send mail error")
        return False
    finally:
        try:
            smtp.quit()
        except:  # noqa: E722; pylint: disable=bare-except
            pass
    return True


def _encrypt(conf: ty.Dict[str, ty.Any], message: str) -> str:
    with subprocess.Popen(
        ["/usr/bin/env", "gpg", "-e", "-a", "-r", conf["mail_to"]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as subp:
        stdout, stderr = subp.communicate(message.encode("utf-8"))
        if subp.wait(60) != 0:
            _LOG.error(
                "EMailOutput: encrypt error: %s; mail_to: %r",
                stderr,
                conf["mail_to"],
            )
            return stderr.decode("utf-8")

        return stdout.decode("utf-8")


def _get_entry_score_mark(entry: model.Entry) -> str:
    if entry.score < -5:
        return "▼▼ "
    if entry.score < 0:
        return "▼ "
    if entry.score > 5:
        return "▲▲ "
    if entry.score > 0:
        return "▲ "
    return ""


def _is_silent_hour(conf: ty.Dict[str, ty.Any]) -> bool:
    begin = conf.get("silent_hours_from", "")
    end = conf.get("silent_hours_to", "")

    _LOG.debug("check silent hours %r", (begin, end))

    if not begin or not end:
        return False

    try:
        begin = int(begin)
        end = int(end)
    except ValueError:
        _LOG.exception("parse silent hours%r  error", (begin, end))
        return False

    hour = datetime.now().hour

    if begin > end:  # ie 22 - 6
        if hour >= begin or hour < end:
            return True
    else:  # ie 0-6
        if begin <= hour <= end:
            return True

    _LOG.debug("not in silent hours")

    return False
