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
    Blueprint, render_template, redirect, url_for, request, flash, session
)

from webmon2.web import get_db


_LOG = logging.getLogger(__name__)
BP = Blueprint('system', __name__, url_prefix='/system')


@BP.route('/settings/', methods=["POST", "GET"])
def sett_index():
    return redirect(url_for("system.sett_user"))


@BP.route('/settings/globals', methods=["POST", "GET"])
def sett_globals():
    db = get_db()
    user_id = session['user']
    settings = list(db.get_settings(user_id))
    if request.method == 'POST':
        for sett in settings:
            if sett.key in request.form:
                sett.set_value(request.form[sett.key])
        db.save_settings(settings)
        flash("Settings saved")
        return redirect(url_for("system.globals"))

    return render_template("system/globals.html", settings=settings)


@BP.route('/settings/user', methods=["POST", "GET"])
def sett_user():
    if request.method == 'POST':
        if request.form['new_password1'] != request.form['new_password2']:
            flash("passwords not match")
        elif not request.form['new_password1']:
            flash("missing new password")
        elif not request.form['curr_password']:
            flash("missing curr_password password")
        else:
            db = get_db()
            user = db.get_user(id_=session['user'])
            if user.verify_password(request.form['curr_password']):
                user.hash_password(request.form['new_password1'])
                db.save_user(user)
                flash("password changed")
            else:
                flash("wrong current password")
    return render_template("system/user.html")
