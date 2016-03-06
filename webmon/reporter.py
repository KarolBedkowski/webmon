#!/usr/bin/python3


class AbstractReporter(object):
    """docstring for Reporter"""
    def __init__(self, conf):
        super(AbstractReporter, self).__init__()
        self.conf = conf

    def begin(self):
        pass

    def end(self):
        pass

    def report_raw(self, inp, title, content):
        pass

    def report_new(self, inp, content):
        self.report_raw(inp, "New: " + inp['name'], content)

    def report_changed(self, inp, diff):
        self.report_raw(inp, "CHANGED: " + inp['name'], diff)

    def report_error(self, inp, error):
        self.report_raw(inp, "ERR: " + inp['name'], error)

    def report_unchanged(self, inp):
        self.report_raw(inp, "UNCHANGED: " + inp['name'], None)


class TextReporter(AbstractReporter):
    """Simple text reporter"""
    def __init__(self, conf):
        super(TextReporter, self).__init__(conf)
        if not conf.get("file"):
            raise ValueError("missing 'file' parameter")
        self._ofile = None

    def begin(self):
        self._ofile = open(self.conf["file"], "w")

    def end(self):
        self._ofile.close()

    def report_raw(self, inp, title, content):
        self._ofile.write(title)
        self._ofile.write("\n")
        if content:
            self._ofile.write("\n")
            self._ofile.write(content)
            self._ofile.write("\n")
            self._ofile.write("----------------------------\n\n")


class ConsoleReporter(AbstractReporter):
    """Simple text reporter"""
    def __init__(self, conf):
        super(ConsoleReporter, self).__init__(conf)

    def report_raw(self, inp, title, content):
        print(title)
        print("\n")
        if content:
            print("\n")
            print(content)
            print("\n")
            print("----------------------------\n\n")


def get_reporter(name, params):
    if name == "console":
        return ConsoleReporter(params)
    if name == "text":
        return TextReporter(params)
    return None
