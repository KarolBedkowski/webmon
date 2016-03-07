#!/usr/bin/python3

import smtplib
import email.mime.text
import email.utils
import logging


_LOG = logging.getLogger(__name__)


class AbstractOutput(object):
    """docstring for Reporter"""

    _required_params = None

    def __init__(self, conf):
        super(AbstractOutput, self).__init__()
        self.conf = conf
        self.cnt_changed = 0
        self.cnt_unchanged = 0
        self.cnt_new = 0
        self.cnt_error = 0

    @property
    def _changed(self):
        return self.cnt_changed or self.cnt_error or self.cnt_new

    def validate(self):
        for param in self._required_params or []:
            if not self.conf.get(param):
                raise ValueError("missing parameter " + param)

    def begin(self):
        pass

    def end(self):
        pass

    def report_raw(self, inp, title, content):
        pass

    def report_new(self, inp, content):
        self.cnt_new += 1
        self.report_raw(inp, "New: " + inp['name'], content)

    def report_changed(self, inp, diff):
        self.cnt_changed += 1
        self.report_raw(inp, "CHANGED: " + inp['name'], diff)

    def report_error(self, inp, error):
        self.cnt_error += 1
        self.report_raw(inp, "ERR: " + inp['name'], error)

    def report_unchanged(self, inp):
        self.cnt_unchanged += 1
        self.report_raw(inp, "UNCHANGED: " + inp['name'], None)


class AbstractTextOutput(AbstractOutput):
    """Simple text reporter"""

    def __init__(self, conf):
        super(AbstractTextOutput, self).__init__(conf)
        self._body = []

    def report_raw(self, inp, title, content):
        self._body.append(title)
        self._body.append("")
        if content:
            self._body.append("")
            self._body.append(content)
            self._body.append("")
            self._body.append("----------------------------")
            self._body.append("")


class TextFileOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "text"
    _required_params = ("file", )

    def end(self):
        with open(self.conf["file"], "w") as ofile:
            if not self._changed and (not self.cnt_changed or
                                      not self.conf.get("report_all")):
                return
            for line in self._body:
                ofile.write(line)
                ofile.write("\n")


class ConsoleOutput(AbstractTextOutput):
    """Simple text reporter"""

    name = "console"

    def end(self):
        if not self._changed and (not self.cnt_changed or
                                  not self.conf.get("report_all")):
            return
        for line in self._body:
            print(line)


class EMailOutput(AbstractTextOutput):
    """docstring for MailOutput"""

    name = "email"
    _required_params = ("to", "from", "subject",
                        "smtp_host", "smtp_port")

    def end(self):
        if not self._body:
            return
        if not self._changed and (not self.cnt_changed or
                                  not self.conf.get("report_all")):
            return
        body = "\n".join(self._body)
        msg = email.mime.text.MIMEText(body, 'plain', 'utf-8')
        conf = self.conf
        msg['Subject'] = conf["subject"]
        msg['From'] = conf["from"]
        msg['To'] = conf["to"]
        msg['Date'] = email.utils.formatdate()
        smtp = smtplib.SMTP()
        smtp.connect(conf["smtp_host"], conf["smtp_port"])
        smtp.ehlo()
        if conf.get("smtp_tls"):
            smtp.starttls()
        if conf["smtp_login"]:
            smtp.login(conf["smtp_login"], conf["smtp_password"])
        smtp.sendmail(msg['From'], [msg['To']], msg.as_string())
        smtp.quit()


def get_output(name, params):
    _LOG.debug("get_output %s", name)
    if not params.get("enabled", True):
        return None

    def find(parent_cls):
        for rcls in getattr(parent_cls, "__subclasses__")():
            if hasattr(rcls, "name") and getattr(rcls, 'name') == name:
                out = rcls(params)
                out.validate()
                return out
            # find in subclasses
            out = find(rcls)
            if out:
                return out

        return None

    return find(AbstractOutput)


class Output(object):
    def __init__(self, conf):
        super(Output, self).__init__()
        self.conf = conf
        self._reps = []
        for repname, repconf in (conf or {}).items():
            rep = get_output(repname, repconf or {})
            if rep:
                rep.begin()
                self._reps.append(rep)

    def report_new(self, inp, content):
        for rep in self._reps:
            rep.report_new(inp, content)

    def report_changed(self, inp, diff):
        for rep in self._reps:
            rep.report_changed(inp, diff)

    def report_error(self, inp, error):
        for rep in self._reps:
            rep.report_error(inp, error)

    def report_unchanged(self, inp):
        for rep in self._reps:
            rep.report_unchanged(inp)

    def end(self):
        for rep in self._reps:
            rep.end()
