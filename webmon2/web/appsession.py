#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2022 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Database-based server-side session storage.

Based on flask-session.

"""
import pickle
from datetime import datetime, timezone
from uuid import uuid4

from flask.sessions import SessionInterface as FlaskSessionInterface
from flask.sessions import SessionMixin
from itsdangerous import BadSignature, Signer, want_bytes
from werkzeug.datastructures import CallbackDict

from webmon2 import database, model


class DBSession(CallbackDict, SessionMixin):
    """Server-side sessions."""

    def __init__(self, initial=None, sid=None, permanent=None):
        def on_update(self):
            self.modified = True

        self.sid = sid
        self.modified = False
        if permanent:
            self.permanent = permanent

        CallbackDict.__init__(self, initial, on_update)


class DBSessionInterface(FlaskSessionInterface):
    """Uses database as a session backend.

    :param use_signer: Whether to sign the session id cookie or not.
    :param permanent: Whether to use permanent session or not.
    """

    def __init__(self, use_signer=False, permanent=True):
        self.use_signer = use_signer
        self.permanent = permanent
        self.has_same_site_capability = hasattr(self, "get_cookie_samesite")

    def open_session(self, app, request):
        sid = request.cookies.get(app.session_cookie_name)
        if not sid:
            return DBSession(sid=_generate_sid(), permanent=self.permanent)

        if self.use_signer:
            signer = _get_signer(app)
            if signer is None:
                return None

            try:
                sid_as_bytes = signer.unsign(sid)
                sid = sid_as_bytes.decode()
            except BadSignature:
                return DBSession(sid=_generate_sid(), permanent=self.permanent)

        with database.DB.get() as db:
            saved_session = database.system.get_session(db, sid)
            if saved_session and saved_session.expiry <= datetime.now(
                timezone.utc
            ):
                # Delete expired session
                database.system.delete_session(db, sid)
                db.commit()
                saved_session = None

        if not saved_session:
            return DBSession(sid=sid, permanent=self.permanent)

        try:
            data = pickle.loads(want_bytes(saved_session.data))
            return DBSession(data, sid=sid)
        except pickle.UnpicklingError:
            return DBSession(sid=sid, permanent=self.permanent)

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        with database.DB.get() as db:

            if not session:
                if session.modified:
                    database.system.delete_session(db, session.sid)
                    db.commit()
                    response.delete_cookie(
                        app.session_cookie_name, domain=domain, path=path
                    )
                return

            saved_session = database.system.get_session(db, session.sid)
            expires = self.get_expiration_time(app, session)
            val = pickle.dumps(dict(session))
            if saved_session:
                saved_session.data = val
                saved_session.expiry = expires
            elif not session.modified:
                db.commit()
                return
            else:
                saved_session = model.Session(session.sid, expires, val)

            database.system.save_session(db, saved_session)
            db.commit()

        if self.use_signer:
            session_id = _get_signer(app).sign(want_bytes(session.sid))
        else:
            session_id = session.sid

        conditional_cookie_kwargs = {}
        if self.has_same_site_capability:
            conditional_cookie_kwargs["samesite"] = self.get_cookie_samesite(
                app
            )

        response.set_cookie(
            app.session_cookie_name,
            session_id,
            expires=expires,
            httponly=self.get_cookie_httponly(app),
            domain=domain,
            path=path,
            secure=self.get_cookie_secure(app),
            **conditional_cookie_kwargs
        )


def _generate_sid():
    return str(uuid4())


def _get_signer(app):
    if not app.secret_key:
        return None

    return Signer(
        app.secret_key, salt=app.config["SECRET_KEY"], key_derivation="hmac"
    )
