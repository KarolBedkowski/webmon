#!/usr/bin/python3
"""
Default outputs.
Output get new/changed/deleted contents and present it in human-readable
format. I.e. generate report, send mail.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import collections
import email.mime.multipart
import email.mime.text
import email.utils
import logging
import os.path
import smtplib
import subprocess
import time
import typing as ty
from datetime import datetime
import textwrap

from docutils.core import publish_string

import yaml
import typecheck as tc

from . import (common, metrics)

_LOG = logging.getLogger("outputs")

_DOCUTILS_HTML_OVERRIDES = {
    'stylesheet_path': os.path.join(os.path.dirname(__file__), "main.css")
}


class AbstractOutput(object):
    """Abstract/Base class for all outputs"""

    name = ""
    # parameters - list of tuples (name, description, default, required)
    params = []  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def __init__(self, conf: dict) -> None:
        super().__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self._conf = common.apply_defaults(
            {key: val for key, _d, val, _r in self.params},
            conf)

    def dump_debug(self):
        return " ".join(("<", self.__class__.__name__, self.name,
                         repr(self._conf), ">"))

    def validate(self):
        for name, _, _, required in self.params or []:
            val = self._conf.get(name)
            if required and not val:
                raise common.ParamError("missing parameter " + name)

    def report(self, groups: dict, footer: ty.Optional[str]=None):
        """ Generate report """
        raise NotImplementedError()


@tc.typecheck
def rst_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('`', '\\').replace("*", "\\*").\
        replace('_', '\\_')


_RST_HEADERS_CHARS = ('=', '-', '`', "'")


@tc.typecheck
def yield_rst_header(text: str, level: int) -> ty.Iterable[str]:
    if text:
        yield ''
        yield text
        yield _RST_HEADERS_CHARS[level] * len(text)
        yield ''


def wrap_debug_info(text: str) -> str:
    return textwrap.fill(text, width=150, break_long_words=False,
                         break_on_hyphens=False, initial_indent='  ',
                         subsequent_indent='          ')


def text_to_rst(text: str) -> ty.Iterable[str]:
    """Do some magic to convert given `text` to valid rst output.
    For now: remove common indent from all lines; add empty lines before indent
    changes; remove doubled empty lines.
    """
    last_indent = ""
    last_empty_line = False
    text = textwrap.dedent(text)
    for line in text.split('\n'):
        if not line and not last_empty_line:
            yield ""
            last_empty_line = True
            continue
        indent = common.get_whitespace_prefix(line)
        if indent != last_indent and not last_empty_line:
            # add empty line when indent changed
            yield ""
        last_indent = indent
        last_empty_line = False
        yield rst_escape(line)


class AbstractTextOutput(AbstractOutput):
    """Simple text reporter"""

    def _format_item_header(self, item: dict) -> str:
        update_date = item['meta'].get('update_date')
        if update_date:
            yield time.strftime("%x %X", time.localtime(update_date))
        yield "*" + common.status_human_str(item['meta']['status']) + "*"

    @tc.typecheck
    def _format_item(self, item: dict, show_header: bool):
        """ Generate section for one result """
        if show_header:
            yield from yield_rst_header(
                ' '.join(self._format_item_header(item)), 3)

        header = item.get('header')
        if header:
            yield from text_to_rst(str(header))
            yield ''

        link = item.get('link')
        if link:
            yield link
            yield ''

        comparator_opts = item['meta'].get('comparator_opts') or {}
        content = item['content'].rstrip() or "<no data>"

        if comparator_opts.get(common.OPTS_PREFORMATTED):
            yield "::"
            for sec in content.split(common.RECORD_SEPARATOR):
                yield ""
                yield from ("  " + line for line in sec.split("\n"))
        else:
            for sec in content.split(common.RECORD_SEPARATOR):
                yield from text_to_rst(sec)
                yield ''
        yield ""

        footer = item.get('footer')
        if footer:
            yield '*' + rst_escape(str(footer)) + '*'
            yield ''

        if self._conf.get('_debug'):
            yield '.. code::'
            yield ""
            yield wrap_debug_info("OID: " + str(item['oid']))
            yield wrap_debug_info("META: " + str(item['meta']))
            yield wrap_debug_info("DEBUG: " + str(item['debug']))
            yield ""

    @tc.typecheck
    def _get_stats_str(self, groups: dict) ->str:
        """ Generate header """
        return ";  ".join(
            "*%s*: %d" % (title, len(items)) for title, items in [
                ("Changed", groups[common.STATUS_CHANGED]),
                ("New", groups[common.STATUS_NEW]),
                ("Unchanged", groups[common.STATUS_UNCHANGED]),
                ("Error", groups[common.STATUS_ERROR])
            ] if items)

    @tc.typecheck
    def _gen_section(self, title: str, items: list):
        """ Generate section (changed/new/errors/etc)"""
        if not items:
            return

        yield from yield_rst_header("%s [%d]" % (title, len(items)), 1)
        for item in items:
            assert isinstance(item, list)
            assert len(item) > 0
            fitem = item[-1]
            yield from yield_rst_header(fitem['title'], 2)
            show_items_headers = len(item) > 1
            for content in item:
                yield from self._format_item(content, show_items_headers)
        yield ''

    @tc.typecheck
    def _mk_report(self, groups: dict, footer=None):
        """ Generate whole report"""
        yield "========"
        yield " WebMon"
        yield "========"
        yield ""
        yield "Updated " + datetime.now().strftime("%x %X")
        yield ""
        yield self._get_stats_str(groups)
        yield ""
        yield from self._gen_section("Changed",
                                     groups[common.STATUS_CHANGED])
        yield from self._gen_section("New", groups[common.STATUS_NEW])
        yield from self._gen_section("Errors", groups[common.STATUS_ERROR])
        yield from self._gen_section("Unchanged",
                                     groups[common.STATUS_UNCHANGED])
        yield ""
        yield ".. footer:: " + (footer or str(datetime.now()))

    def report(self, items: dict, footer: ty.Optional[str]=None):
        """ Generate report """
        raise NotImplementedError()


class TextFileOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "text"
    params = [
        ("file", "Destination file name", None, True),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def report(self, items, footer: ty.Optional[str]=None):
        filename = common.prepare_filename(self._conf["file"])
        _make_backup(filename)
        try:
            with open(filename, "w") as ofile:
                ofile.write("\n".join(self._mk_report(items, footer)))
        except IOError as err:
            raise common.ReportGenerateError(
                self, "Writing report file %s error : %s" %
                (self._conf['file'], err))


class HtmlFileOutput(AbstractTextOutput):
    """Simple html reporter"""

    name = "html"
    params = [
        ("file", "Destination file name", None, True),
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def report(self, items, footer: ty.Optional[str]=None):
        filename = common.prepare_filename(self._conf["file"])
        _make_backup(filename)
        try:
            with open(filename, "w") as ofile:
                html = publish_string(
                    "\n".join(self._mk_report(items, footer)),
                    writer_name='html',
                    settings=None,
                    settings_overrides=_DOCUTILS_HTML_OVERRIDES)
                ofile.write(html.decode('utf-8'))
        except IOError as err:
            raise common.ReportGenerateError(
                self, "Writing report file %s error : %s" %
                (self._conf['file'], err))


class ConsoleOutput(AbstractTextOutput):
    """Display report on console"""

    name = "console"

    @tc.typecheck
    def report(self, items: dict, footer: ty.Optional[str]=None):
        print("\n".join(self._mk_report(items, footer)))


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
    ]  # type: List[ty.Tuple[str, str, ty.Any, bool]]

    def validate(self):
        super().validate()
        conf = self._conf
        if conf.get("smtp_login"):
            if not conf.get("smtp_password"):
                raise common.ParamError("missing password for login")
        if conf.get("smtp_tls") and conf.get("smtp_ssl"):
            self._log.warning("EMailOutput: configured tls and ssl; using ssl")

        encrypt = self._conf.get("encrypt", "")
        if encrypt and encrypt not in ('gpg', ):
            raise common.ParamError("invalid encrypt parameter: %r" % encrypt)

    @tc.typecheck
    def report(self, items: dict, footer: ty.Optional[str]=None):
        conf = self._conf
        body = "\n".join(self._mk_report(items, footer))
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
            raise common.ReportGenerateError(self,
                                             "Sending mail error: %s" % err)
        finally:
            smtp.quit()

    def _get_msg(self, gen_html: bool, body: str) -> ty.Any:
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

    def _encrypt(self, message: str) -> str:
        subp = subprocess.Popen(["gpg", "-e", "-a", "-r", self._conf["to"]],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = subp.communicate(message.encode('utf-8'))
        if subp.wait(60) != 0:
            self._log.error("EMailOutput: encrypt error: %s", stderr)
            return stderr
        return stdout


@tc.typecheck
def _get_output(name: str, params: dict) -> ty.Optional[AbstractOutput]:
    _LOG.debug("_get_output %r", name)
    if not params.get("enabled", True):
        return None

    rcls = common.find_subclass(AbstractOutput, name)
    if rcls:
        out = rcls(params)
        out.validate()
        return out

    _LOG.warning("unknown output: %s", name)


@tc.typecheck
def qualify_item_to_status(group: ty.Iterable) -> str:
    """ Qualify items to one of the groups by status.
    Items in list can have various statuses
    """
    for status in (common.STATUS_CHANGED, common.STATUS_NEW,
                   common.STATUS_ERROR):
        if any(fdata['meta']['status'] == status for fdata in group):
            return status
    return common.STATUS_UNCHANGED


class OutputManager(object):
    """ Object group all outputs. """
    def __init__(self, conf, working_dir: str) -> None:
        super().__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self._conf = conf
        self._working_dir = os.path.expanduser(working_dir)
        common.create_missing_dir(working_dir)

    def find_parts(self) -> ty.ValuesView:
        """ Find all files generated by inputs.
        Returns:
            [ file path ]
        """
        files = collections.defaultdict(list)
        # type: ty.DefaultDict[str, ty.List[ty.Tuple[str, str]]]
        for fname in sorted(os.listdir(self._working_dir)):
            fpath = os.path.join(self._working_dir, fname)
            if not os.path.isfile(fpath):
                continue
            oid = fname.split('.', 1)[0]
            if len(oid) == 40:
                files[oid].append(fpath)
        return files.values()

    @tc.typecheck
    def _load_file(self, fpath: str) -> dict:
        self._log.debug("_load_file %r", fpath)
        with open(fpath, "r") as ifile:
            try:
                content = yaml.safe_load(ifile)
            except yaml.io.UnsupportedOperation:
                content = None
            else:
                if isinstance(content, dict) and \
                        'meta' in content and 'content' in content and \
                        'oid' in content and 'title' in content:
                    self._log.debug("_load_file: %r", content)
                    return content
            self._log.error("invalid file %s: %r", fpath, content)
        return None

    def write(self, footer=None, debug: bool=False):
        """ Write all reports; footer is optionally included. """
        self._log.debug("OutputManager: writing...")
        gstart = time.time()

        data_by_status = {
            common.STATUS_NEW: [],
            common.STATUS_ERROR: [],
            common.STATUS_UNCHANGED: [],
            common.STATUS_CHANGED: [],
        }  # type: dict[str, list]

        input_files = self.find_parts()
        for files in input_files:
            group_data = list(filter(None, map(self._load_file, files)))
            status = qualify_item_to_status(group_data)
            data_by_status[status].append(group_data)

        all_items = 0
        # sort by input index
        for items in data_by_status.values():
            items.sort(key=lambda x: x[0].get('index', 0))
            all_items += len(items)

        if not all_items:
            self._log.info("no new reports")
            return

        all_ok = True

        for rep, conf in self._conf['output'].items():
            conf['_debug'] = debug
            start = time.time()
            try:
                output = _get_output(rep, conf)
                if output:
                    output.report(data_by_status, footer)
                    metrics.COLLECTOR.put_output(
                        rep, time.time() - start, "success")
            except Exception as err:
                metrics.COLLECTOR.put_output(rep, time.time() - start,
                                             "error")
                self._log.exception("OutputManager: write %s error: %s",
                                    rep, err)
                all_ok = False

        # delete reported files
        if all_ok:
            try:
                map(os.remove, (fpath for group in input_files
                                for fpath in group))
            except IOError as err:
                self._log.error("Remove file error: %s", err)

        self._log.debug("OutputManager: write done")

        metrics.COLLECTOR.put_output_summary(all_items, len(input_files),
                                             time.time() - gstart)

    @tc.typecheck
    def put(self, part: common.Result, content: str):
        assert isinstance(part, common.Result)
        dst_file = os.path.join(self._working_dir, part.oid + "." +
                                str(int(part.meta['update_date'])))

        outp = {
            'meta': part.meta,
            'debug': part.debug,
            'content': content,
            'oid': part.oid,
            'title': part.title,
            'link': part.link,
            'footer': part.footer,
            'header': part.header,
            'index': part.index,
        }

        with open(dst_file, "w") as ofile:
            yaml.safe_dump(outp, ofile)

    @tc.typecheck
    def put_error(self, ctx: common.Context, err):
        result = common.Result(ctx.oid, ctx.input_idx)
        result.set_error(err)
        self.put(result, None)


def _make_backup(filename):
    if os.path.isfile(filename):
        os.rename(filename, filename + ".bak")
