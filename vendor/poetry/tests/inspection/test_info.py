from __future__ import annotations

from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

import pytest

from poetry.inspection.info import PackageInfo
from poetry.inspection.info import PackageInfoError
from poetry.utils._compat import decode
from poetry.utils.env import EnvCommandError
from poetry.utils.env import VirtualEnv


if TYPE_CHECKING:
    from pytest_mock import MockerFixture

FIXTURE_DIR_BASE = Path(__file__).parent.parent / "fixtures"
FIXTURE_DIR_INSPECTIONS = FIXTURE_DIR_BASE / "inspection"


@pytest.fixture(autouse=True)
def pep517_metadata_mock():
    pass


@pytest.fixture
def demo_sdist() -> Path:
    return FIXTURE_DIR_BASE / "distributions" / "demo-0.1.0.tar.gz"


@pytest.fixture
def demo_wheel() -> Path:
    return FIXTURE_DIR_BASE / "distributions" / "demo-0.1.0-py2.py3-none-any.whl"


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    return Path(tmp_path.as_posix())


@pytest.fixture
def demo_setup(source_dir: Path) -> Path:
    setup_py = source_dir / "setup.py"
    setup_py.write_text(
        decode(
            "from setuptools import setup; "
            'setup(name="demo", '
            'version="0.1.0", '
            'install_requires=["package"])'
        )
    )
    return source_dir


@pytest.fixture
def demo_setup_cfg(source_dir: Path) -> Path:
    setup_cfg = source_dir / "setup.cfg"
    setup_cfg.write_text(
        decode(
            "\n".join(
                [
                    "[metadata]",
                    "name = demo",
                    "version = 0.1.0",
                    "[options]",
                    "install_requires = package",
                ]
            )
        )
    )
    return source_dir


@pytest.fixture
def demo_setup_complex(source_dir: Path) -> Path:
    setup_py = source_dir / "setup.py"
    setup_py.write_text(
        decode(
            "from setuptools import setup; "
            'setup(name="demo", '
            'version="0.1.0", '
            'install_requires=[i for i in ["package"]])'
        )
    )
    return source_dir


@pytest.fixture
def demo_setup_complex_pep517_legacy(demo_setup_complex: Path) -> Path:
    pyproject_toml = demo_setup_complex / "pyproject.toml"
    pyproject_toml.write_text(
        decode('[build-system]\nrequires = ["setuptools", "wheel"]')
    )
    return demo_setup_complex


def demo_check_info(info: PackageInfo, requires_dist: set[str] = None) -> None:
    assert info.name == "demo"
    assert info.version == "0.1.0"
    assert info.requires_dist

    if requires_dist:
        assert set(info.requires_dist) == requires_dist
    else:
        assert set(info.requires_dist) in (
            # before https://github.com/python-poetry/poetry-core/pull/510
            {
                'cleo; extra == "foo"',
                "pendulum (>=1.4.4)",
                'tomlkit; extra == "bar"',
            },
            # after https://github.com/python-poetry/poetry-core/pull/510
            {
                'cleo ; extra == "foo"',
                "pendulum (>=1.4.4)",
                'tomlkit ; extra == "bar"',
            },
        )


def test_info_from_sdist(demo_sdist: Path):
    info = PackageInfo.from_sdist(demo_sdist)
    demo_check_info(info)


def test_info_from_wheel(demo_wheel: Path):
    info = PackageInfo.from_wheel(demo_wheel)
    demo_check_info(info)


def test_info_from_bdist(demo_wheel: Path):
    info = PackageInfo.from_bdist(demo_wheel)
    demo_check_info(info)


def test_info_from_poetry_directory():
    info = PackageInfo.from_directory(
        FIXTURE_DIR_INSPECTIONS / "demo", disable_build=True
    )
    demo_check_info(info)


def test_info_from_poetry_directory_fallback_on_poetry_create_error(
    mocker: MockerFixture,
):
    mock_create_poetry = mocker.patch(
        "poetry.inspection.info.Factory.create_poetry", side_effect=RuntimeError
    )
    mock_get_poetry_package = mocker.spy(PackageInfo, "_get_poetry_package")
    mock_get_pep517_metadata = mocker.patch(
        "poetry.inspection.info.get_pep517_metadata"
    )

    PackageInfo.from_directory(FIXTURE_DIR_INSPECTIONS / "demo_poetry_package")

    assert mock_create_poetry.call_count == 1
    assert mock_get_poetry_package.call_count == 1
    assert mock_get_pep517_metadata.call_count == 1


def test_info_from_requires_txt():
    info = PackageInfo.from_metadata(
        FIXTURE_DIR_INSPECTIONS / "demo_only_requires_txt.egg-info"
    )
    demo_check_info(info)


def test_info_from_setup_py(demo_setup: Path):
    info = PackageInfo.from_setup_files(demo_setup)
    demo_check_info(info, requires_dist={"package"})


def test_info_from_setup_cfg(demo_setup_cfg: Path):
    info = PackageInfo.from_setup_files(demo_setup_cfg)
    demo_check_info(info, requires_dist={"package"})


def test_info_no_setup_pkg_info_no_deps():
    info = PackageInfo.from_directory(
        FIXTURE_DIR_INSPECTIONS / "demo_no_setup_pkg_info_no_deps",
        disable_build=True,
    )
    assert info.name == "demo"
    assert info.version == "0.1.0"
    assert info.requires_dist is None


def test_info_setup_simple(mocker: MockerFixture, demo_setup: Path):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup)
    assert spy.call_count == 0
    demo_check_info(info, requires_dist={"package"})


def test_info_setup_cfg(mocker: MockerFixture, demo_setup_cfg: Path):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup_cfg)
    assert spy.call_count == 0
    demo_check_info(info, requires_dist={"package"})


def test_info_setup_complex(demo_setup_complex: Path):
    info = PackageInfo.from_directory(demo_setup_complex)
    demo_check_info(info, requires_dist={"package"})


def test_info_setup_complex_pep517_error(
    mocker: MockerFixture, demo_setup_complex: Path
):
    mocker.patch(
        "poetry.utils.env.VirtualEnv.run",
        autospec=True,
        side_effect=EnvCommandError(CalledProcessError(1, "mock", output="mock")),
    )

    with pytest.raises(PackageInfoError):
        PackageInfo.from_directory(demo_setup_complex)


def test_info_setup_complex_pep517_legacy(demo_setup_complex_pep517_legacy: Path):
    info = PackageInfo.from_directory(demo_setup_complex_pep517_legacy)
    demo_check_info(info, requires_dist={"package"})


def test_info_setup_complex_disable_build(
    mocker: MockerFixture, demo_setup_complex: Path
):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup_complex, disable_build=True)
    assert spy.call_count == 0
    assert info.name == "demo"
    assert info.version == "0.1.0"
    assert info.requires_dist is None


@pytest.mark.parametrize("missing", ["version", "name", "install_requires"])
def test_info_setup_missing_mandatory_should_trigger_pep517(
    mocker: MockerFixture, source_dir: Path, missing: str
):
    setup = "from setuptools import setup; "
    setup += "setup("
    setup += 'name="demo", ' if missing != "name" else ""
    setup += 'version="0.1.0", ' if missing != "version" else ""
    setup += 'install_requires=["package"]' if missing != "install_requires" else ""
    setup += ")"

    setup_py = source_dir / "setup.py"
    setup_py.write_text(decode(setup))

    spy = mocker.spy(VirtualEnv, "run")
    try:
        PackageInfo.from_directory(source_dir)
    except PackageInfoError:
        assert spy.call_count == 3
    else:
        assert spy.call_count == 1


def test_info_prefer_poetry_config_over_egg_info():
    info = PackageInfo.from_directory(
        FIXTURE_DIR_INSPECTIONS / "demo_with_obsolete_egg_info"
    )
    demo_check_info(info)
