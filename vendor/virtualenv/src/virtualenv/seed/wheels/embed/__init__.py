from __future__ import annotations

from pathlib import Path

from virtualenv import __path_assets__
from virtualenv.seed.wheels.util import Wheel

if __path_assets__:
    BUNDLE_FOLDER = __path_assets__ / "seed" / "wheels"
else:
    BUNDLE_FOLDER = Path(__file__).absolute().parent

BUNDLE_SUPPORT = {
    "3.7": {
        "pip": "pip-23.1.2-py3-none-any.whl",
        "setuptools": "setuptools-67.7.2-py3-none-any.whl",
        "wheel": "wheel-0.40.0-py3-none-any.whl",
    },
    "3.8": {
        "pip": "pip-23.1.2-py3-none-any.whl",
        "setuptools": "setuptools-67.7.2-py3-none-any.whl",
        "wheel": "wheel-0.40.0-py3-none-any.whl",
    },
    "3.9": {
        "pip": "pip-23.1.2-py3-none-any.whl",
        "setuptools": "setuptools-67.7.2-py3-none-any.whl",
        "wheel": "wheel-0.40.0-py3-none-any.whl",
    },
    "3.10": {
        "pip": "pip-23.1.2-py3-none-any.whl",
        "setuptools": "setuptools-67.7.2-py3-none-any.whl",
        "wheel": "wheel-0.40.0-py3-none-any.whl",
    },
    "3.11": {
        "pip": "pip-23.1.2-py3-none-any.whl",
        "setuptools": "setuptools-67.7.2-py3-none-any.whl",
        "wheel": "wheel-0.40.0-py3-none-any.whl",
    },
    "3.12": {
        "pip": "pip-23.1.2-py3-none-any.whl",
        "setuptools": "setuptools-67.7.2-py3-none-any.whl",
        "wheel": "wheel-0.40.0-py3-none-any.whl",
    },
}
MAX = "3.7"


def get_embed_wheel(distribution, for_py_version):
    path = BUNDLE_FOLDER / (BUNDLE_SUPPORT.get(for_py_version, {}) or BUNDLE_SUPPORT[MAX]).get(distribution)
    return Wheel.from_path(path)


__all__ = [
    "get_embed_wheel",
    "BUNDLE_SUPPORT",
    "MAX",
    "BUNDLE_FOLDER",
]
