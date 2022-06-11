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
import typing as ty

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import gettext

from webmon2 import database, model, security

from . import _commons as c

_LOG = logging.getLogger(__name__)
BP = Blueprint("sec", __name__, url_prefix="/sec")


@BP.route("/login", methods=["POST", "GET"])
def login() -> ty.Any:
    if "temp_user_id" in session:
        del session["temp_user_id"]

    if "user" in session:
        del session["user"]

    # regenerate new csrf token
    c.generate_csrf_token()

    session.modified = True

    if request.method == "POST":
        flogin = request.form["login"]
        fpassword = request.form["password"]
        db = c.get_db()
        try:
            user = database.users.get(db, login=flogin)
        except database.NotFound:
            flash(gettext("Invalid user and/or password"))
            return render_template("login.html")

        assert user.password is not None
        if user.active and security.verify_password(user.password, fpassword):
            session["_user_tz"] = request.form["_user_tz"]
            if user.totp and security.otp_available():
                session["temp_user_id"] = user.id
                session.permanent = False
                return redirect(url_for("sec.login_totp"))

            back = session.get("_back_url")
            if back:
                del session["_back_url"]

            _after_login(user)
            return redirect(back or url_for("root.index"))

        flash(gettext("Invalid user and/or password"))

    return render_template("login.html")


@BP.route("/login/totp", methods=["POST", "GET"])
def login_totp() -> ty.Any:
    # regenerate new csrf token
    c.generate_csrf_token()

    if request.method == "POST":
        db = c.get_db()
        try:
            user = database.users.get(db, session["temp_user_id"])
        except database.NotFound:
            return render_template("login.totp.html")

        assert user.totp is not None
        ftotp = request.form["otp"]
        if user and user.active and security.verify_totp(user.totp, ftotp):
            back = session.get("_back_url")
            if back:
                del session["_back_url"]

            del session["temp_user_id"]
            _after_login(user)
            return redirect(back or url_for("root.index"))

        flash(gettext("Invalid TOTP answer"))

    return render_template("login.totp.html")


@BP.route("/logout")
def logout() -> ty.Any:
    session.clear()
    session.modified = True
    return redirect(url_for("root.index"))


def _after_login(user: model.User) -> None:
    session["user"] = user.id
    session["user_admin"] = bool(user.admin)

    db = c.get_db()
    user_id: int = session["user"]
    if user_tz := database.settings.get_value(db, "timezone", user_id):
        session["_user_tz"] = user_tz
    else:
        user_tz = session["_user_tz"]
        database.settings.set_value(db, user_id, "timezone", user_tz)
        db.commit()

    session.permanent = True
    session.modified = True
