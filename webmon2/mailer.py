# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Sending reports by mail functions
"""

import email.message
import email.utils
import logging
import re
import smtplib
import subprocess
import tempfile
import typing as ty
from configparser import ConfigParser
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import html2text as h2t
from prometheus_client import Counter

from webmon2 import common, database, formatters, model

_LOG = logging.getLogger(__name__)
_SENT_MAIL_COUNT = Counter("webmon2_mails_count", "Mail sent count")


@dataclass
class Ctx:
    user_id: int
    conf: ty.Dict[str, ty.Any]
    timezone: ty.Optional[ZoneInfo] = None


def process(db: database.DB, user: model.User, app_conf: ConfigParser) -> bool:
    """Process unread entries for user and send report via mail"""
    if not user.id:
        raise ValueError("require existing user")

    conf = database.settings.get_dict(db, user.id)
    if not conf.get("mail_enabled"):
        _LOG.debug("mail not enabled for user %d", user.id)
        return False

    if _is_silent_hour(conf):
        return False

    # it is time for send mail?
    last_send = database.users.get_state(
        db,
        user.id,
        "mail_last_send",
        conv=lambda x: datetime.fromtimestamp(float(x or 0), tz=timezone.utc),
    )
    if last_send:
        interval = timedelta(
            seconds=common.parse_interval(conf.get("mail_interval", "1h"))
        )
        if last_send + interval > datetime.now(timezone.utc):
            _LOG.debug("still waiting for send mail")
            return False

    ctx = Ctx(
        user_id=user.id,
        conf=conf,
    )
    if tzone := conf.get("timezone"):
        ctx.timezone = ZoneInfo(tzone)

    try:
        content = "".join(_process_groups(ctx, db))
    except Exception as err:  # pylint: disable=broad-except
        _LOG.error("prepare mail for user %d error: %s", user.id, err)
        return False

    if content and not _send_mail(conf, content, app_conf, user):
        return False

    _SENT_MAIL_COUNT.inc()
    database.users.set_state(
        db,
        user.id,
        "mail_last_send",
        datetime.now(timezone.utc).timestamp(),
    )

    return True


def _process_groups(ctx: Ctx, db: database.DB) -> ty.Iterable[str]:
    """
    Iterate over source groups for `user_id` and build mail body.
    """
    for group in database.groups.get_all(db, ctx.user_id):
        if group.mail_report == model.MailReportMode.NO_SEND:
            _LOG.debug("group %s skipped", group.name)
            continue

        if not group.unread:
            _LOG.debug("no unread entries in group %s", group.name)
            continue

        assert group.id
        yield from _process_group(ctx, db, group.id)


def _process_group(
    ctx: Ctx, db: database.DB, group_id: int
) -> ty.Iterator[str]:
    """
    Process sources in `group_id` and build mail body part.
    """
    _LOG.debug("processing group %d", group_id)
    sources = [
        source
        for source in database.sources.get_all(db, ctx.user_id, group_id)
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
        yield from _proces_source(ctx, db, source.id)

    yield "\n\n\n"


def _proces_source(
    ctx: Ctx, db: database.DB, source_id: int
) -> ty.Iterator[str]:
    """
    Build mail content for `source_id`.
    """
    _LOG.debug("processing source %d", source_id)

    entries = [
        entry
        for entry in database.entries.find(
            db,
            ctx.user_id,
            source_id=source_id,
        )
        if model.MailReportMode.SEND
        in (entry.source.mail_report, entry.source.group.mail_report)
        or (
            entry.source.mail_report
            == entry.source.group.mail_report
            == model.MailReportMode.AS_GROUP_SOURCE
        )
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
        yield from _render_entry_plain(ctx, entry)

    if ctx.conf.get("mail_mark_read"):
        ids = [entry.id for entry in entries]
        database.entries.mark_read(db, ctx.user_id, ids=ids)

    yield "\n\n"


def _adjust_header(line: str, prefix: str = "###") -> str:
    if line and re.compile(r"^#+ .+").match(line):
        return prefix + line

    return line


def _render_entry_plain(ctx: Ctx, entry: model.Entry) -> ty.Iterator[str]:
    """Render entry as markdown document.
    If entry content type is not plain or markdown try convert it to plain
    text.
    """
    updated = entry.updated
    assert updated
    if tzone := ctx.timezone:
        updated = updated.astimezone(tzone)

    title = (entry.title or "") + " " + updated.strftime("%x %X")

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
) -> email.message.EmailMessage:
    """
    Prepare email message according to `conf` and with `content`.
    If `mail_html` enabled build multi part message (convert `content` using
    markdown -> html converter).
    """
    msg = email.message.EmailMessage()
    if not conf.get("mail_html"):
        if conf.get("mail_encrypt"):
            content = _encrypt(conf, content)

        msg.set_content(content)
        return msg

    msg.set_content(content)
    html = formatters.format_markdown(content)
    msg.add_alternative(html, subtype="html")

    if conf.get("mail_encrypt"):
        content = _encrypt(conf, msg.as_string())

        msg = email.message.EmailMessage()

        submsg1 = email.message.Message()
        submsg1.set_payload("Version: 1\n")
        submsg1.set_type("application/pgp-encrypted")
        msg.attach(submsg1)

        submsg2 = email.message.Message()
        submsg2.set_type("application/octet-stream")
        submsg2.set_payload(content)
        msg.attach(submsg2)

        msg.set_type("multipart/encrypted")
        msg.set_param("protocol", "application/pgp-encrypted")

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
        with suppress():
            smtp.quit()
    return True


def _encrypt(conf: ty.Dict[str, ty.Any], message: str) -> str:
    args = ["/usr/bin/env", "gpg", "-e", "-a", "-r", conf["mail_to"]]

    if user_key := conf.get("gpg_key"):
        keyfile_name = None
        with tempfile.NamedTemporaryFile(delete=False) as keyfile:
            keyfile.write(user_key.encode("UTF-8"))
            keyfile_name = keyfile.name

        args.extend(("-f", keyfile_name))
        try:
            return __do_encrypt(args, message)
        finally:
            Path(keyfile.name).unlink()

    return __do_encrypt(args, message)


def __do_encrypt(args: ty.List[str], message: str) -> str:
    with subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as subp:
        stdout, stderr = subp.communicate(message.encode("utf-8"))
        if subp.wait(60) != 0:
            _LOG.error(
                "EMailOutput: encrypt error: %s; args: %r",
                stderr,
                args,
            )
            return stderr.decode("ascii")

        return stdout.decode("ascii")


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
