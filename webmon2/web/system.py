#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Web gui
"""

import logging

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash
)

from webmon2.web import get_db


_LOG = logging.getLogger(__name__)
BP = Blueprint('system', __name__, url_prefix='/system')


@BP.route('/settings', methods=["POST", "GET"])
def settings():
    db = get_db()
    settings = list(db.get_settings())
    if request.method == 'POST':
        for sett in settings:
            if sett.key in request.form:
                sett.set_value(request.form[sett.key])
        db.save_settings(settings)
        flash("Settings saved")
        return redirect(url_for("system.settings"))

    return render_template("system/settings.html", settings=settings)
