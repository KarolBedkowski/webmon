# Copyright © 2021 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Security related functions.
"""

import hashlib
import os
import socket

try:
    import pyotp

    _HAS_PYOTP = True
except ImportError:
    _HAS_PYOTP = False
    print("pyotp module not found - TOTP unavailable!")


class NotAvaliable(RuntimeError):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    phash = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=16, r=16, p=2
    )
    return salt.hex() + phash.hex()


def verify_password(hashed: str, password: str) -> bool:
    salt = bytes.fromhex(hashed[:32])
    passw = bytes.fromhex(hashed[32:])
    phash = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=16, r=16, p=2
    )
    return passw == phash


def otp_available() -> bool:
    return _HAS_PYOTP


def generate_totp() -> str:
    if not _HAS_PYOTP:
        raise NotAvaliable()

    return str(pyotp.random_base32())


def generate_totp_url(secret: str, name: str) -> str:
    if not _HAS_PYOTP:
        raise NotAvaliable()

    issuer = "webmon2." + socket.gethostname()
    return str(
        pyotp.totp.TOTP(secret).provisioning_uri(
            name=name + "@" + issuer, issuer_name=issuer
        )
    )


def verify_totp(secret: str, totp: str) -> bool:
    if not _HAS_PYOTP:
        raise NotAvaliable()

    if not secret:
        return True

    if not totp:
        return False

    return bool(pyotp.TOTP(secret).verify(totp, valid_window=1))
