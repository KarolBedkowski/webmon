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
    # list of required parameters
    _required_params = None

    def __init__(self, conf):
        super(AbstractOutput, self).__init__()
        self.conf = conf

    def validate(self):
        for param in self._required_params or []:
            if not self.conf.get(param):
                raise common.ParamError("missing parameter " + param)

    def report(self, new, changed, errors, unchanged):
        """ Generate report """
        raise NotImplementedError()


class AbstractTextOutput(AbstractOutput):
    """Simple text reporter"""

    def _format_item(self, inp, content):
        """ Generate section for one input """
        title = inp["name"]
        yield title
        yield "^" * len(title)
        if 'url' in inp:
            yield inp['url']
        if content:
            content = content.strip() or "<no data>"
            yield "::"
            yield ""
            for line in content.split("\n"):
                yield "  " + line
            yield ""
        yield ""

    def _get_stats_str(self, new, changed, errors, unchanged):
        """ Generate header """
        out = []
        if changed:
            out.append("Changed: %d" % len(changed))
        if new:
            out.append("New: %d" % len(new))
        if unchanged:
            out.append("Unchanged: %d" % len(unchanged))
        if errors:
            out.append("Error: %d" % len(errors))
        return ";  ".join(out)

    def _gen_section(self, title, items):
        """ Generate section for group of inputs """
        title = "%s [%d] " % (title, len(items))
        yield title
        yield '-' * len(title)
        for inp, content in items:
            yield from self._format_item(inp, content)

    def _mk_report(self, new, changed, errors, unchanged):
        """ Generate whole report"""
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


class TextFileOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "text"
    _required_params = ("file", )

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
    _required_params = ("file", )

    def report(self, new, changed, errors, unchanged):
        content = [
            "========",
            " WebMon",
            "========",
            "",
            "Updated " + datetime.now().strftime("%x %X"),
            ""
        ]
        content.extend(self._mk_report(new, changed, errors, unchanged))
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
    _required_params = ("to", "from", "subject", "smtp_host", "smtp_port")

    def validate(self):
        super(EMailOutput, self).validate()
        conf = self.conf
        if conf.get("smtp_login"):
            if not conf.get("smtp_password"):
                raise common.ParamError("missing password for login")
        if conf.get("smtp_tls") and conf.get("smtp_ssl"):
            _LOG.warning("configured tls and ssl; using ssl")

        encrypt = self.conf.get("encrypt", "")
        if encrypt not in ('gpg', ""):
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
        subp = subprocess.run(["gpg", "-e", "-a", "-r", self.conf["to"]],
                              input=message.encode('utf-8'),
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

        if subp.returncode != 0:
            err = subp.stderr
            _LOG.error("email output encrypt error: %s", err)
            return err
        return subp.stdout



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
        self._reps = []
        self._new = []
        self._changed = []
        self._unchanged = []
        self._errors = []
        for repname, repconf in (conf or {}).items():
            try:
                rep = _get_output(repname, repconf or {})
                if rep:
                    self._reps.append(rep)
            finally:
                pass

    @property
    def valid(self):
        return bool(self._reps)

    def add_new(self, inp, content):
        self._new.append((inp, content))

    def add_changed(self, inp, diff):
        self._changed.append((inp, diff))

    def add_error(self, inp, error):
        self._errors.append((inp, error))

    def add_unchanged(self, inp):
        self._unchanged.append((inp, None))

    def write(self):
        if not (self.conf.get("report_unchanged") or self._new
                or self._changed or self._errors):
            return
        for rep in self._reps:
            try:
                rep.report(self._new, self._changed, self._errors,
                           self._unchanged)
            except Exception as err:
                _LOG.error("Output.end %s error: %s", rep, err)
