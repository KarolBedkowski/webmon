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

import datetime
import logging
from io import BytesIO

try:
    import pyqrcode
except ImportError:
    print("pyqrcode not available")
    pyqrcode = None

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from webmon2 import common, database, imp_exp, model, opml, security

from . import _commons as c
from . import forms

_LOG = logging.getLogger(__name__)
BP = Blueprint("system", __name__, url_prefix="/system")


@BP.route("/settings/", methods=["POST", "GET"])
def sett_index():
    return redirect(url_for("system.sett_user"))


@BP.route("/settings/globals", methods=["POST", "GET"])
def sett_globals():
    db = c.get_db()
    user_id = session["user"]
    settings = list(database.settings.get_all(db, user_id))
    form = forms.FieldsForm(
        [forms.Field.from_setting(sett, "sett-") for sett in settings]
    )
    if request.method == "POST":
        if form.update_from_request(request.form):
            values = form.values_map()
            for sett in settings:
                sett.value = values[sett.key]
                sett.user_id = user_id
            database.settings.save_all(db, settings)
            db.commit()
            flash("Settings saved")
            return redirect(url_for("system.sett_globals"))
        flash("There are errors in form", "error")

    return render_template("system/globals.html", form=form)


@BP.route("/settings/user", methods=["POST", "GET"])
def sett_user():
    db = c.get_db()
    user = database.users.get(db, id_=session["user"])

    if request.method == "POST":
        if request.form["new_password1"] != request.form["new_password2"]:
            flash("New passwords not match", "error")
        elif not request.form["new_password1"]:
            flash("Missing new password", "error")
        elif not request.form["curr_password"]:
            flash("Missing curr_password password", "error")
        else:
            if security.verify_password(
                user.password, request.form["curr_password"]
            ):
                user.password = security.hash_password(
                    request.form["new_password1"]
                )
                database.users.save(db, user)
                db.commit()
                flash("Password changed")
            else:
                flash("Wrong current password", "error")

    otp_available = security.otp_available()
    totp_enabled = bool(user.totp)
    return render_template(
        "system/user.html",
        totp_enabled=totp_enabled,
        otp_available=otp_available,
    )


@BP.route("/settings/user/totp/remove", methods=["GET", "POST"])
def sett_user_totp_del():
    if not security.otp_available():
        return abort(404)

    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    if not user.totp:
        return abort(400)

    user.totp = None
    database.users.save(db, user)
    db.commit()
    flash("TOTP removed")
    return redirect(url_for("system.sett_user"))


@BP.route("/settings/user/totp", methods=["GET"])
def sett_user_totp_get():
    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    if user.totp:
        return abort(400)

    totp = session.get("temp_totp")
    if not totp:
        totp = security.generate_totp()
        session["temp_totp"] = totp
        session.modified = True

    otp_url = security.generate_totp_url(totp, user.login)
    return render_template(
        "system/user.totp.html",
        totp=totp,
        otp_url=otp_url,
        qrcode_available=pyqrcode is not None,
    )


@BP.route("/settings/user/totp", methods=["POST"])
def sett_user_totp_post():
    if not security.otp_available():
        return abort(404)

    secret = session["temp_totp"]
    if not secret:
        return abort(400)

    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    if user.totp:
        return abort(400)

    totp = request.form["totp"]
    if security.verify_totp(secret, totp):
        user.totp = secret
        database.users.save(db, user)
        db.commit()
        flash("TOTP saved")

        del session["temp_totp"]
        session.modified = True

        return redirect(url_for("system.sett_user"))

    flash("Wrong TOTP response")
    return redirect(url_for("system.sett_user_totp_get"))


@BP.route("/settings/data")
def sett_data():
    return render_template("system/data.html")


@BP.route("/settings/data/export")
def sett_data_export():
    db = c.get_db()
    user_id = session["user"]
    content = imp_exp.dump_export(db, user_id)
    headers = {"Content-Disposition": "attachment; filename=dump.json"}
    return make_response((content, headers))


@BP.route("/settings/data/export/opml")
def sett_data_export_opml():
    db = c.get_db()
    user_id = session["user"]
    content = opml.dump_data(db, user_id)
    headers = {"Content-Disposition": "attachment; filename=dump.opml"}
    return make_response((content, headers))


@BP.route("/settings/data/import", methods=["POST"])
def sett_data_import():
    if "file" not in request.files:
        flash("No file to import")
        return redirect(url_for("system.sett_data"))

    file = request.files["file"]
    data = file.read()
    if not data:
        flash("No file to import", "error")
        return redirect(url_for("system.sett_data"))

    db = c.get_db()
    user_id = session["user"]
    try:
        imp_exp.dump_import(db, user_id, data)
        db.commit()
        flash("Import completed")
    except Exception as err:  # pylint: disable=broad-except
        flash("Error importing file: " + str(err), "error")
        _LOG.exception("import file error")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/import/opml", methods=["POST"])
def sett_data_import_opml():
    if "file" not in request.files:
        flash("No file to import")
        return redirect(url_for("system.sett_data"))

    file = request.files["file"]
    data = file.read()
    if not data:
        flash("No file to import", "error")
        return redirect(url_for("system.sett_data"))

    db = c.get_db()
    user_id = session["user"]
    try:
        opml.load_data(db, data, user_id)
        db.commit()
        flash("Import completed")
    except Exception as err:  # pylint: disable=broad-except
        flash("Error importing file: " + str(err), "error")
        _LOG.exception("import file error")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/manipulation/mark_all_read")
def sett_data_mark_all_read():
    user_id = session["user"]
    db = c.get_db()
    updated = database.entries.mark_all_read(db, user_id)
    db.commit()
    flash(f"{updated} entries mark read")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/manipulation/mark_all_read_y")
def sett_data_mark_all_old_read():
    user_id = session["user"]
    db = c.get_db()
    max_date = datetime.date.today() - datetime.timedelta(days=1)
    updated = database.entries.mark_all_read(db, user_id, max_date)
    db.commit()
    flash(f"{updated} entries mark read")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/scoring", methods=["GET", "POST"])
def sett_scoring():
    user_id = session["user"]
    db = c.get_db()
    if request.method == "POST":
        scs = [
            model.ScoringSett(
                user_id=user_id,
                pattern=sett.get("pattern"),
                active=sett.get("active"),
                score_change=sett.get("score"),
            )
            for sett in common.parse_form_list_data(request.form, "r")
        ]
        scs = filter(lambda x: x.valid(), scs)
        database.scoring.save(db, user_id, scs)
        db.commit()
        flash("Saved")
        return redirect(url_for("system.sett_scoring"))

    rules = database.scoring.get(db, user_id)
    return render_template("system/scoring.html", rules=rules)


@BP.route("/settings/system/users", methods=["GET"])
def sett_sys_users():
    if not session["user_admin"]:
        abort(403)

    db = c.get_db()
    users = database.users.get_all(db)
    return render_template("system/sys_users.html", users=users)


@BP.route("/settings/system/users/new", methods=["GET", "POST"])
@BP.route("/settings/system/users/<int:user_id>", methods=["GET", "POST"])
def sett_sys_user(user_id: int = None):
    if not session["user_admin"]:
        abort(403)

    db = c.get_db()
    if user_id:
        user = database.users.get(db, user_id)
        if not user:
            flash("User not found")
            return redirect(url_for("system.sett_sys_users"))
    else:
        user = model.User()

    errors = {}
    form = forms.UserForm.from_model(user)

    if request.method == "POST":
        form.update_from_request(request.form)
        errors = form.validate()

        if session["user"] == user_id and not form.active and user.active:
            errors["active"] = "Can't deactivate current user"

        if not errors:
            uuser = form.update_model(user)  # type: model.User
            if form.password1:
                uuser.password = security.hash_password(form.password1)

            _LOG.info("save user: %r", uuser)
            try:
                database.users.save(db, uuser)
            except database.users.LoginAlreadyExistsError:
                errors["login"] = "Login already exists"
            else:
                db.commit()
                flash("User saved")
                return redirect(url_for("system.sett_sys_users"))

        flash("There are errors in form", "error")

    return render_template("system/sys_user.html", form=form, errors=errors)


@BP.route(
    "/settings/system/users/<int:user_id>/delete", methods=["GET", "POST"]
)
def sett_sys_user_delete(user_id: int):
    if not session["user_admin"]:
        abort(403)

    if user_id == session["user"] or not user_id:
        # can't delete myself
        abort(401)

    db = c.get_db()
    user = database.users.get(db, user_id)
    if not user:
        flash("User not found")
        return redirect(url_for("system.sett_sys_users"))

    _LOG.info("delete user: %r", user)
    database.users.delete(db, user_id)
    db.commit()
    flash("User deleted")
    return redirect(url_for("system.sett_sys_users"))


@BP.route("/qrcode")
def sys_qrcode():
    if pyqrcode is None:
        return abort(404)

    url = request.args["url"]
    qrc = pyqrcode.create(url)
    stream = BytesIO()
    qrc.svg(stream, scale=5)
    return (
        stream.getvalue(),
        200,
        {
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
