#!/usr/bin/python3
"""
Default outputs.
Output get new/changed/deleted contents and present it in human-readable
format. I.e. generate report, send mail.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import os.path
import smtplib
import email.mime.text
import email.mime.multipart
import email.utils
import logging
from datetime import datetime
import subprocess


from docutils.core import publish_string

from . import common
from . import cache


_LOG = logging.getLogger("outputs")

_DOCUTILS_HTML_OVERRIDES = {
    'stylesheet_path': os.path.join(os.path.dirname(__file__), "main.css")
}


class AbstractOutput(object):
    """Abstract/Base class for all outputs"""

    name = ""
    # parameters - list of tuples (name, description, default, required)
    params = []

    def __init__(self, conf):
        super(AbstractOutput, self).__init__()
        self._conf = common.apply_defaults(
            {key: val for key, _, val, _ in self.params},
            conf)
        self.footer = None

    def validate(self):
        for name, _, _, required in self.params or []:
            val = self._conf.get(name)
            if required and not val:
                raise common.ParamError("missing parameter " + name)

    def report(self, new, changed, errors, unchanged):
        """ Generate report """
        raise NotImplementedError()


def _rst_escape(text):
    return text.replace("\\", "\\\\").replace('`', '\\').replace("*", "\\*")


class AbstractTextOutput(AbstractOutput):
    """Simple text reporter"""

    def _format_item(self, ctx: common.Context, content: str):
        """ Generate section for one input """
        yield ctx.name
        yield "'" * len(ctx.name)
        if 'url' in ctx.conf:
            yield ctx.conf['url']

        header = ctx.opt.get('header')
        if header:
            if isinstance(header, str):
                yield header
            else:
                yield from header

        if ctx.args.debug:
            yield str(ctx)

        if content:
            content = content.rstrip() or "<no data>"
            if ctx.opt.get(common.OPTS_PREFORMATTED):
                yield "::"
                yield ""
                for line in content.split("\n"):
                    yield "  " + line
            else:
                for line in content.split("\n"):
                    yield ""
                    yield _rst_escape(line)
        yield ""

    def _get_stats_str(self, new, changed, errors, unchanged):
        """ Generate header """
        return ";  ".join(
            "*%s*: %d" % (title, len(items)) for title, items in [
                ("Changed", changed), ("New", new),
                ("Unchanged", unchanged), ("Error", errors)
            ] if items)

    def _gen_section(self, title, items):
        """ Generate section for group of inputs """
        title = "%s [%d]" % (title, len(items))
        yield title
        yield '-' * len(title)
        for ctx, content in items:
            yield from self._format_item(ctx, content)
        yield ''

    def _mk_report(self, new, changed, errors, unchanged):
        """ Generate whole report"""
        yield from [
            "========",
            " WebMon",
            "========",
            "",
            "Updated " + datetime.now().strftime("%x %X"),
            ""
        ]
        if new or changed or errors or unchanged:
            yield self._get_stats_str(new, changed, errors, unchanged)
            yield ""
            if new:
                yield from self._gen_section("New", new)
            if changed:
                yield from self._gen_section("Changed", changed)
            if errors:
                yield from self._gen_section("Errors", errors)
            if unchanged:
                yield from self._gen_section("Unchanged", unchanged)
        yield from self._gen_footer()

    def _gen_footer(self):
        yield ""
        yield ".. footer:: " + (self.footer or str(datetime.now()))

    def report(self, new, changed, errors, unchanged):
        """ Generate report """
        raise NotImplementedError()


class TextFileOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "text"
    params = [
        ("file", "Destination file name", None, True),
    ]

    def report(self, new, changed, errors, unchanged):
        _make_backup(self._conf["file"])
        try:
            with open(self._conf["file"], "w") as ofile:
                ofile.write("\n".join(self._mk_report(new, changed, errors,
                                                      unchanged)))
        except IOError as err:
            raise common.ReportGenerateError(
                "Writing report file %s error : %s" %
                (self._conf['file'], err))


class HtmlFileOutput(AbstractTextOutput):
    """Simple html reporter"""

    name = "html"
    params = [
        ("file", "Destination file name", None, True),
    ]

    def report(self, new, changed, errors, unchanged):
        _make_backup(self._conf["file"])
        content = self._mk_report(new, changed, errors, unchanged)
        try:
            with open(self._conf["file"], "w") as ofile:
                html = publish_string(
                    "\n".join(content), writer_name='html',
                    settings=None,
                    settings_overrides=_DOCUTILS_HTML_OVERRIDES)
                ofile.write(html.decode('utf-8'))
        except IOError as err:
            raise common.ReportGenerateError(
                "Writing report file %s error : %s" %
                (self._conf['file'], err))


class ConsoleOutput(AbstractTextOutput):
    """Display report on console"""

    name = "console"

    def report(self, new, changed, errors, unchanged):
        print("\n".join(self._mk_report(new, changed, errors, unchanged)))


class EMailOutput(AbstractTextOutput):
    """Send report by smtp"""

    name = "email"
    params = [
        ("to", "email recipient", None, True),
        ("from", "email sender", None, True),
        ("subject", "email subject", "WebMail Report", True),
        ("smtp_host", "SMTP server address", None, True),
        ("smtp_port", "SMTP server port", None, True),
        ("smtp_login", "SMTP user login", None, False),
        ("smtp_password", "SMTP user password", None, False),
        ("smtp_tls", "Enable TLS", None, False),
        ("smtp_ssl", "Enable SSL", None, False),
        ("encrypt", "Encrypt email", False, False),
        ("html", "Send miltipart email with html content", False, False),
    ]

    def validate(self):
        super(EMailOutput, self).validate()
        conf = self._conf
        if conf.get("smtp_login"):
            if not conf.get("smtp_password"):
                raise common.ParamError("missing password for login")
        if conf.get("smtp_tls") and conf.get("smtp_ssl"):
            _LOG.warning("EMailOutput: configured tls and ssl; using ssl")

        encrypt = self._conf.get("encrypt", "")
        if encrypt and encrypt not in ('gpg', ):
            raise common.ParamError("invalid encrypt parameter: %r" % encrypt)

    def report(self, new, changed, errors, unchanged):
        conf = self._conf
        body = "\n".join(self._mk_report(new, changed, errors, unchanged))
        msg = self._get_msg(conf.get("html"), body)
        header = self._get_stats_str(new, changed, errors, unchanged)
        msg['Subject'] = conf["subject"] + (" [" + header + "]"
                                            if header else "")
        msg['From'] = conf["from"]
        msg['To'] = conf["to"]
        msg['Date'] = email.utils.formatdate()
        smtp = None
        try:
            smtp = smtplib.SMTP_SSL() if conf.get("smtp_ssl") \
                else smtplib.SMTP()
            smtp.connect(conf["smtp_host"], conf["smtp_port"])
            smtp.ehlo()
            if conf.get("smtp_tls") and not conf.get("smtp_ssl"):
                smtp.starttls()
            if conf.get("smtp_login"):
                smtp.login(conf["smtp_login"], conf["smtp_password"])
            smtp.sendmail(msg['From'], [msg['To']], msg.as_string())
        except Exception as err:
            raise common.ReportGenerateError("Sending mail error: %s" % err)
        finally:
            smtp.quit()

    def _get_msg(self, gen_html, body):
        if self._conf.get("encrypt") == 'gpg':
            body = self._encrypt(body)
        if gen_html:
            msg = email.mime.multipart.MIMEMultipart('alternative')
            msg.attach(email.mime.text.MIMEText(body, 'plain', 'utf-8'))

            html = publish_string(
                body, writer_name='html', settings=None,
                settings_overrides=_DOCUTILS_HTML_OVERRIDES).decode('utf-8')
            msg.attach(email.mime.text.MIMEText(html, 'html', 'utf-8'))
            return msg
        return email.mime.text.MIMEText(body, 'plain', 'utf-8')

    def _encrypt(self, message):
        subp = subprocess.Popen(["gpg", "-e", "-a", "-r", self._conf["to"]],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = subp.communicate(message.encode('utf-8'))
        if subp.wait(60) != 0:
            _LOG.error("EMailOutput: encrypt error: %s", stderr)
            return stderr
        return stdout


def _get_output(name, params):
    _LOG.debug("_get_output %r", name)
    if not params.get("enabled", True):
        return None

    rcls = common.find_subclass(AbstractOutput, name)
    if rcls:
        out = rcls(params)
        out.validate()
        return out

    _LOG.warning("unknown output: %s", name)


class OutputManager(object):
    """ Object group all outputs. """
    def __init__(self, conf, args):
        super(OutputManager, self).__init__()
        self._conf = conf
        self.args = args
        self._outputs = []
        self._new = []
        self._changed = []
        self._unchanged = []
        self._errors = []
        self._cache = cache.PartsCache(os.path.join(args.cache_dir, "parts"))
        for repname, repconf in (conf or {}).items():
            try:
                rep = _get_output(repname, repconf or {})
                if rep:
                    self._outputs.append(rep)
            finally:
                pass

    def status(self):
        return {
            'new': len(self._new),
            'changed': len(self._changed),
            'unchanged': len(self._unchanged),
            'error': len(self._errors)
        }

    @property
    def errors_cnt(self):
        return len(self._errors)

    @property
    def valid(self):
        return bool(self._outputs)

    def add_new(self, ctx, content):
        self._new.append((ctx, content))

    def add_changed(self, ctx, diff):
        self._changed.append((ctx, diff))

    def add_error(self, ctx, error):
        self._errors.append((ctx, error))

    def add_unchanged(self, ctx, content):
        self._unchanged.append((ctx, content))

    def write(self, footer=None):
        """ Write all reports; footer is optionally included. """
        _LOG.debug("OutputManager: writing...")
        if not (self._conf.get("report_unchanged") or self._new or
                self._changed or self._errors):
            return
        for rep in self._outputs:
            try:
                rep.footer = footer
                rep.report(self._new, self._changed, self._errors,
                           self._unchanged)
            except Exception as err:
                _LOG.error("OutputManager: write %s error: %s", rep, err)
        _LOG.debug("OutputManager: write done")


def _make_backup(filename):
    if not os.path.isfile(filename):
        return
    os.rename(filename, filename + ".bak")
