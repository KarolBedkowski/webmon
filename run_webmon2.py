#!/usr/bin/python3 -X dev
"""
Copyright (c) Karol Będkowski, 2016-2022

This file is part of webmon.
Licence: GPLv2+
"""

from webmon2 import main

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2022"

try:
    import stackprinter

    stackprinter.set_excepthook(style="color")
except ImportError:
    try:
        from rich.traceback import install

        install()
    except ImportError:
        pass
try:
    import icecream

    icecream.install()
    icecream.ic.configureOutput(includeContext=True)
except ImportError:  # Graceful fallback if IceCream isn't installed.
    pass

if __name__ == "__main__":
    main.main()
