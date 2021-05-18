# -*- coding: utf-8 -*-

"""
certifi.py
~~~~~~~~~~

This module returns the installation location of cacert.pem or its contents.
"""
import sys

from pathlib import Path

from . import __path__


def read_text(_module, _path, encoding="ascii"):
    with where().open("r", encoding=encoding) as data:
        return data.read()


def where():
    if getattr(sys, "oxidized", False):
        parents = 1 if sys.platform.startswith("win") else 2
        path = Path(__path__[0]).parents[parents] / "assets" / "certifi"
    else:
        path = Path(__path__[0])
    return path / "cacert.pem"


def contents():
    return read_text("certifi", "cacert.pem", encoding="ascii")
