#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""

"""

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for,
    current_app as app
)

from werkzeug.security import check_password_hash, generate_password_hash

from webmon.web import get_db


bp = Blueprint('browser', __name__, url_prefix='/')


@bp.route('/index')
def index():
    db = get_db()
    return render_template(
        "index.html",
        entries=db.get_unread_entries()
    )
