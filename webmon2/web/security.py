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
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
)

from webmon2 import database
from webmon2.web import get_db


_LOG = logging.getLogger(__name__)
BP = Blueprint("sec", __name__, url_prefix="/sec")


@BP.route("/login", methods=["POST", "GET"])
def login():
    if "temp_user_id" in session:
        del session["temp_user_id"]
    if "temp_redirect" in session:
        del session["temp_redirect"]
    session.modified = True

    if request.method == "POST":
        flogin = request.form["login"]
        fpassword = request.form["password"]
        db = get_db()
        user = database.users.get(db, login=flogin)
        if user and user.active and user.verify_password(fpassword):
            if user.totp:
                session["temp_user_id"] = user.id
                session["temp_redirect"] = request.args.get("back")
                session.modified = True
                return redirect(url_for("sec.login_totp"))

            session["user"] = user.id
            session["user_admin"] = bool(user.admin)
            session.permanent = True
            session.modified = True

            return redirect(request.args.get("back", url_for("root.index")))
        flash("Invalid user and/or password")

    return render_template("login.html")


@BP.route("/login/totp", methods=["POST", "GET"])
def login_totp():
    user_id = session["temp_user_id"]
    if request.method == "POST":
        ftotp = request.form["otp"]
        db = get_db()
        user = database.users.get(db, user_id)
        if user and user.active and user.verify_totp(ftotp):
            back = session["temp_redirect"]
            session["user"] = user.id
            session["user_admin"] = bool(user.admin)
            del session["temp_user_id"]
            del session["temp_redirect"]
            session.permanent = True
            session.modified = True
            return redirect(back or url_for("root.index"))

        flash("Invalid TOTP answer")

    return render_template("login.totp.html")


@BP.route("/logout")
def logout():
    del session["user"]
    del session["user_admin"]
    session.modified = True
    return redirect(url_for("root.index"))
