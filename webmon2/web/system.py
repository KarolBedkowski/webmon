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
import datetime
from io import BytesIO

import pyqrcode
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
    make_response,
    abort,
)

from webmon2.web import get_db, forms
from webmon2 import model, common, security
from webmon2 import database, imp_exp, opml


_LOG = logging.getLogger(__name__)
BP = Blueprint("system", __name__, url_prefix="/system")


@BP.route("/settings/", methods=["POST", "GET"])
def sett_index():
    return redirect(url_for("system.sett_user"))


@BP.route("/settings/globals", methods=["POST", "GET"])
def sett_globals():
    db = get_db()
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
    db = get_db()
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

    totp_enabled = bool(user.totp)
    return render_template("system/user.html", totp_enabled=totp_enabled)


@BP.route("/settings/user/totp/remove", methods=["GET", "POST"])
def sett_user_totp_del():
    db = get_db()
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
    db = get_db()
    user = database.users.get(db, id_=session["user"])
    if user.totp:
        return abort(400)

    totp = session.get("temp_totp")
    if not totp:
        totp = security.generate_totp()
        session["temp_totp"] = totp
        session.modified = True

    otp_url = security.generate_totp_url(totp, user.login)

    return render_template("system/user.totp.html", totp=totp, otp_url=otp_url)


@BP.route("/settings/user/totp", methods=["POST"])
def sett_user_totp_post():
    secret = session["temp_totp"]
    if not secret:
        return abort(400)

    db = get_db()
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
    db = get_db()
    user_id = session["user"]
    content = imp_exp.dump_export(db, user_id)
    headers = {"Content-Disposition": "attachment; filename=dump.json"}
    return make_response((content, headers))


@BP.route("/settings/data/export/opml")
def sett_data_export_opml():
    db = get_db()
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

    db = get_db()
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

    db = get_db()
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
    db = get_db()
    updated = database.entries.mark_all_read(db, user_id)
    db.commit()
    flash(f"{updated} entries mark read")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/manipulation/mark_all_read_y")
def sett_data_mark_all_read_yesterday():
    user_id = session["user"]
    db = get_db()
    max_date = datetime.date.today() - datetime.timedelta(days=1)
    updated = database.entries.mark_all_read(db, user_id, max_date)
    db.commit()
    flash(f"{updated} entries mark read")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/scoring", methods=["GET", "POST"])
def sett_scoring():
    user_id = session["user"]
    db = get_db()
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


@BP.route("/qrcode")
def sys_qrcode():
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
