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

from datetime import datetime, timedelta
import email.mime.multipart
import email.mime.text
import email.utils
import smtplib
import logging
import subprocess
import typing as ty

import html2text as h2t

from webmon2 import database, common, formatters


_LOG = logging.getLogger(__file__)


def process(db, user_id):
    """ Process unread entries for user and send report via mail """
    conf = database.settings.get_dict(db, user_id)
    if not conf.get('mail_enabled'):
        _LOG.debug("mail not enabled for user %d", user_id)
        return

    last_send = database.users.get_state(
        db, user_id, 'mail_last_send',
        conv=lambda x: datetime.fromtimestamp(float(x)))
    if last_send:
        interval = timedelta(
            seconds=common.parse_interval(conf.get('mail_interval', '1h')))
        if last_send + interval > datetime.now():
            _LOG.debug("still waiting for send mail")
            return

    content = ''.join(_process_groups(db, conf, user_id, last_send))
#    _LOG.debug("content: %s", content)
    if content and not _send_mail(conf, content):
        return

    database.users.set_state(db, user_id, 'mail_last_send',
                             datetime.now().timestamp())


def _process_groups(db, conf, user_id: int, last_send):
    for group in database.groups.get_all(db, user_id):
        yield from _process_group(db, conf, user_id, group.id, last_send)


def _process_group(db, conf, user_id: int, group_id: int, last_send) \
        -> ty.Iterator[str]:
    entries = list(database.entries.find(db, user_id, group_id=group_id))
    if last_send:
        entries = [entry for entry in entries if entry.updated > last_send]
    if not entries:
        return

    if conf.get('mail_mark_read'):
        min_id = min(entry.id for entry in entries)
        max_id = max(entry.id for entry in entries)
        database.groups.mark_read(db, user_id, group_id, min_id=min_id,
                                  max_id=max_id)

    fentry = entries[0]
    group_name = fentry.source.group.name \
        if fentry.source and fentry.source.group \
        else fentry.title
    group_name += f" [{len(entries)}]"
    yield group_name
    yield '\n'
    yield '-' * len(group_name)
    yield '\n\n'
    for entry in entries:
        yield from _render_entry_plain(entry)
    yield '\n\n\n'


def _render_entry_plain(entry):
    title = entry.source.name + ": " + entry.title + " " + \
        entry.updated.strftime("%x %X")
    yield title
    yield '\n'
    yield '-' * len(title)
    yield '\n\n'
    if entry.url:
        yield '['
        yield entry.url
        yield ']\n\n'
    content_type = entry.get_opt('content-type')
    if content_type == 'html':
        conv = h2t.HTML2Text(bodywidth=74)
        conv.protect_links = True
        yield conv.handle(entry.content)
    else:
        yield entry.content
    yield '\n\n\n'


def _prepare_msg(conf, content):
    body_plain = _encrypt(conf, content) if conf.get('mail_encrypt') \
        else content

    if not conf.get('mail_html'):
        return email.mime.text.MIMEText(body_plain, 'plain', 'utf-8')

    msg = email.mime.multipart.MIMEMultipart('alternative')
    msg.attach(email.mime.text.MIMEText(body_plain, 'plain', 'utf-8'))

    html = formatters.format_markdown(content)
    if conf.get('mail_encrypt'):
        html = _encrypt(conf, html)
    msg.attach(email.mime.text.MIMEText(html, 'html', 'utf-8'))
    return msg


def _send_mail(conf, content):
    _LOG.debug("send mail: %r", conf)
    try:
        msg = _prepare_msg(conf, content)
        msg['Subject'] = conf["mail_subject"]
        msg['From'] = conf["mail_from"]
        msg['To'] = conf["mail_to"]
        msg['Date'] = email.utils.formatdate()
        smtp = smtplib.SMTP_SSL() if conf.get("smtp_ssl") \
            else smtplib.SMTP()
        host, port = conf["smtp_host"], conf["smtp_port"]
        _LOG.debug("host, port: %r, %r", host, port)
        smtp.connect(host, port)
        smtp.ehlo()
        if conf.get("smtp_tls") and not conf.get("smtp_ssl"):
            smtp.starttls()
        if conf.get("smtp_login"):
            smtp.login(conf["smtp_login"], conf["smtp_password"])
        smtp.sendmail(msg['From'], [msg['To']], msg.as_string())
        _LOG.debug("mail send")
    except Exception:  # pylint: disable=broad-except
        _LOG.exception("send mail error")
        return False
    finally:
        smtp.quit()
    return True


def _encrypt(conf, message: str) -> str:
    subp = subprocess.Popen(["gpg", "-e", "-a", "-r", conf["mail_to"]],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = subp.communicate(message.encode('utf-8'))
    if subp.wait(60) != 0:
        _LOG.error("EMailOutput: encrypt error: %s", stderr)
        return stderr
    return stdout
