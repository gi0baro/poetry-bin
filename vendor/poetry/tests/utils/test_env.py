from __future__ import annotations

import contextlib
import os
import site
import subprocess
import sys

from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING
from typing import Any

import pytest
import tomlkit

from poetry.core.constraints.version import Version

from poetry.factory import Factory
from poetry.repositories.installed_repository import InstalledRepository
from poetry.toml.file import TOMLFile
from poetry.utils._compat import WINDOWS
from poetry.utils._compat import metadata
from poetry.utils.env import GET_PYTHON_VERSION_ONELINER
from poetry.utils.env import EnvCommandError
from poetry.utils.env import EnvManager
from poetry.utils.env import GenericEnv
from poetry.utils.env import IncorrectEnvError
from poetry.utils.env import InvalidCurrentPythonVersionError
from poetry.utils.env import MockEnv
from poetry.utils.env import NoCompatiblePythonVersionFound
from poetry.utils.env import PythonVersionNotFound
from poetry.utils.env import SystemEnv
from poetry.utils.env import VirtualEnv
from poetry.utils.env import build_environment
from poetry.utils.helpers import remove_directory


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator

    from pytest_mock import MockerFixture

    from poetry.poetry import Poetry
    from tests.conftest import Config
    from tests.types import FixtureDirGetter
    from tests.types import ProjectFactory

MINIMAL_SCRIPT = """\

print("Minimal Output"),
"""

# Script expected to fail.
ERRORING_SCRIPT = """\
import nullpackage

print("nullpackage loaded"),
"""


class MockSubprocRun:
    def __init__(self, v):
        self.stdout = v


class MockVirtualEnv(VirtualEnv):
    def __init__(
        self,
        path: Path,
        base: Path | None = None,
        sys_path: list[str] | None = None,
    ) -> None:
        super().__init__(path, base=base)

        self._sys_path = sys_path

    @property
    def sys_path(self) -> list[str]:
        if self._sys_path is not None:
            return self._sys_path

        return super().sys_path


@pytest.fixture()
def poetry(project_factory: ProjectFactory, fixture_dir: FixtureDirGetter) -> Poetry:
    return project_factory("simple", source=fixture_dir("simple_project"))


@pytest.fixture()
def manager(poetry: Poetry) -> EnvManager:
    return EnvManager(poetry)


def test_virtualenvs_with_spaces_in_their_path_work_as_expected(
    tmp_path: Path, manager: EnvManager
) -> None:
    venv_path = tmp_path / "Virtual Env"

    manager.build_venv(venv_path)

    venv = VirtualEnv(venv_path)

    assert venv.run("python", "-V").startswith("Python")


@pytest.mark.skip("no xattr on bin")
def test_venv_backup_exclusion(tmp_path: Path, manager: EnvManager) -> None:
    import xattr

    venv_path = tmp_path / "Virtual Env"

    manager.build_venv(venv_path)

    value = (
        b"bplist00_\x10\x11com.apple.backupd"
        b"\x08\x00\x00\x00\x00\x00\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00"
        b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1c"
    )
    assert (
        xattr.getxattr(
            str(venv_path), "com.apple.metadata:com_apple_backup_excludeItem"
        )
        == value
    )


def test_env_commands_with_spaces_in_their_arg_work_as_expected(
    tmp_path: Path, manager: EnvManager
) -> None:
    venv_path = tmp_path / "Virtual Env"
    manager.build_venv(venv_path)
    venv = VirtualEnv(venv_path)
    assert venv.run("python", str(venv.pip), "--version").startswith(
        f"pip {venv.pip_version} from "
    )


def test_env_get_supported_tags_matches_inside_virtualenv(
    tmp_path: Path, manager: EnvManager
) -> None:
    venv_path = tmp_path / "Virtual Env"
    manager.build_venv(venv_path)
    venv = VirtualEnv(venv_path)

    import packaging.tags

    assert venv.get_supported_tags() == list(packaging.tags.sys_tags())


@pytest.fixture
def in_project_venv_dir(poetry: Poetry) -> Iterator[Path]:
    os.environ.pop("VIRTUAL_ENV", None)
    venv_dir = poetry.file.path.parent.joinpath(".venv")
    venv_dir.mkdir()
    try:
        yield venv_dir
    finally:
        venv_dir.rmdir()


@pytest.mark.parametrize("in_project", [True, False, None])
def test_env_get_venv_with_venv_folder_present(
    manager: EnvManager,
    poetry: Poetry,
    in_project_venv_dir: Path,
    in_project: bool | None,
) -> None:
    poetry.config.config["virtualenvs"]["in-project"] = in_project
    venv = manager.get()
    if in_project is False:
        assert venv.path != in_project_venv_dir
    else:
        assert venv.path == in_project_venv_dir


def build_venv(path: Path | str, **__: Any) -> None:
    os.mkdir(str(path))


VERSION_3_7_1 = Version.parse("3.7.1")


def check_output_wrapper(
    version: Version = VERSION_3_7_1,
) -> Callable[[list[str], Any, Any], str]:
    def check_output(cmd: list[str], *args: Any, **kwargs: Any) -> str:
        # cmd is a list, like ["python", "-c", "do stuff"]
        python_cmd = cmd[-1]
        if "print(json.dumps(env))" in python_cmd:
            return (
                f'{{"version_info": [{version.major}, {version.minor},'
                f" {version.patch}]}}"
            )

        if "sys.version_info[:3]" in python_cmd:
            return version.text

        if "sys.version_info[:2]" in python_cmd:
            return f"{version.major}.{version.minor}"

        if "import sys; print(sys.executable)" in python_cmd:
            executable = cmd[0]
            basename = os.path.basename(executable)
            return f"/usr/bin/{basename}"

        if "print(sys.base_prefix)" in python_cmd:
            return "/usr"

        assert "import sys; print(sys.prefix)" in python_cmd
        return "/prefix"

    return check_output


def test_activate_in_project_venv_no_explicit_config(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    mocker: MockerFixture,
    venv_name: str,
    in_project_venv_dir: Path,
) -> None:
    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )
    m = mocker.patch("poetry.utils.env.EnvManager.build_venv", side_effect=build_venv)

    env = manager.activate("python3.7")

    assert env.path == tmp_path / "poetry-fixture-simple" / ".venv"
    assert env.base == Path("/usr")

    m.assert_called_with(
        tmp_path / "poetry-fixture-simple" / ".venv",
        executable=Path("/usr/bin/python3.7"),
        flags={
            "always-copy": False,
            "system-site-packages": False,
            "no-pip": False,
            "no-setuptools": False,
        },
        prompt="simple-project-py3.7",
    )

    envs_file = TOMLFile(tmp_path / "envs.toml")
    assert not envs_file.exists()


@pytest.mark.skipif(sys.platform == 'darwin', reason='no hardcoded bin on macos')
def test_activate_activates_non_existing_virtualenv_no_envs_file(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )
    m = mocker.patch("poetry.utils.env.EnvManager.build_venv", side_effect=build_venv)

    env = manager.activate("python3.7")

    m.assert_called_with(
        tmp_path / f"{venv_name}-py3.7",
        executable=Path("/usr/bin/python3.7"),
        flags=venv_flags_default,
        prompt="simple-project-py3.7",
    )

    envs_file = TOMLFile(tmp_path / "envs.toml")

    assert envs_file.exists()
    envs: dict[str, Any] = envs_file.read()
    assert envs[venv_name]["minor"] == "3.7"
    assert envs[venv_name]["patch"] == "3.7.1"

    assert env.path == tmp_path / f"{venv_name}-py3.7"
    assert env.base == Path("/usr")


def test_activate_fails_when_python_cannot_be_found(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    os.mkdir(tmp_path / f"{venv_name}-py3.7")

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(PythonVersionNotFound) as e:
        manager.activate("python3.7")

    expected_message = "Could not find the python executable python3.7"
    assert str(e.value) == expected_message


def test_activate_activates_existing_virtualenv_no_envs_file(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    os.mkdir(tmp_path / f"{venv_name}-py3.7")

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )
    m = mocker.patch("poetry.utils.env.EnvManager.build_venv", side_effect=build_venv)

    env = manager.activate("python3.7")

    m.assert_not_called()

    envs_file = TOMLFile(tmp_path / "envs.toml")
    assert envs_file.exists()
    envs: dict[str, Any] = envs_file.read()
    assert envs[venv_name]["minor"] == "3.7"
    assert envs[venv_name]["patch"] == "3.7.1"

    assert env.path == tmp_path / f"{venv_name}-py3.7"
    assert env.base == Path("/usr")


def test_activate_activates_same_virtualenv_with_envs_file(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": "3.7", "patch": "3.7.1"}
    envs_file.write(doc)

    os.mkdir(tmp_path / f"{venv_name}-py3.7")

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )
    m = mocker.patch("poetry.utils.env.EnvManager.create_venv")

    env = manager.activate("python3.7")

    m.assert_not_called()

    assert envs_file.exists()
    envs: dict[str, Any] = envs_file.read()
    assert envs[venv_name]["minor"] == "3.7"
    assert envs[venv_name]["patch"] == "3.7.1"

    assert env.path == tmp_path / f"{venv_name}-py3.7"
    assert env.base == Path("/usr")


def test_activate_activates_different_virtualenv_with_envs_file(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": "3.7", "patch": "3.7.1"}
    envs_file.write(doc)

    os.mkdir(tmp_path / f"{venv_name}-py3.7")

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )
    m = mocker.patch("poetry.utils.env.EnvManager.build_venv", side_effect=build_venv)

    env = manager.activate("python3.6")

    m.assert_called_with(
        tmp_path / f"{venv_name}-py3.6",
        executable=Path("/usr/bin/python3.6"),
        flags=venv_flags_default,
        prompt="simple-project-py3.6",
    )

    assert envs_file.exists()
    envs: dict[str, Any] = envs_file.read()
    assert envs[venv_name]["minor"] == "3.6"
    assert envs[venv_name]["patch"] == "3.6.6"

    assert env.path == tmp_path / f"{venv_name}-py3.6"
    assert env.base == Path("/usr")


def test_activate_activates_recreates_for_different_patch(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": "3.7", "patch": "3.7.0"}
    envs_file.write(doc)

    os.mkdir(tmp_path / f"{venv_name}-py3.7")

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )
    build_venv_m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=build_venv
    )
    remove_venv_m = mocker.patch(
        "poetry.utils.env.EnvManager.remove_venv", side_effect=EnvManager.remove_venv
    )

    env = manager.activate("python3.7")

    build_venv_m.assert_called_with(
        tmp_path / f"{venv_name}-py3.7",
        executable=Path("/usr/bin/python3.7"),
        flags=venv_flags_default,
        prompt="simple-project-py3.7",
    )
    remove_venv_m.assert_called_with(tmp_path / f"{venv_name}-py3.7")

    assert envs_file.exists()
    envs: dict[str, Any] = envs_file.read()
    assert envs[venv_name]["minor"] == "3.7"
    assert envs[venv_name]["patch"] == "3.7.1"

    assert env.path == tmp_path / f"{venv_name}-py3.7"
    assert env.base == Path("/usr")
    assert (tmp_path / f"{venv_name}-py3.7").exists()


def test_activate_does_not_recreate_when_switching_minor(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": "3.7", "patch": "3.7.0"}
    envs_file.write(doc)

    os.mkdir(tmp_path / f"{venv_name}-py3.7")
    os.mkdir(tmp_path / f"{venv_name}-py3.6")

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )
    build_venv_m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=build_venv
    )
    remove_venv_m = mocker.patch(
        "poetry.utils.env.EnvManager.remove_venv", side_effect=EnvManager.remove_venv
    )

    env = manager.activate("python3.6")

    build_venv_m.assert_not_called()
    remove_venv_m.assert_not_called()

    assert envs_file.exists()
    envs: dict[str, Any] = envs_file.read()
    assert envs[venv_name]["minor"] == "3.6"
    assert envs[venv_name]["patch"] == "3.6.6"

    assert env.path == tmp_path / f"{venv_name}-py3.6"
    assert env.base == Path("/usr")
    assert (tmp_path / f"{venv_name}-py3.6").exists()


def test_deactivate_non_activated_but_existing(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    python = ".".join(str(c) for c in sys.version_info[:2])
    (tmp_path / f"{venv_name}-py{python}").mkdir()

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.10.5")),
    )

    manager.deactivate()
    env = manager.get()

    assert env.path == tmp_path / f"{venv_name}-py{python}"


def test_deactivate_activated(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    version = Version.from_parts(*sys.version_info[:3])
    other_version = Version.parse("3.4") if version.major == 2 else version.next_minor()
    (tmp_path / f"{venv_name}-py{version.major}.{version.minor}").mkdir()
    (tmp_path / f"{venv_name}-py{other_version.major}.{other_version.minor}").mkdir()

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {
        "minor": f"{other_version.major}.{other_version.minor}",
        "patch": other_version.text,
    }
    envs_file.write(doc)

    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.10.5")),
    )

    manager.deactivate()
    env = manager.get()

    assert env.path == tmp_path / f"{venv_name}-py{version.major}.{version.minor}"

    envs = envs_file.read()
    assert len(envs) == 0


def test_get_prefers_explicitly_activated_virtualenvs_over_env_var(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    os.environ["VIRTUAL_ENV"] = "/environment/prefix"

    config.merge({"virtualenvs": {"path": str(tmp_path)}})
    (tmp_path / f"{venv_name}-py3.7").mkdir()

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": "3.7", "patch": "3.7.0"}
    envs_file.write(doc)

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )

    env = manager.get()

    assert env.path == tmp_path / f"{venv_name}-py3.7"
    assert env.base == Path("/usr")


def test_list(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    venv_name: str,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    (tmp_path / f"{venv_name}-py3.7").mkdir()
    (tmp_path / f"{venv_name}-py3.6").mkdir()

    venvs = manager.list()

    assert len(venvs) == 2
    assert venvs[0].path == tmp_path / f"{venv_name}-py3.6"
    assert venvs[1].path == tmp_path / f"{venv_name}-py3.7"


def test_remove_by_python_version(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    (tmp_path / f"{venv_name}-py3.7").mkdir()
    (tmp_path / f"{venv_name}-py3.6").mkdir()

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )

    venv = manager.remove("3.6")

    expected_venv_path = tmp_path / f"{venv_name}-py3.6"
    assert venv.path == expected_venv_path
    assert not expected_venv_path.exists()


def test_remove_by_name(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    (tmp_path / f"{venv_name}-py3.7").mkdir()
    (tmp_path / f"{venv_name}-py3.6").mkdir()

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )

    venv = manager.remove(f"{venv_name}-py3.6")

    expected_venv_path = tmp_path / f"{venv_name}-py3.6"
    assert venv.path == expected_venv_path
    assert not expected_venv_path.exists()


def test_remove_by_string_with_python_and_version(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    (tmp_path / f"{venv_name}-py3.7").mkdir()
    (tmp_path / f"{venv_name}-py3.6").mkdir()

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )

    venv = manager.remove("python3.6")

    expected_venv_path = tmp_path / f"{venv_name}-py3.6"
    assert venv.path == expected_venv_path
    assert not expected_venv_path.exists()


def test_remove_by_full_path_to_python(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    (tmp_path / f"{venv_name}-py3.7").mkdir()
    (tmp_path / f"{venv_name}-py3.6").mkdir()

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )

    expected_venv_path = tmp_path / f"{venv_name}-py3.6"
    python_path = expected_venv_path / "bin" / "python"

    venv = manager.remove(str(python_path))

    assert venv.path == expected_venv_path
    assert not expected_venv_path.exists()


def test_raises_if_acting_on_different_project_by_full_path(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    different_venv_name = "different-project"
    different_venv_path = tmp_path / f"{different_venv_name}-py3.6"
    different_venv_bin_path = different_venv_path / "bin"
    different_venv_bin_path.mkdir(parents=True)

    python_path = different_venv_bin_path / "python"
    python_path.touch(exist_ok=True)

    # Patch initial call where python env path is extracted
    mocker.patch(
        "subprocess.check_output",
        side_effect=lambda *args, **kwargs: str(different_venv_path),
    )

    with pytest.raises(IncorrectEnvError):
        manager.remove(str(python_path))


def test_raises_if_acting_on_different_project_by_name(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    different_venv_name = (
        EnvManager.generate_env_name(
            "different-project",
            str(poetry.file.path.parent),
        )
        + "-py3.6"
    )
    different_venv_path = tmp_path / different_venv_name
    different_venv_bin_path = different_venv_path / "bin"
    different_venv_bin_path.mkdir(parents=True)

    python_path = different_venv_bin_path / "python"
    python_path.touch(exist_ok=True)

    with pytest.raises(IncorrectEnvError):
        manager.remove(different_venv_name)


def test_raises_when_passing_old_env_after_dir_rename(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    venv_name: str,
) -> None:
    # Make sure that poetry raises when trying to remove old venv after you've renamed
    # root directory of the project, which will create another venv with new name.
    # This is not ideal as you still "can't" remove it by name, but it at least doesn't
    # cause any unwanted side effects
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    previous_venv_name = EnvManager.generate_env_name(
        poetry.package.name,
        "previous_dir_name",
    )
    venv_path = tmp_path / f"{venv_name}-py3.6"
    venv_path.mkdir()

    previous_venv_name = f"{previous_venv_name}-py3.6"
    previous_venv_path = tmp_path / previous_venv_name
    previous_venv_path.mkdir()

    with pytest.raises(IncorrectEnvError):
        manager.remove(previous_venv_name)


def test_remove_also_deactivates(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    (tmp_path / f"{venv_name}-py3.7").mkdir()
    (tmp_path / f"{venv_name}-py3.6").mkdir()

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )

    envs_file = TOMLFile(tmp_path / "envs.toml")
    doc = tomlkit.document()
    doc[venv_name] = {"minor": "3.6", "patch": "3.6.6"}
    envs_file.write(doc)

    venv = manager.remove("python3.6")

    expected_venv_path = tmp_path / f"{venv_name}-py3.6"
    assert venv.path == expected_venv_path
    assert not expected_venv_path.exists()

    envs = envs_file.read()
    assert venv_name not in envs


def test_remove_keeps_dir_if_not_deleteable(
    tmp_path: Path,
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    venv_name: str,
) -> None:
    # Ensure we empty rather than delete folder if its is an active mount point.
    # See https://github.com/python-poetry/poetry/pull/2064
    config.merge({"virtualenvs": {"path": str(tmp_path)}})

    venv_path = tmp_path / f"{venv_name}-py3.6"
    venv_path.mkdir()

    folder1_path = venv_path / "folder1"
    folder1_path.mkdir()

    file1_path = folder1_path / "file1"
    file1_path.touch(exist_ok=False)

    file2_path = venv_path / "file2"
    file2_path.touch(exist_ok=False)

    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.6.6")),
    )

    def err_on_rm_venv_only(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.resolve() == venv_path.resolve():
            raise OSError(16, "Test error")  # ERRNO 16: Device or resource busy
        else:
            remove_directory(path)

    m = mocker.patch(
        "poetry.utils.env.env_manager.remove_directory", side_effect=err_on_rm_venv_only
    )

    venv = manager.remove(f"{venv_name}-py3.6")

    m.assert_any_call(venv_path)

    assert venv_path == venv.path
    assert venv_path.exists()

    assert not folder1_path.exists()
    assert not file1_path.exists()
    assert not file2_path.exists()

    m.side_effect = remove_directory  # Avoid teardown using `err_on_rm_venv_only`


@pytest.mark.skipif(os.name == "nt", reason="Symlinks are not support for Windows")
def test_env_has_symlinks_on_nix(tmp_path: Path, tmp_venv: VirtualEnv) -> None:
    assert os.path.islink(tmp_venv.python)


def test_run_with_keyboard_interrupt(
    tmp_path: Path, tmp_venv: VirtualEnv, mocker: MockerFixture
) -> None:
    mocker.patch("subprocess.check_output", side_effect=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        tmp_venv.run("python", "-c", MINIMAL_SCRIPT)
    subprocess.check_output.assert_called_once()  # type: ignore[attr-defined]


def test_call_with_keyboard_interrupt(
    tmp_path: Path, tmp_venv: VirtualEnv, mocker: MockerFixture
) -> None:
    mocker.patch("subprocess.check_call", side_effect=KeyboardInterrupt())
    kwargs = {"call": True}
    with pytest.raises(KeyboardInterrupt):
        tmp_venv.run("python", "-", **kwargs)
    subprocess.check_call.assert_called_once()  # type: ignore[attr-defined]


def test_run_with_called_process_error(
    tmp_path: Path, tmp_venv: VirtualEnv, mocker: MockerFixture
) -> None:
    mocker.patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(
            42, "some_command", "some output", "some error"
        ),
    )
    with pytest.raises(EnvCommandError) as error:
        tmp_venv.run("python", "-c", MINIMAL_SCRIPT)
    subprocess.check_output.assert_called_once()  # type: ignore[attr-defined]
    assert "some output" in str(error.value)
    assert "some error" in str(error.value)


def test_call_no_input_with_called_process_error(
    tmp_path: Path, tmp_venv: VirtualEnv, mocker: MockerFixture
) -> None:
    mocker.patch(
        "subprocess.check_call",
        side_effect=subprocess.CalledProcessError(
            42, "some_command", "some output", "some error"
        ),
    )
    kwargs = {"call": True}
    with pytest.raises(EnvCommandError) as error:
        tmp_venv.run("python", "-", **kwargs)
    subprocess.check_call.assert_called_once()  # type: ignore[attr-defined]
    assert "some output" in str(error.value)
    assert "some error" in str(error.value)


def test_check_output_with_called_process_error(
    tmp_path: Path, tmp_venv: VirtualEnv, mocker: MockerFixture
) -> None:
    mocker.patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(
            42, "some_command", "some output", "some error"
        ),
    )
    with pytest.raises(EnvCommandError) as error:
        tmp_venv.run("python", "-")
    subprocess.check_output.assert_called_once()  # type: ignore[attr-defined]
    assert "some output" in str(error.value)
    assert "some error" in str(error.value)


@pytest.mark.parametrize("out", ["sys.stdout", "sys.stderr"])
def test_call_does_not_block_on_full_pipe(
    tmp_path: Path, tmp_venv: VirtualEnv, out: str
) -> None:
    """see https://github.com/python-poetry/poetry/issues/7698"""
    script = tmp_path / "script.py"
    script.write_text(f"""\
import sys
for i in range(10000):
    print('just print a lot of text to fill the buffer', file={out})
""")

    def target(result: list[int]) -> None:
        tmp_venv.run("python", str(script), call=True)
        result.append(0)

    results: list[int] = []
    # use a separate thread, so that the test does not block in case of error
    thread = Thread(target=target, args=(results,))
    thread.start()
    thread.join(1)  # must not block
    assert results and results[0] == 0


def test_run_python_script_called_process_error(
    tmp_path: Path, tmp_venv: VirtualEnv, mocker: MockerFixture
) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            42, "some_command", "some output", "some error"
        ),
    )
    with pytest.raises(EnvCommandError) as error:
        tmp_venv.run_python_script(MINIMAL_SCRIPT)
    assert "some output" in str(error.value)
    assert "some error" in str(error.value)


def test_run_python_script_only_stdout(tmp_path: Path, tmp_venv: VirtualEnv) -> None:
    output = tmp_venv.run_python_script(
        "import sys; print('some warning', file=sys.stderr); print('some output')"
    )
    assert "some output" in output
    assert "some warning" not in output


def test_create_venv_tries_to_find_a_compatible_python_executable_using_generic_ones_first(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry.package.python_versions = "^3.6"

    mocker.patch("sys.version_info", (2, 7, 16))
    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.7.5")),
    )
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    manager.create_venv()

    m.assert_called_with(
        config_virtualenvs_path / f"{venv_name}-py3.7",
        executable=Path("/usr/bin/python"),
        flags=venv_flags_default,
        prompt="simple-project-py3.7",
    )


def test_create_venv_finds_no_python_executable(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry.package.python_versions = "^3.6"

    mocker.patch("sys.version_info", (2, 7, 16))
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(NoCompatiblePythonVersionFound) as e:
        manager.create_venv()

    expected_message = (
        "Poetry was unable to find a compatible version. "
        "If you have one, you can explicitly use it "
        'via the "env use" command.'
    )

    assert str(e.value) == expected_message


def test_create_venv_tries_to_find_a_compatible_python_executable_using_specific_ones(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry.package.python_versions = "^3.6"

    orig_run = subprocess.run
    orig_check_output = subprocess.check_output
    pyversions = ["3.5.3", "3.5.3", "3.9.0"]

    def mock_run(cmd: str, *_: Any, **__: Any) -> str:
        if "/usr/bin/python3.9" in cmd:
            return MockSubprocRun("/usr/local")
        return orig_run(cmd, *_, **__)

    def mock_check_output(cmd: str, *_: Any, **__: Any) -> str:
        if GET_PYTHON_VERSION_ONELINER in cmd:
            return pyversions.pop(0)
        if "import sys; print(sys.executable)" in cmd:
            return "/usr/bin/python3.9"
        return orig_check_output(cmd, *_, **__)

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch("subprocess.check_output", side_effect=mock_check_output)
    mocker.patch("subprocess.run", side_effect=mock_run)
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    manager.create_venv()

    m.assert_called_with(
        config_virtualenvs_path / f"{venv_name}-py3.9",
        executable=Path("/usr/bin/python3.9"),
        flags=venv_flags_default,
        prompt="simple-project-py3.9",
    )


def test_create_venv_fails_if_no_compatible_python_version_could_be_found(
    manager: EnvManager, poetry: Poetry, config: Config, mocker: MockerFixture
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry.package.python_versions = "^4.8"

    mocker.patch("subprocess.check_output", side_effect=lambda *args, **kwargs: "")
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    with pytest.raises(NoCompatiblePythonVersionFound) as e:
        manager.create_venv()

    expected_message = (
        "Poetry was unable to find a compatible version. "
        "If you have one, you can explicitly use it "
        'via the "env use" command.'
    )

    assert str(e.value) == expected_message
    assert m.call_count == 0


def test_create_venv_does_not_try_to_find_compatible_versions_with_executable(
    manager: EnvManager, poetry: Poetry, config: Config, mocker: MockerFixture
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry.package.python_versions = "^4.8"

    orig_check_output = subprocess.check_output

    def mock_check_output(cmd: str, *_: Any, **__: Any) -> str:
        if GET_PYTHON_VERSION_ONELINER in cmd:
            return "3.8.0"
        if "import sys; print(sys.executable)" in cmd:
            return "python"
        return orig_check_output(cmd, *_, **__)

    mocker.patch("subprocess.check_output", side_effect=mock_check_output)
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    with pytest.raises(NoCompatiblePythonVersionFound) as e:
        manager.create_venv(executable=Path("python3.8"))

    expected_message = (
        "The specified Python version (3.8.0) is not supported by the project (^4.8).\n"
        "Please choose a compatible version or loosen the python constraint "
        "specified in the pyproject.toml file."
    )

    assert str(e.value) == expected_message
    assert m.call_count == 0


def test_create_venv_uses_patch_version_to_detect_compatibility(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    version = Version.from_parts(*sys.version_info[:3])
    poetry.package.python_versions = "^" + ".".join(
        str(c) for c in sys.version_info[:3]
    )

    assert version.patch is not None
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse(f"{version.major}.{version.minor}.{version.patch + 1}")),
    )
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    manager.create_venv()

    m.assert_called_with(
        config_virtualenvs_path / f"{venv_name}-py{version.major}.{version.minor}",
        executable=Path('/usr/bin/python'),
        flags=venv_flags_default,
        prompt=f"simple-project-py{version.major}.{version.minor}",
    )


def test_create_venv_uses_patch_version_to_detect_compatibility_with_executable(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
    venv_name: str,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    version = Version.from_parts(*sys.version_info[:3])
    assert version.minor is not None
    poetry.package.python_versions = f"~{version.major}.{version.minor - 1}.0"
    venv_name = manager.generate_env_name(
        "simple-project", str(poetry.file.path.parent)
    )

    check_output = mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(
            Version.parse(f"{version.major}.{version.minor - 1}.0")
        ),
    )
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    manager.create_venv(executable=Path(f"python{version.major}.{version.minor - 1}"))

    assert check_output.called
    m.assert_called_with(
        config_virtualenvs_path / f"{venv_name}-py{version.major}.{version.minor - 1}",
        executable=Path(f"python{version.major}.{version.minor - 1}"),
        flags=venv_flags_default,
        prompt=f"simple-project-py{version.major}.{version.minor - 1}",
    )


def test_create_venv_fails_if_current_python_version_is_not_supported(
    manager: EnvManager, poetry: Poetry
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    manager.create_venv()

    current_version = Version.parse(".".join(str(c) for c in sys.version_info[:3]))
    assert current_version.minor is not None
    next_version = ".".join(
        str(c) for c in (current_version.major, current_version.minor + 1, 0)
    )
    package_version = "~" + next_version
    poetry.package.python_versions = package_version

    with pytest.raises(InvalidCurrentPythonVersionError) as e:
        manager.create_venv()

    expected_message = (
        f"Current Python version ({current_version}) is not allowed by the project"
        f' ({package_version}).\nPlease change python executable via the "env use"'
        " command."
    )

    assert expected_message == str(e.value)


@pytest.mark.skipif(sys.platform == 'darwin', reason='no hardcoded bin on macos')
def test_activate_with_in_project_setting_does_not_fail_if_no_venvs_dir(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    tmp_path: Path,
    mocker: MockerFixture,
    venv_flags_default: dict[str, bool],
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    config.merge(
        {
            "virtualenvs": {
                "path": str(tmp_path / "virtualenvs"),
                "in-project": True,
            }
        }
    )

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(),
    )
    m = mocker.patch("poetry.utils.env.EnvManager.build_venv")

    manager.activate("python3.7")

    m.assert_called_with(
        poetry.file.path.parent / ".venv",
        executable=Path("/usr/bin/python3.7"),
        flags=venv_flags_default,
        prompt="simple-project-py3.7",
    )

    envs_file = TOMLFile(tmp_path / "virtualenvs" / "envs.toml")
    assert not envs_file.exists()


def test_system_env_has_correct_paths() -> None:
    env = SystemEnv(Path(sys.prefix), auto_path=False)

    paths = env.paths

    assert paths.get("purelib") is not None
    assert paths.get("platlib") is not None
    assert paths.get("scripts") is not None
    assert env.site_packages.path == Path(paths["purelib"])
    assert paths["include"] is not None


@pytest.mark.skip
@pytest.mark.parametrize(
    "enabled",
    [True, False],
)
def test_system_env_usersite(mocker: MockerFixture, enabled: bool) -> None:
    mocker.patch("site.check_enableusersite", return_value=enabled)
    env = SystemEnv(Path(sys.prefix))
    assert (enabled and env.usersite is not None) or (
        not enabled and env.usersite is None
    )


def test_venv_has_correct_paths(tmp_venv: VirtualEnv) -> None:
    paths = tmp_venv.paths

    assert paths.get("purelib") is not None
    assert paths.get("platlib") is not None
    assert paths.get("scripts") is not None
    assert tmp_venv.site_packages.path == Path(paths["purelib"])
    assert paths["include"] == str(
        tmp_venv.path.joinpath(
            f"include/site/python{tmp_venv.version_info[0]}.{tmp_venv.version_info[1]}"
        )
    )


def test_env_system_packages(tmp_path: Path, poetry: Poetry) -> None:
    venv_path = tmp_path / "venv"
    pyvenv_cfg = venv_path / "pyvenv.cfg"

    EnvManager(poetry).build_venv(path=venv_path, flags={"system-site-packages": True})
    env = VirtualEnv(venv_path)

    assert "include-system-site-packages = true" in pyvenv_cfg.read_text()
    assert env.includes_system_site_packages


@pytest.mark.skip
def test_env_system_packages_are_relative_to_lib(
    tmp_path: Path, poetry: Poetry
) -> None:
    venv_path = tmp_path / "venv"
    EnvManager(poetry).build_venv(path=venv_path, flags={"system-site-packages": True})
    env = VirtualEnv(venv_path)
    site_dir = Path(site.getsitepackages()[-1])
    for dist in metadata.distributions():
        # Emulate is_relative_to, only available in 3.9+
        with contextlib.suppress(ValueError):
            dist._path.relative_to(site_dir)  # type: ignore[attr-defined]
            break
    assert env.is_path_relative_to_lib(dist._path)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("flags", "packages"),
    [
        ({"no-pip": False}, {"pip"}),
        ({"no-pip": False, "no-wheel": True}, {"pip"}),
        ({"no-pip": False, "no-wheel": False}, {"pip", "wheel"}),
        ({"no-pip": True}, set()),
        ({"no-setuptools": False}, {"setuptools"}),
        ({"no-setuptools": True}, set()),
        ({"setuptools": "bundle"}, {"setuptools"}),
        ({"no-pip": True, "no-setuptools": False}, {"setuptools"}),
        ({"no-wheel": False}, {"wheel"}),
        ({"wheel": "bundle"}, {"wheel"}),
        ({}, set()),
    ],
)
def test_env_no_pip(
    tmp_path: Path, poetry: Poetry, flags: dict[str, str | bool], packages: set[str]
) -> None:
    venv_path = tmp_path / "venv"
    EnvManager(poetry).build_venv(path=venv_path, flags=flags)
    env = VirtualEnv(venv_path)
    installed_repository = InstalledRepository.load(env=env, with_dependencies=True)
    installed_packages = {
        package.name
        for package in installed_repository.packages
        # workaround for BSD test environments
        if package.name != "sqlite3"
    }

    # For python >= 3.12, virtualenv defaults to "--no-setuptools" and "--no-wheel"
    # behaviour, so setting these values to False becomes meaningless.
    if sys.version_info >= (3, 12):
        if not flags.get("no-setuptools", True):
            packages.discard("setuptools")
        if not flags.get("no-wheel", True):
            packages.discard("wheel")

    assert installed_packages == packages


def test_env_finds_the_correct_executables(tmp_path: Path, manager: EnvManager) -> None:
    venv_path = tmp_path / "Virtual Env"
    manager.build_venv(venv_path, with_pip=True)
    venv = VirtualEnv(venv_path)

    default_executable = expected_executable = f"python{'.exe' if WINDOWS else ''}"
    default_pip_executable = expected_pip_executable = f"pip{'.exe' if WINDOWS else ''}"
    major_executable = f"python{sys.version_info[0]}{'.exe' if WINDOWS else ''}"
    major_pip_executable = f"pip{sys.version_info[0]}{'.exe' if WINDOWS else ''}"

    if (
        venv._bin_dir.joinpath(default_executable).exists()
        and venv._bin_dir.joinpath(major_executable).exists()
    ):
        venv._bin_dir.joinpath(default_executable).unlink()
        expected_executable = major_executable

    if (
        venv._bin_dir.joinpath(default_pip_executable).exists()
        and venv._bin_dir.joinpath(major_pip_executable).exists()
    ):
        venv._bin_dir.joinpath(default_pip_executable).unlink()
        expected_pip_executable = major_pip_executable

    venv = VirtualEnv(venv_path)

    assert Path(venv.python).name == expected_executable
    assert Path(venv.pip).name.startswith(expected_pip_executable.split(".")[0])


def test_env_finds_the_correct_executables_for_generic_env(
    tmp_path: Path, manager: EnvManager
) -> None:
    venv_path = tmp_path / "Virtual Env"
    child_venv_path = tmp_path / "Child Virtual Env"
    manager.build_venv(venv_path, with_pip=True)
    parent_venv = VirtualEnv(venv_path)
    manager.build_venv(child_venv_path, executable=parent_venv.python, with_pip=True)
    venv = GenericEnv(parent_venv.path, child_env=VirtualEnv(child_venv_path))

    expected_executable = (
        f"python{sys.version_info[0]}.{sys.version_info[1]}{'.exe' if WINDOWS else ''}"
    )
    expected_pip_executable = (
        f"pip{sys.version_info[0]}.{sys.version_info[1]}{'.exe' if WINDOWS else ''}"
    )

    if WINDOWS:
        expected_executable = "python.exe"
        expected_pip_executable = "pip.exe"

    assert Path(venv.python).name == expected_executable
    assert Path(venv.pip).name == expected_pip_executable


def test_env_finds_fallback_executables_for_generic_env(
    tmp_path: Path, manager: EnvManager
) -> None:
    venv_path = tmp_path / "Virtual Env"
    child_venv_path = tmp_path / "Child Virtual Env"
    manager.build_venv(venv_path, with_pip=True)
    parent_venv = VirtualEnv(venv_path)
    manager.build_venv(child_venv_path, executable=parent_venv.python, with_pip=True)
    venv = GenericEnv(parent_venv.path, child_env=VirtualEnv(child_venv_path))

    default_executable = f"python{'.exe' if WINDOWS else ''}"
    major_executable = f"python{sys.version_info[0]}{'.exe' if WINDOWS else ''}"
    minor_executable = (
        f"python{sys.version_info[0]}.{sys.version_info[1]}{'.exe' if WINDOWS else ''}"
    )
    expected_executable = minor_executable
    if (
        venv._bin_dir.joinpath(expected_executable).exists()
        and venv._bin_dir.joinpath(major_executable).exists()
    ):
        venv._bin_dir.joinpath(expected_executable).unlink()
        expected_executable = major_executable

    if (
        venv._bin_dir.joinpath(expected_executable).exists()
        and venv._bin_dir.joinpath(default_executable).exists()
    ):
        venv._bin_dir.joinpath(expected_executable).unlink()
        expected_executable = default_executable

    default_pip_executable = f"pip{'.exe' if WINDOWS else ''}"
    major_pip_executable = f"pip{sys.version_info[0]}{'.exe' if WINDOWS else ''}"
    minor_pip_executable = (
        f"pip{sys.version_info[0]}.{sys.version_info[1]}{'.exe' if WINDOWS else ''}"
    )
    expected_pip_executable = minor_pip_executable
    if (
        venv._bin_dir.joinpath(expected_pip_executable).exists()
        and venv._bin_dir.joinpath(major_pip_executable).exists()
    ):
        venv._bin_dir.joinpath(expected_pip_executable).unlink()
        expected_pip_executable = major_pip_executable

    if (
        venv._bin_dir.joinpath(expected_pip_executable).exists()
        and venv._bin_dir.joinpath(default_pip_executable).exists()
    ):
        venv._bin_dir.joinpath(expected_pip_executable).unlink()
        expected_pip_executable = default_pip_executable

    if not venv._bin_dir.joinpath(expected_executable).exists():
        expected_executable = default_executable

    if not venv._bin_dir.joinpath(expected_pip_executable).exists():
        expected_pip_executable = default_pip_executable

    venv = GenericEnv(parent_venv.path, child_env=VirtualEnv(child_venv_path))

    assert Path(venv.python).name == expected_executable
    assert Path(venv.pip).name == expected_pip_executable


def test_create_venv_accepts_fallback_version_w_nonzero_patchlevel(
    manager: EnvManager,
    poetry: Poetry,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
    venv_name: str,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry.package.python_versions = "~3.5.1"

    orig_run = subprocess.run

    def mock_run(cmd: str, *_: Any, **__: Any) -> str:
        if "/usr/bin/python3.5" in cmd:
            return MockSubprocRun("/usr/local")
        return orig_run(cmd, *_, **__)

    def mock_check_output(cmd: str, *args: Any, **kwargs: Any) -> str:
        if GET_PYTHON_VERSION_ONELINER in cmd:
            executable = cmd[0]
            if "python3.5" in str(executable):
                return "3.5.12"
            else:
                return "3.7.1"
        else:
            return "/usr/bin/python3.5"

    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch("subprocess.run", side_effect=mock_run)
    check_output = mocker.patch(
        "subprocess.check_output",
        side_effect=mock_check_output,
    )
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    manager.create_venv()

    assert check_output.called
    m.assert_called_with(
        config_virtualenvs_path / f"{venv_name}-py3.5",
        executable=Path("/usr/bin/python3.5"),
        flags={
            "always-copy": False,
            "system-site-packages": False,
            "no-pip": False,
            "no-setuptools": False,
        },
        prompt="simple-project-py3.5",
    )


def test_generate_env_name_ignores_case_for_case_insensitive_fs(
    poetry: Poetry,
    tmp_path: Path,
) -> None:
    venv_name1 = EnvManager.generate_env_name(poetry.package.name, "MyDiR")
    venv_name2 = EnvManager.generate_env_name(poetry.package.name, "mYdIr")
    if sys.platform == "win32":
        assert venv_name1 == venv_name2
    else:
        assert venv_name1 != venv_name2


def test_generate_env_name_uses_real_path(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch("os.path.realpath", return_value="the_real_dir")
    venv_name1 = EnvManager.generate_env_name("simple-project", "the_real_dir")
    venv_name2 = EnvManager.generate_env_name("simple-project", "linked_dir")
    assert venv_name1 == venv_name2


@pytest.fixture()
def extended_without_setup_poetry(fixture_dir: FixtureDirGetter) -> Poetry:
    poetry = Factory().create_poetry(fixture_dir("extended_project_without_setup"))

    return poetry


def test_build_environment_called_build_script_specified(
    mocker: MockerFixture, extended_without_setup_poetry: Poetry, tmp_path: Path
) -> None:
    project_env = MockEnv(path=tmp_path / "project")
    ephemeral_env = MockEnv(path=tmp_path / "ephemeral")

    mocker.patch(
        "poetry.utils.env.ephemeral_environment"
    ).return_value.__enter__.return_value = ephemeral_env

    with build_environment(extended_without_setup_poetry, project_env) as env:
        assert env == ephemeral_env
        assert env.executed == [  # type: ignore[attr-defined]
            [
                str(sys.executable),
                env.pip_embedded,
                "install",
                "--disable-pip-version-check",
                "--ignore-installed",
                "--no-input",
                *extended_without_setup_poetry.pyproject.build_system.requires,
            ]
        ]


def test_build_environment_not_called_without_build_script_specified(
    mocker: MockerFixture, poetry: Poetry, tmp_path: Path
) -> None:
    project_env = MockEnv(path=tmp_path / "project")
    ephemeral_env = MockEnv(path=tmp_path / "ephemeral")

    mocker.patch(
        "poetry.utils.env.ephemeral_environment"
    ).return_value.__enter__.return_value = ephemeral_env

    with build_environment(poetry, project_env) as env:
        assert env == project_env
        assert not env.executed  # type: ignore[attr-defined]


@pytest.mark.skipif(sys.platform == 'darwin', reason='no hardcoded bin on macos')
def test_create_venv_project_name_empty_sets_correct_prompt(
    fixture_dir: FixtureDirGetter,
    project_factory: ProjectFactory,
    config: Config,
    mocker: MockerFixture,
    config_virtualenvs_path: Path,
) -> None:
    if "VIRTUAL_ENV" in os.environ:
        del os.environ["VIRTUAL_ENV"]

    poetry = project_factory("no", source=fixture_dir("no_name_project"))
    manager = EnvManager(poetry)

    poetry.package.python_versions = "^3.7"
    venv_name = manager.generate_env_name("", str(poetry.file.path.parent))

    mocker.patch("sys.version_info", (2, 7, 16))
    mocker.patch("shutil.which", side_effect=lambda py: f"/usr/bin/{py}")
    mocker.patch(
        "subprocess.check_output",
        side_effect=check_output_wrapper(Version.parse("3.7.5")),
    )
    m = mocker.patch(
        "poetry.utils.env.EnvManager.build_venv", side_effect=lambda *args, **kwargs: ""
    )

    manager.create_venv()

    m.assert_called_with(
        config_virtualenvs_path / f"{venv_name}-py3.7",
        executable=Path("/usr/bin/python"),
        flags={
            "always-copy": False,
            "system-site-packages": False,
            "no-pip": False,
            "no-setuptools": False,
        },
        prompt="virtualenv-py3.7",
    )


def test_fallback_on_detect_active_python(
    poetry: Poetry, mocker: MockerFixture
) -> None:
    m = mocker.patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "some command"),
    )
    env_manager = EnvManager(poetry)
    active_python = env_manager._detect_active_python()

    assert active_python is None
    assert m.call_count == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_detect_active_python_with_bat(poetry: Poetry, tmp_path: Path) -> None:
    """On Windows pyenv uses batch files for python management."""
    python_wrapper = tmp_path / "python.bat"
    wrapped_python = Path(r"C:\SpecialPython\python.exe")
    with python_wrapper.open("w") as f:
        f.write(f"@echo {wrapped_python}")
    os.environ["PATH"] = str(python_wrapper.parent) + os.pathsep + os.environ["PATH"]

    active_python = EnvManager(poetry)._detect_active_python()

    assert active_python == wrapped_python


def test_command_from_bin_preserves_relative_path(manager: EnvManager) -> None:
    # https://github.com/python-poetry/poetry/issues/7959
    env = manager.get()
    command = env.get_command_from_bin("./foo.py")
    assert command == ["./foo.py"]
