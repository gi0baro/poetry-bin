from __future__ import annotations

import os

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from poetry.utils.env import EnvManager


if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.helpers import PoetryTestApplication


@pytest.fixture
def venv_name(app: PoetryTestApplication) -> str:
    return EnvManager.generate_env_name("simple-project", str(app.poetry.file.parent))


@pytest.fixture
def venv_cache(tmp_dir: str) -> Path:
    return Path(tmp_dir)


@pytest.fixture(scope="module")
def python_versions() -> list[str]:
    return ["3.6", "3.7"]


@pytest.fixture
def venvs_in_cache_config(app: PoetryTestApplication, venv_cache: Path) -> None:
    app.poetry.config.merge({"virtualenvs": {"path": str(venv_cache)}})


@pytest.fixture
def venvs_in_cache_dirs(
    app: PoetryTestApplication,
    venvs_in_cache_config: None,
    venv_name: str,
    venv_cache: Path,
    python_versions: list[str],
) -> list[str]:
    directories = []
    for version in python_versions:
        directory = venv_cache.joinpath(f"{venv_name}-py{version}")
        directory.mkdir(parents=True, exist_ok=True)
        directories.append(directory.name)
    return directories


@pytest.fixture
def venvs_in_project_dir(app: PoetryTestApplication) -> Iterator[Path]:
    os.environ.pop("VIRTUAL_ENV", None)
    venv_dir = app.poetry.file.parent.joinpath(".venv")
    venv_dir.mkdir(exist_ok=True)
    app.poetry.config.merge({"virtualenvs": {"in-project": True}})

    try:
        yield venv_dir
    finally:
        venv_dir.rmdir()
