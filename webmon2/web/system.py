#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Web gui
"""

import logging

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, session,
    make_response
)

from webmon2.web import get_db
from webmon2 import database, imp_exp


_LOG = logging.getLogger(__name__)
BP = Blueprint('system', __name__, url_prefix='/system')


@BP.route('/settings/', methods=["POST", "GET"])
def sett_index():
    return redirect(url_for("system.sett_user"))


@BP.route('/settings/globals', methods=["POST", "GET"])
def sett_globals():
    db = get_db()
    user_id = session['user']
    settings = list(database.settings.get_all(db, user_id))
    if request.method == 'POST':
        for sett in settings:
            if sett.key in request.form:
                sett.set_value(request.form[sett.key])
            sett.user_id = user_id
        database.settings.save_all(db, settings)
        db.commit()
        flash("Settings saved")
        return redirect(url_for("system.sett_globals"))

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
            user = database.users.get(db, id_=session['user'])
            if user.verify_password(request.form['curr_password']):
                user.hash_password(request.form['new_password1'])
                database.users.save(db, user)
                db.commit()
                flash("password changed")
            else:
                flash("wrong current password")
    return render_template("system/user.html")


@BP.route('/settings/data')
def sett_data():
    return render_template("system/data.html")


@BP.route('/settings/data/export')
def sett_data_export():
    db = get_db()
    user_id = session['user']
    content = imp_exp.dump_export(db, user_id)
    headers = {"Content-Disposition": "attachment; filename=dump.json"}
    return make_response((content, headers))


@BP.route('/settings/data/import', methods=["POST"])
def sett_data_import():
    if 'file' not in request.files:
        flash('No file to import')
        return redirect(url_for("system.sett_data"))

    file = request.files['file']
    data = file.read()
    if not data:
        flash('No file to import')
        return redirect(url_for("system.sett_data"))

    db = get_db()
    user_id = session['user']
    try:
        imp_exp.dump_import(db, user_id, data)
        db.commit()
        flash("import completed")
    except Exception as err:  # pylint: disable=broad-except
        flash("Error importing file: " + str(err))
        _LOG.exception("import file error")
    return redirect(url_for("system.sett_data"))
