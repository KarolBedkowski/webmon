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
import typing as ty
from io import BytesIO

try:
    import pyqrcode

    _HAS_PYQRCODE = True
except ImportError:
    print("pyqrcode not available")
    _HAS_PYQRCODE = False

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import gettext, ngettext

from webmon2 import VERSION, common, database, imp_exp, model, opml, security

from . import _commons as c
from . import forms

_LOG = logging.getLogger(__name__)
BP = Blueprint("system", __name__, url_prefix="/system")


@BP.route("/settings/", methods=["POST", "GET"])
def sett_index() -> ty.Any:
    return redirect(url_for("system.sett_user"))


@BP.route("/settings/globals", methods=["POST", "GET"])
def sett_globals() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    settings = database.settings.get_all(db, user_id)
    settings = list(_translate_sett_descr(settings))
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
        flash(gettext("There are errors in form"), "error")

    return render_template("system/globals.html", form=form)


@BP.route("/settings/user", methods=["POST", "GET"])
def sett_user() -> ty.Any:
    """
    Edit current user profile.
    """
    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    entity_hash = str(hash(user))

    if request.method == "POST":
        if entity_hash != request.form["_entity_hash"]:
            flash(gettext("User changed somewhere else; reloading..."))
        elif request.form["new_password1"] != request.form["new_password2"]:
            flash(gettext("New passwords not match"), "error")
        elif not request.form["new_password1"]:
            flash(gettext("Missing new password"), "error")
        elif not request.form["curr_password"]:
            flash(gettext("Missing current password"), "error")
        else:
            assert user.password is not None
            if security.verify_password(
                user.password, request.form["curr_password"]
            ):
                user.password = security.hash_password(
                    request.form["new_password1"]
                )
                database.users.save(db, user)
                db.commit()
                flash(gettext("Password changed"))
            else:
                flash(gettext("Wrong current password"), "error")

    otp_available = security.otp_available()
    totp_enabled = bool(user.totp)
    return render_template(
        "system/user.html",
        totp_enabled=totp_enabled,
        otp_available=otp_available,
        entity_hash=entity_hash,
    )


@BP.route("/settings/user/totp/remove", methods=["GET", "POST"])
def sett_user_totp_del() -> ty.Any:
    if not security.otp_available():
        return abort(404)

    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    user.totp = None
    database.users.save(db, user)
    db.commit()
    flash("TOTP removed")
    return redirect(url_for("system.sett_user"))


@BP.route("/settings/user/totp", methods=["GET"])
def sett_user_totp_get() -> ty.Any:
    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    totp = session.get("temp_totp")
    if not totp:
        totp = security.generate_totp()
        session["temp_totp"] = totp
        session.modified = True

    assert user.login is not None
    otp_url = security.generate_totp_url(totp, user.login)
    return render_template(
        "system/user.totp.html",
        totp=totp,
        otp_url=otp_url,
        qrcode_available=_HAS_PYQRCODE,
    )


@BP.route("/settings/user/totp", methods=["POST"])
def sett_user_totp_post() -> ty.Any:
    if not security.otp_available():
        return abort(404)

    secret = session["temp_totp"]
    if not secret:
        return abort(400)

    db = c.get_db()
    user = database.users.get(db, id_=session["user"])
    totp = request.form["totp"]
    if security.verify_totp(secret, totp):
        user.totp = secret
        database.users.save(db, user)
        db.commit()
        flash(gettext("TOTP saved"))

        del session["temp_totp"]
        session.modified = True

        return redirect(url_for("system.sett_user"))

    flash(gettext("Wrong TOTP response"))
    return redirect(url_for("system.sett_user_totp_get"))


@BP.route("/settings/data")
def sett_data() -> ty.Any:
    return render_template("system/data.html")


@BP.route("/settings/data/export")
def sett_data_export() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    content = imp_exp.dump_export(db, user_id)
    headers = {"Content-Disposition": "attachment; filename=dump.json"}
    return make_response((content, headers))


@BP.route("/settings/data/export/opml")
def sett_data_export_opml() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    content = opml.dump_data(db, user_id)
    headers = {"Content-Disposition": "attachment; filename=dump.opml"}
    return make_response((content, headers))


@BP.route("/settings/data/import", methods=["POST"])
def sett_data_import() -> ty.Any:
    if "file" not in request.files:
        flash("No file to import")
        return redirect(url_for("system.sett_data"))

    file = request.files["file"]
    data = file.read()
    if not data:
        flash(gettext("No file to import"), "error")
        return redirect(url_for("system.sett_data"))

    db = c.get_db()
    user_id = session["user"]
    try:
        imp_exp.dump_import(db, user_id, data)
        db.commit()
        flash(gettext("Import completed"))
    except Exception as err:  # pylint: disable=broad-except
        flash("Error importing file: " + str(err), "error")
        _LOG.exception("import file error")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/import/opml", methods=["POST"])
def sett_data_import_opml() -> ty.Any:
    if "file" not in request.files:
        flash(gettext("No file to import"))
        return redirect(url_for("system.sett_data"))

    file = request.files["file"]
    data = file.read()
    if not data:
        flash(gettext("No file to import"), "error")
        return redirect(url_for("system.sett_data"))

    db = c.get_db()
    user_id = session["user"]
    try:
        opml.load_data(db, data, user_id)
        db.commit()
        flash(gettext("Import completed"))
    except Exception as err:  # pylint: disable=broad-except
        flash("Error importing file: " + str(err), "error")
        _LOG.exception("import file error")
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/manipulation/mark_all_read")
def sett_data_mark_all_read() -> ty.Any:
    user_id = session["user"]
    db = c.get_db()
    updated = database.entries.mark_all_read(db, user_id)
    db.commit()
    flash(
        ngettext(
            "One entry mark read",
            "%(updated)s entries mark read",
            updated,
            updated=updated,
        )
    )
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/manipulation/mark_all_read_y")
def sett_data_mark_all_old_read() -> ty.Any:
    user_id = session["user"]
    db = c.get_db()
    max_date = datetime.date.today() - datetime.timedelta(days=1)
    updated = database.entries.mark_all_read(db, user_id, max_date)
    db.commit()
    flash(
        ngettext(
            "One entry mark read",
            "%(updated)s entries mark read",
            updated,
            updated=updated,
        )
    )
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/data/manipulation/randomize_next_check")
def sett_data_randomize_next_check() -> ty.Any:
    user_id = session["user"]
    db = c.get_db()
    updated = database.sources.randomize_next_check(db, user_id)
    db.commit()
    flash(
        ngettext(
            "One source updated",
            "%(updated)s sources updated",
            updated,
            updated=updated,
        )
    )
    return redirect(url_for("system.sett_data"))


@BP.route("/settings/scoring", methods=["GET", "POST"])
def sett_scoring() -> ty.Any:
    user_id = session["user"]
    db = c.get_db()
    if request.method == "POST":
        scs = (
            item
            for item in (
                model.ScoringSett(
                    user_id=user_id,
                    pattern=sett.get("pattern"),  # type: ignore
                    active=sett.get("active"),  # type: ignore
                    score_change=sett.get("score"),  # type: ignore
                )
                for sett in common.parse_form_list_data(request.form, "r")
            )
            if item.valid()
        )
        database.scoring.save(db, user_id, scs)
        db.commit()
        flash(gettext("Saved"))
        return redirect(url_for("system.sett_scoring"))

    rules = database.scoring.get(db, user_id)
    return render_template("system/scoring.html", rules=rules)


@BP.route("/settings/system/users", methods=["GET"])
def sett_sys_users() -> ty.Any:
    if not session["user_admin"]:
        abort(403)

    db = c.get_db()
    users = database.users.get_all(db)
    return render_template("system/sys_users.html", users=users)


@BP.route("/settings/system/users/new", methods=["GET", "POST"])
@BP.route("/settings/system/users/<int:user_id>", methods=["GET", "POST"])
def sett_sys_user(user_id: ty.Optional[int] = None) -> ty.Any:
    if not session["user_admin"]:
        abort(403)

    db = c.get_db()
    if user_id:
        try:
            user = database.users.get(db, user_id)
        except database.NotFound:
            flash(gettext("User not found"))
            return redirect(url_for("system.sett_sys_users"))
    else:
        user = model.User(active=True)

    errors = {}
    form = forms.UserForm.from_model(user)
    entity_hash = str(hash(user))

    if request.method == "POST":
        if entity_hash == request.form["_entity_hash"]:
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

            flash(gettext("There are errors in form"), "error")
        else:
            flash(gettext("User changed somewhere else; reloading..."))

    return render_template(
        "system/sys_user.html",
        form=form,
        errors=errors,
        entity_hash=entity_hash,
    )


@BP.route(
    "/settings/system/users/<int:user_id>/delete", methods=["GET", "POST"]
)
def sett_sys_user_delete(user_id: int) -> ty.Any:
    if not session["user_admin"]:
        abort(403)

    if user_id == session["user"] or not user_id:
        # can't delete myself
        abort(401)

    db = c.get_db()
    try:
        user = database.users.get(db, user_id)
    except database.NotFound:
        flash(gettext("User not found"))
        return redirect(url_for("system.sett_sys_users"))

    _LOG.info("delete user: %r", user)
    database.users.delete(db, user_id)
    db.commit()
    flash(gettext("User deleted"))
    return redirect(url_for("system.sett_sys_users"))


@BP.route("/qrcode")
def sys_qrcode() -> ty.Any:
    if not _HAS_PYQRCODE:
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


@BP.route("/settings/system/info")
def sys_info() -> ty.Any:
    if not session["user_admin"]:
        abort(403)

    info = [
        ("Version", VERSION),
    ]

    db = c.get_db()
    info.extend(database.system.get_sysinfo(db))
    settings = database.settings.get_global(db)
    db_tab_sizes = database.system.get_table_sizes(db)

    return render_template(
        "system/sys_info.html",
        info=info,
        settings=settings,
        app_conf=current_app.config["app_conf"],
        db_tab_sizes=db_tab_sizes,
    )


def _translate_sett_descr(
    settings: ty.Iterable[model.Setting],
) -> ty.Iterable[model.Setting]:
    """Get translated descriptions"""

    translations = {
        "github_user": gettext("GitHub: user name"),
        "github_token": gettext("GitHub: access token"),
        "interval": gettext("Default refresh interval"),
        "jamendo_client_id": gettext("Jamendo: client ID"),
        "keep_entries_days": gettext("Keep read entries by given days"),
        "mail_enabled": gettext("Email: enable email reports"),
        "mail_interval": gettext("Email: send email interval"),
        "mail_to": gettext("Email: recipient"),
        "mail_subject": gettext("Email: subject"),
        "mail_encrypt": gettext("Email: enable encryption"),
        "mail_html": gettext("Email: send miltipart email with html content"),
        "mail_mark_read": gettext("Email: mark reported entries read"),
        "start_at_unread_group": gettext("Start at first unread group"),
        "gitlab_token": gettext("GitLab: personal token"),
        "silent_hours_from": gettext("Silent hours: begin"),
        "silent_hours_to": gettext("Silent hours: end"),
        "minimal_score": gettext("Minimal score of entries to show"),
        "timezone": gettext("User: default timezone"),
        "locale": gettext("User: language"),
    }
    for sett in settings:
        sett.description = translations.get(sett.key, sett.key)
        yield sett
