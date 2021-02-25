# -*- coding: utf-8 -*-

"""
certifi.py
~~~~~~~~~~

This module returns the installation location of cacert.pem or its contents.
"""
import os

from pathlib import Path

from . import __path__


def read_text(_module, _path, encoding="ascii"):
    with where().open("r", encoding=encoding) as data:
        return data.read()


def where():
    return Path(__path__[0]).parents[2] / "assets" / "cacert.pem"


def contents():
    return read_text("certifi", "cacert.pem", encoding="ascii")
