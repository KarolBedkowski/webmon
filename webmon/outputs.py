#!/usr/bin/python3
"""
Default outputs.
Output get new/changed/deleted contents and present it in human-readable
format. I.e. generate report, send mail.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import time
import os.path
import smtplib
import email.mime.text
import email.mime.multipart
import email.utils
import logging
from datetime import datetime
import subprocess
import collections

from docutils.core import publish_string

import yaml

from . import common
from . import cache
from .beartype import beartype

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

    def report(self, groups: dict):
        """ Generate report """
        raise NotImplementedError()


def _rst_escape(text):
    return text.replace("\\", "\\\\").replace('`', '\\').replace("*", "\\*")


class AbstractTextOutput(AbstractOutput):
    """Simple text reporter"""

    @beartype
    def _format_item(self, content: dict):
        """ Generate section for one result """
        update_date = content['meta'].get('update_date')
        if update_date:
            date = time.strftime("%x %X", time.localtime(update_date))
            yield date
            yield "'" * len(date)

        if __debug__:
            yield '.. code::'
            yield ""
            yield "  META: " + str(content['meta'])
            yield "  DEBUG: " + str(content['debug'])
            yield ""

        if content:
            comparator_opts = content['meta'].get('comparator_opts') or {}
            content = content['content'].rstrip() or "<no data>"

            if comparator_opts.get(common.OPTS_PREFORMATTED):
                yield "::"
                yield ""
                for line in content.split("\n"):
                    yield "  " + line
            else:
                for line in content.split("\n"):
                    yield ""
                    yield _rst_escape(line)
        yield ""

    @beartype
    def _get_stats_str(self, groups: dict) ->str:
        """ Generate header """
        return ";  ".join(
            "*%s*: %d" % (title, len(items)) for title, items in [
                ("Changed", groups[common.STATUS_CHANGED]),
                ("New", groups[common.STATUS_NEW]),
                ("Unchanged", groups[common.STATUS_UNCHANGED]),
                ("Error", groups[common.STATUS_ERROR])
            ] if items)

    @beartype
    def _gen_section(self, title: str, items: list):
        """ Generate section (changed/new/errors/etc)"""
        if not items:
            return

        title = "%s [%d]" % (title, len(items))
        yield title
        yield '-' * len(title)
        yield
        for item in items:
            assert isinstance(item, list)
            assert len(item) > 0
            fitem = item[0]
            if fitem['title']:
                yield fitem['title']
                yield '^' * len(fitem['title'])
            for content in item:
                yield from self._format_item(content)
        yield ''

    @beartype
    def _mk_report(self, groups: dict):
        """ Generate whole report"""
        yield from [
            "========",
            " WebMon",
            "========",
            "",
            "Updated " + datetime.now().strftime("%x %X"),
            ""
        ]
        yield self._get_stats_str(groups)
        yield ""
        yield from self._gen_section("Changed",
                                        groups[common.STATUS_CHANGED])
        yield from self._gen_section("New", groups[common.STATUS_NEW])
        yield from self._gen_section("Errors", groups[common.STATUS_ERROR])
        yield from self._gen_section("Unchanged",
                                        groups[common.STATUS_UNCHANGED])
        yield from self._gen_footer()

    def _gen_footer(self):
        yield ""
        yield ".. footer:: " + (self.footer or str(datetime.now()))

    def report(self, items: dict):
        """ Generate report """
        raise NotImplementedError()


class TextFileOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "text"
    params = [
        ("file", "Destination file name", None, True),
    ]

    def report(self, items):
        _make_backup(self._conf["file"])
        try:
            with open(self._conf["file"], "w") as ofile:
                ofile.write("\n".join(part for part in self._mk_report(items)
                                      if part is not None))
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

    def report(self, items):
        _make_backup(self._conf["file"])
        content = self._mk_report(items)
        try:
            with open(self._conf["file"], "w") as ofile:
                html = publish_string(
                    "\n".join(line for line in content if line is not None),
                    writer_name='html',
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

    @beartype
    def report(self, items: dict):
        print("\n".join(item for item in self._mk_report(items)
                        if item is not None))


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

    @beartype
    def report(self, items: dict):
        conf = self._conf
        body = "\n".join(item for item in self._mk_report(items)
                         if item is not None)
        msg = self._get_msg(conf.get("html"), body)
        header = self._get_stats_str(items)
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


@beartype
def _get_output(name: str, params: dict):
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
        self._partials_dir = os.path.expanduser(args.partials_dir)

    def find_parts(self):
        files = collections.defaultdict(list)
        for fname in os.listdir(self._partials_dir):
            fpath = os.path.join(self._partials_dir, fname)
            if not os.path.isfile(fpath):
                continue
            oid, tstamp = fname.split('.', 1)
            files[oid].append((tstamp, fpath))
        return files

    @beartype
    def _load_file(self, fpath: str) -> dict:
        _LOG.debug("_load_file %r", fpath)
        with open(fpath, "r") as ifile:
            try:
                content = yaml.safe_load(ifile)
            except yaml.io.UnsupportedOperation:
                content = None
            if isinstance(content, dict) and \
                    'meta' in content and 'debug' in content and \
                    'content' in content and 'oid' in content and \
                    'title' in content and 'link' in content:
                return content
            _LOG.error("invalid file %s: %r", fpath, content)
        return None

    def write(self, footer=None):
        """ Write all reports; footer is optionally included. """
        _LOG.debug("OutputManager: writing...")

        data_by_status = {
            common.STATUS_NEW: [],
            common.STATUS_ERROR: [],
            common.STATUS_UNCHANGED: [],
            common.STATUS_CHANGED: [],
        }

        input_files = self.find_parts()
        for files in input_files.values():
            group_data = [self._load_file(fpath)
                          for _fst, fpath in sorted(files)]
            group_data = [item for item in group_data if item]
            status = common.STATUS_UNCHANGED
            if any(fdata['meta']['status'] == common.STATUS_CHANGED
                   for fdata in group_data):
                status = common.STATUS_CHANGED
            elif any(fdata['meta']['status'] == common.STATUS_NEW
                     for fdata in group_data):
                status = common.STATUS_NEW
            elif any(fdata['meta']['status'] == common.STATUS_ERROR
                     for fdata in group_data):
                status = common.STATUS_ERROR
            data_by_status[status].append(group_data)

        # TODO: sort data_by_status[] by name

        _LOG.debug("result: %r", data_by_status)

        for rep, conf in self._conf['output'].items():
            try:
                output = _get_output(rep, conf)
                if output:
                    output.report(data_by_status),
            except Exception as err:
                _LOG.exception("OutputManager: write %s error: %s", rep, err)

        # delete reported files
        for group in input_files.values():
            for _ts, fpath in group:
                try:
                    os.remove(fpath)
                except IOError as err:
                    _LOG.error("Remove %s file error: %s", fpath, err)

        _LOG.debug("OutputManager: write done")


def _make_backup(filename):
    if os.path.isfile(filename):
        os.rename(filename, filename + ".bak")


class Output(object):
    """Output store/load results.

    TODO: thread-safe
    """
    def __init__(self, working_dir: str):
        super(Output, self).__init__()
        self.working_dir = os.path.expanduser(working_dir)
        common.create_missing_dir(working_dir)

        self.stats = {
            common.STATUS_NEW: 0,
            common.STATUS_ERROR: 0,
            common.STATUS_UNCHANGED: 0,
            common.STATUS_CHANGED: 0
        }

    @beartype
    def put(self, part: common.Result, content: str):
        assert isinstance(part, common.Result)
        assert part.meta['status'] in self.stats, "Invalid status " + \
            str(part)
        self.stats[part.meta['status']] += 1
        dst_file = os.path.join(self.working_dir, part.oid + "." +
                                str(int(part.meta['update_date'])))

        outp = {
            'meta': part.meta,
            'debug': part.debug,
            'content': content,
            'oid': part.oid,
            'title': part.title,
            'link': part.link,
        }

        with open(dst_file, "w") as ofile:
            yaml.safe_dump(outp, ofile)

    @beartype
    def put_error(self, ctx: common.Context, err):
        # TODO: czy raportowanie globalnych błędów powinno być tutaj?
        result = common.Result(ctx.oid)
        result.set_error(err)
        self.put(result, None)
