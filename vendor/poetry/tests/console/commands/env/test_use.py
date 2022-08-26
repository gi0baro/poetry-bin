from __future__ import annotations

import os

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import tomlkit

from poetry.core.semver.version import Version
from poetry.core.toml.file import TOMLFile

from poetry.utils.env import MockEnv
from tests.console.commands.env.helpers import build_venv
from tests.console.commands.env.helpers import check_output_wrapper


if TYPE_CHECKING:
    from cleo.testers.command_tester import CommandTester
    from pytest_mock import MockerFixture

    from tests.types import CommandTesterFactory


@pytest.fixture(autouse=True)
def setup(mocker: MockerFixture) -> None:
    mocker.stopall()
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]


@pytest.fixture(autouse=True)
def mock_subprocess_calls(
    setup: None, current_python: tuple[int, int, int], mocker: MockerFixture
) -> None:
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.from_parts(*current_python)),
    )
    mocker.patch(
        "subprocess.Popen.communicate",
        side_effect=[("/prefix", None), ("/prefix", None), ("/prefix", None)],
    )


@pytest.fixture
def tester(command_tester_factory: CommandTesterFactory) -> CommandTester:
    return command_tester_factory("env use")


def test_activate_activates_non_existing_virtualenv_no_envs_file(
    mocker: MockerFixture,
    tester: CommandTester,
    venv_cache: Path,
    venv_name: str,
    venvs_in_cache_config: None,
):
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )

    mock_build_env = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=build_venv
    )

    tester.execute("3.7")

    venv_py37 = venv_cache / f"{venv_name}-py3.7"
    mock_build_env.assert_called_with(
        venv_py37,
        executable="/usr/bin/python3.7",
        flags={
            "always-copy": False,
            "system-site-packages": False,
            "no-pip": False,
            "no-setuptools": False,
        },
        prompt="simple-project-py3.7",
    )

    envs_file = TOMLFile(venv_cache / "envs.toml")
    assert envs_file.exists()
    envs = envs_file.read()
    assert envs[venv_name]["minor"] == "3.7"
    assert envs[venv_name]["patch"] == "3.7.1"

    expected = f"""\
Creating virtualenv {venv_py37.name} in {venv_py37.parent}
Using virtualenv: {venv_py37}
"""

    assert tester.io.fetch_output() == expected


def test_get_prefers_explicitly_activated_virtualenvs_over_env_var(
    tester: CommandTester,
    current_python: tuple[int, int, int],
    venv_cache: Path,
    venv_name: str,
    venvs_in_cache_config: None,
):
    os.environ["VIRTUAL_ENV"] = "/environment/prefix"

    python_minor = ".".join(str(v) for v in current_python[:2])
    python_patch = ".".join(str(v) for v in current_python[:3])
    venv_dir = venv_cache / f"{venv_name}-py{python_minor}"
    venv_dir.mkdir(parents=True, exist_ok=True)

    envs_file = TOMLFile(venv_cache / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": python_minor, "patch": python_patch}
    envs_file.write(doc)

    tester.execute(python_minor)

    expected = f"""\
Using virtualenv: {venv_dir}
"""

    assert tester.io.fetch_output() == expected


def test_get_prefers_explicitly_activated_non_existing_virtualenvs_over_env_var(
    mocker: MockerFixture,
    tester: CommandTester,
    current_python: tuple[int, int, int],
    venv_cache: Path,
    venv_name: str,
    venvs_in_cache_config: None,
):
    os.environ["VIRTUAL_ENV"] = "/environment/prefix"

    python_minor = ".".join(str(v) for v in current_python[:2])
    venv_dir = venv_cache / f"{venv_name}-py{python_minor}"

    mocker.patch(
        "poetry.utils.env.EnvManager._env",
        new_callable=mocker.PropertyMock,
        return_value=MockEnv(
            path=Path("/environment/prefix"),
            base=Path("/base/prefix"),
            version_info=current_python,
            is_venv=True,
        ),
    )
    mocker.patch("poetry.utils.env.EnvManager.build_venv", side_effect=build_venv)

    tester.execute(python_minor)

    expected = f"""\
Creating virtualenv {venv_dir.name} in {venv_dir.parent}
Using virtualenv: {venv_dir}
"""

    assert tester.io.fetch_output() == expected
