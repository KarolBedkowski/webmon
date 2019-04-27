#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages

from webmon import main

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    'License :: OSI Approved :: GNU General Public License (GPL)'
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
]

REQUIRES = [
    'setuptools',
    'requests',
    'markdown2',
    'lxml',
    'PyYAML',
    'html2text',
    'feedparser',
    'github3.py',
    'flask'
]


def get_data_files():
    tmpl_dir = './webmon/web/templates/'
    yield tmpl_dir, \
        [os.path.join(tmpl_dir, fname)
         for fname in os.listdir(tmpl_dir) if fname.endswith('.html')]
    schema_dir = './webmon/schema/'
    yield schema_dir, \
        [os.path.join(schema_dir, fname)
         for fname in os.listdir(schema_dir) if fname.endswith('.sql')]


setup(
    name=main.APP_NAME,
    version=main.VERSION,
    description='webmon - monitor web page changes.',
    long_description=open("README.rst").read(),
    classifiers=CLASSIFIERS,
    author='Karol Będkowski',
    author_email='karol.bedkowski at gmail.com',
    url='',
    download_url='',
    license='GPL v2+',
    py_modules=['webmon'],
    packages=find_packages('.'),
    package_dir={'': '.'},
    include_package_data=True,
    install_requires=REQUIRES,
    entry_points="""
       [console_scripts]
       webmon2 = webmon.main:main
    """,
#    data_files=list(get_data_files()),
    zip_safe=True,
)
