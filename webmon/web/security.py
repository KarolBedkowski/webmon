#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
App security
"""
import logging

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, session
)


from webmon.web import get_db


_LOG = logging.getLogger(__name__)
BP = Blueprint('sec', __name__, url_prefix='/sec')


@BP.route('/login', methods=["POST", "GET"])
def login():
    if request.method == 'POST':
        flogin = request.form['login']
        fpassword = request.form['password']
        db = get_db()
        user = db.get_user(login=flogin)
        if user and user.active and user.verify_password(fpassword):
            session['user'] = user.id
            session['user_admin'] = bool(user.admin)
            return redirect(
                request.form.get('back', url_for('browser.index')))
        flash("Invalid user and/or password")

    return render_template("login.html", )
