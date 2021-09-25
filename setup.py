#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os

from setuptools import find_packages, setup

from webmon2 import main

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "License :: OSI Approved :: GNU General Public License v2 or later "
    "(GPLv2+)",
    "Programming Language :: Python :: 3 :: Only",
    "Environment :: Web Environment",
    "Framework :: Flask",
    "Topic :: Internet :: WWW/HTTP",
    "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
]

REQUIRES = [
    "setuptools",
    "requests",
    "markdown2",
    "lxml",
    "PyYAML",
    "html2text",
    "feedparser",
    "github3.py",
    "flask",
    "cssselect",
    "prometheus_client",
    "Werkzeug",
    "gevent",
    "readability-lxml",
    "psycopg2",
    "python-dateutil",
    "python-gitlab",
    "pyotp",
    "pyqrcode",
    "defusedxml",
]


def get_data_files():
    tmpl_dir = "./webmon2/web/templates/"
    yield tmpl_dir, [
        os.path.join(tmpl_dir, fname)
        for fname in os.listdir(tmpl_dir)
        if fname.endswith(".html")
    ]
    schema_dir = "./webmon2/schema/"
    yield schema_dir, [
        os.path.join(schema_dir, fname)
        for fname in os.listdir(schema_dir)
        if fname.endswith(".sql")
    ]


setup(
    name=main.APP_NAME,
    version=main.VERSION,
    description="webmon2 - monitor web page changes.",
    long_description=open("README.rst").read(),
    classifiers=CLASSIFIERS,
    author="Karol Będkowski",
    author_email="karol.bedkowski at gmail.com",
    url="",
    download_url="",
    license="GPL v2+",
    py_modules=["webmon2"],
    packages=find_packages("."),
    package_dir={"": "."},
    include_package_data=True,
    install_requires=REQUIRES,
    entry_points="""
       [console_scripts]
       webmon2 = webmon2.main:main
    """,
    package_data={
        "webmon2": [
            "web/templates/*.html",
            "web/templates/**/*.html",
            "schema/*.sql",
            "web/static/*",
        ]
    },
    zip_safe=False,
)
