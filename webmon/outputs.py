#!/usr/bin/python3
"""
Default outputs.
"""

import smtplib
import email.mime.text
import email.mime.multipart
import email.utils
import logging
from datetime import datetime
import subprocess

from docutils.core import publish_string

from . import common

_LOG = logging.getLogger(__name__)


class AbstractOutput(object):
    """Abstract/Base class for all outputs"""

    name = ""
    # parameters - list of tuples (name, description, default, required)
    params = []

    def __init__(self, conf):
        super(AbstractOutput, self).__init__()
        self.conf = {key: val for key, _, val, _ in self.params}
        self.conf.update(conf)

    def validate(self):
        for name, _, _, required in self.params or []:
            val = self.conf.get(name)
            if required and not val:
                raise common.ParamError("missing parameter " + name)

    def report(self, new, changed, errors, unchanged):
        """ Generate report """
        raise NotImplementedError()


def _rst_escape(text):
    return text.replace('`', '\\')


class AbstractTextOutput(AbstractOutput):
    """Simple text reporter"""

    def _format_item(self, inp, content, context):
        """ Generate section for one input """
        title = context["name"]
        yield title
        yield "'" * len(title)
        if 'url' in inp:
            yield inp['url']
        if content:
            content = content.strip() or "<no data>"
            content = content.replace(common.PART_LINES_SEPARATOR, "\n")
            if context.get(common.OPTS_PREFORMATTED):
                yield "::"
                yield ""
                for line in content.split("\n"):
                    yield "  " + _rst_escape(line)
                yield ""
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
        for inp, content, context in items:
            yield from self._format_item(inp, content, context)
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
        yield str(datetime.now())


class TextFileOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "text"
    params = [
        ("file", "Destination file name", None, True),
    ]

    def report(self, new, changed, errors, unchanged):
        try:
            with open(self.conf["file"], "w") as ofile:
                ofile.write("\n".join(self._mk_report(new, changed, errors,
                                                      unchanged)))
        except IOError as err:
            raise common.ReportGenerateError(
                "Writing report file %s error : %s" %
                (self.conf['file'], err))


class HtmlFileOutput(AbstractTextOutput):
    """Simple html reporter"""

    name = "html"
    params = [
        ("file", "Destination file name", None, True),
    ]

    def report(self, new, changed, errors, unchanged):
        content = self._mk_report(new, changed, errors, unchanged)
        try:
            with open(self.conf["file"], "w") as ofile:
                html = publish_string("\n".join(content), writer_name='html')
                ofile.write(html.decode('utf-8'))
        except IOError as err:
            raise common.ReportGenerateError(
                "Writing report file %s error : %s" %
                (self.conf['file'], err))


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
        conf = self.conf
        if conf.get("smtp_login"):
            if not conf.get("smtp_password"):
                raise common.ParamError("missing password for login")
        if conf.get("smtp_tls") and conf.get("smtp_ssl"):
            _LOG.warning("configured tls and ssl; using ssl")

        encrypt = self.conf.get("encrypt", "")
        if encrypt and encrypt not in ('gpg', ):
            raise common.ParamError("invalid encrypt parameter: %r" % encrypt)

    def report(self, new, changed, errors, unchanged):
        conf = self.conf
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
        if self.conf.get("encrypt") == 'gpg':
            body = self._encrypt(body)
        if gen_html:
            msg = email.mime.multipart.MIMEMultipart('alternative')
            msg.attach(email.mime.text.MIMEText(body, 'plain', 'utf-8'))

            html = publish_string(body, writer_name='html').decode('utf-8')
            msg.attach(email.mime.text.MIMEText(html, 'html', 'utf-8'))
            return msg
        return email.mime.text.MIMEText(body, 'plain', 'utf-8')


    def _encrypt(self, message):
        subp = subprocess.Popen(["gpg", "-e", "-a", "-r", self.conf["to"]],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = subp.communicate(message.encode('utf-8'))
        if subp.wait(60) != 0:
            _LOG.error("email output encrypt error: %s", stderr)
            return stderr
        return stdout



def _get_output(name, params):
    _LOG.debug("_get_output %s", name)
    if not params.get("enabled", True):
        return None

    rcls = common.find_subclass(AbstractOutput, name)
    if rcls:
        out = rcls(params)
        out.validate()
        return out

    _LOG.warning("unknown output: %s", name)


class Output(object):
    def __init__(self, conf):
        super(Output, self).__init__()
        self.conf = conf
        self._outputs = []
        self._new = []
        self._changed = []
        self._unchanged = []
        self._errors = []
        for repname, repconf in (conf or {}).items():
            try:
                rep = _get_output(repname, repconf or {})
                if rep:
                    self._outputs.append(rep)
            finally:
                pass

    @property
    def valid(self):
        return bool(self._outputs)

    def add_new(self, inp, content, context):
        #_LOG.debug("Output.add_new: %r, %r, %r", inp, content, context)
        self._new.append((inp, content, context))

    def add_changed(self, inp, diff, context):
        #_LOG.debug("Output.add_changed: %r, %r, %r", inp, diff, context)
        self._changed.append((inp, diff, context))

    def add_error(self, inp, error, context):
        #_LOG.debug("Output.add_error: %r, %r, %r", inp, error, context)
        self._errors.append((inp, error, context))

    def add_unchanged(self, inp, content, context):
        #_LOG.debug("Output.add_unchanged: %r, %r, %r", inp, content, context)
        self._unchanged.append((inp, content, context))

    def write(self):
        if not (self.conf.get("report_unchanged") or self._new
                or self._changed or self._errors):
            return
        for rep in self._outputs:
            try:
                rep.report(self._new, self._changed, self._errors,
                           self._unchanged)
            except Exception as err:
                _LOG.error("Output.end %s error: %s", rep, err)
