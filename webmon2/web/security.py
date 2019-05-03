#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
App security
"""
import logging

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, session
)

from webmon2 import database
from webmon2.web import get_db


_LOG = logging.getLogger(__name__)
BP = Blueprint('sec', __name__, url_prefix='/sec')


@BP.route('/login', methods=["POST", "GET"])
def login():
    if request.method == 'POST':
        flogin = request.form['login']
        fpassword = request.form['password']
        db = get_db()
        user = database.users.get(db, login=flogin)
        if user and user.active and user.verify_password(fpassword):
            session['user'] = user.id
            session['user_admin'] = bool(user.admin)
            session.permanent = True
            session.modified = True
            return redirect(
                request.form.get('back', url_for('root.index')))
        flash("Invalid user and/or password")

    return render_template("login.html", )


@BP.route('/logout')
def logout():
    del session['user']
    del session['user_admin']
    session.modified = True
    return redirect(url_for('root.index'))
