#!/usr/bin/python3
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

from webmon import main

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    'License :: OSI Approved :: GNU General Public License (GPL)'
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Environment :: Win32 (MS Windows)",
    "Environment :: X11 Applications",
]

REQUIRES = [
    'setuptools',
    'requests',
]


setup(
    name='webmon',
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
       webmon = webmon.main:main
    """,
    zip_safe=True,
)
