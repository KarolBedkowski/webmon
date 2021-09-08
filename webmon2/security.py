#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2021 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Security related functions.
"""

import os
import hashlib
import socket

try:
    import pyotp
except ImportError:
    pyotp = None
    print("pyotp module not found - TOTP unavailable!")


class NotAvaliable(RuntimeError):
    pass


def hash_password(password):
    salt = os.urandom(16)
    phash = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=16, r=16, p=2
    )
    return salt.hex() + phash.hex()


def verify_password(hashed, password):
    salt = bytes.fromhex(hashed[:32])
    passw = bytes.fromhex(hashed[32:])
    phash = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=16, r=16, p=2
    )
    return passw == phash


def otp_available():
    return pyotp is not None


def generate_totp():
    if pyotp is None:
        raise NotAvaliable()

    return pyotp.random_base32()


def generate_totp_url(secret, name):
    if pyotp is None:
        raise NotAvaliable()

    my_name = "webmon2." + socket.gethostname()
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=name + "@" + my_name, issuer_name=my_name
    )


def verify_totp(secret, totp):
    if pyotp is None:
        raise NotAvaliable()

    if not secret:
        return True

    if not totp:
        return False

    try:
        totp = int(totp)
    except ValueError:
        return False

    return pyotp.TOTP(secret).verify(totp, valid_window=1)
