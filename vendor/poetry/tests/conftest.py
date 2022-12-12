from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import tempfile

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import TextIO

import httpretty
import pytest

from keyring.backend import KeyringBackend

from poetry.config.config import Config as BaseConfig
from poetry.config.dict_config_source import DictConfigSource
from poetry.factory import Factory
from poetry.inspection.info import PackageInfo
from poetry.inspection.info import PackageInfoError
from poetry.layouts import layout
from poetry.repositories import Repository
from poetry.repositories import RepositoryPool
from poetry.utils.env import EnvManager
from poetry.utils.env import SystemEnv
from poetry.utils.env import VirtualEnv
from poetry.utils.helpers import remove_directory
from tests.helpers import MOCK_DEFAULT_GIT_REVISION
from tests.helpers import TestLocker
from tests.helpers import TestRepository
from tests.helpers import get_package
from tests.helpers import isolated_environment
from tests.helpers import mock_clone
from tests.helpers import mock_download


if TYPE_CHECKING:
    from collections.abc import Iterator

    from _pytest.config import Config as PyTestConfig
    from _pytest.config.argparsing import Parser
    from pytest_mock import MockerFixture

    from poetry.poetry import Poetry
    from tests.types import FixtureCopier
    from tests.types import FixtureDirGetter
    from tests.types import ProjectFactory


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--integration",
        action="store_true",
        dest="integration",
        default=False,
        help="enable integration tests",
    )


def pytest_configure(config: PyTestConfig) -> None:
    config.addinivalue_line("markers", "integration: mark integration tests")

    if not config.option.integration:
        config.option.markexpr = "not integration"


class Config(BaseConfig):
    def get(self, setting_name: str, default: Any = None) -> Any:
        self.merge(self._config_source.config)
        self.merge(self._auth_config_source.config)

        return super().get(setting_name, default=default)

    def raw(self) -> dict[str, Any]:
        self.merge(self._config_source.config)
        self.merge(self._auth_config_source.config)

        return super().raw()

    def all(self) -> dict[str, Any]:
        self.merge(self._config_source.config)
        self.merge(self._auth_config_source.config)

        return super().all()


class DummyBackend(KeyringBackend):
    def __init__(self) -> None:
        self._passwords = {}

    @classmethod
    def priority(cls) -> int:
        return 42

    def set_password(self, service: str, username: str | None, password: Any) -> None:
        self._passwords[service] = {username: password}

    def get_password(self, service: str, username: str | None) -> Any:
        return self._passwords.get(service, {}).get(username)

    def get_credential(self, service: str, username: str | None) -> Any:
        return self._passwords.get(service, {}).get(username)

    def delete_password(self, service: str, username: str | None) -> None:
        if service in self._passwords and username in self._passwords[service]:
            del self._passwords[service][username]


@pytest.fixture()
def dummy_keyring() -> DummyBackend:
    return DummyBackend()


@pytest.fixture()
def with_simple_keyring(dummy_keyring: DummyBackend) -> None:
    import keyring

    keyring.set_keyring(dummy_keyring)


@pytest.fixture()
def with_fail_keyring() -> None:
    import keyring

    from keyring.backends.fail import Keyring

    keyring.set_keyring(Keyring())


@pytest.fixture()
def with_null_keyring() -> None:
    import keyring

    from keyring.backends.null import Keyring

    keyring.set_keyring(Keyring())


@pytest.fixture()
def with_chained_fail_keyring(mocker: MockerFixture) -> None:
    from keyring.backends.fail import Keyring

    mocker.patch("keyring.backend.get_all_keyring", lambda: [Keyring()])
    import keyring

    from keyring.backends.chainer import ChainerBackend

    keyring.set_keyring(ChainerBackend())


@pytest.fixture()
def with_chained_null_keyring(mocker: MockerFixture) -> None:
    from keyring.backends.null import Keyring

    mocker.patch("keyring.backend.get_all_keyring", lambda: [Keyring()])
    import keyring

    from keyring.backends.chainer import ChainerBackend

    keyring.set_keyring(ChainerBackend())


@pytest.fixture
def config_cache_dir(tmp_dir: str) -> Path:
    path = Path(tmp_dir) / ".cache" / "pypoetry"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def config_virtualenvs_path(config_cache_dir: Path) -> Path:
    return config_cache_dir / "virtualenvs"


@pytest.fixture
def config_source(config_cache_dir: Path) -> DictConfigSource:
    source = DictConfigSource()
    source.add_property("cache-dir", str(config_cache_dir))

    return source


@pytest.fixture
def auth_config_source() -> DictConfigSource:
    source = DictConfigSource()

    return source


@pytest.fixture(autouse=True)
def config(
    config_source: DictConfigSource,
    auth_config_source: DictConfigSource,
    mocker: MockerFixture,
) -> Config:
    import keyring

    from keyring.backends.fail import Keyring

    keyring.set_keyring(Keyring())

    c = Config()
    c.merge(config_source.config)
    c.set_config_source(config_source)
    c.set_auth_config_source(auth_config_source)

    mocker.patch("poetry.config.config.Config.create", return_value=c)
    mocker.patch("poetry.config.config.Config.set_config_source")

    return c


@pytest.fixture()
def config_dir(tmp_dir: str) -> Path:
    return Path(tempfile.mkdtemp(prefix="poetry_config_", dir=tmp_dir))


@pytest.fixture(autouse=True)
def mock_user_config_dir(mocker: MockerFixture, config_dir: Path) -> None:
    mocker.patch("poetry.locations.CONFIG_DIR", new=config_dir)
    mocker.patch("poetry.config.config.CONFIG_DIR", new=config_dir)


@pytest.fixture(autouse=True)
def download_mock(mocker: MockerFixture) -> None:
    # Patch download to not download anything but to just copy from fixtures
    mocker.patch("poetry.utils.helpers.download_file", new=mock_download)
    mocker.patch("poetry.puzzle.provider.download_file", new=mock_download)
    mocker.patch("poetry.repositories.http_repository.download_file", new=mock_download)


@pytest.fixture(autouse=True)
def pep517_metadata_mock(mocker: MockerFixture) -> None:
    def get_pep517_metadata(path: Path) -> PackageInfo:
        with suppress(PackageInfoError):
            return PackageInfo.from_setup_files(path)
        return PackageInfo(name="demo", version="0.1.2")

    mocker.patch(
        "poetry.inspection.info.get_pep517_metadata",
        get_pep517_metadata,
    )


@pytest.fixture
def environ() -> Iterator[None]:
    with isolated_environment():
        yield


@pytest.fixture(autouse=True)
def isolate_environ() -> Iterator[None]:
    """Ensure the environment is isolated from user configuration."""
    with isolated_environment():
        for var in os.environ:
            if var.startswith("POETRY_") or var in {"PYTHONPATH", "VIRTUAL_ENV"}:
                del os.environ[var]

        yield


@pytest.fixture(autouse=True)
def git_mock(mocker: MockerFixture) -> None:
    # Patch git module to not actually clone projects
    mocker.patch("poetry.vcs.git.Git.clone", new=mock_clone)
    p = mocker.patch("poetry.vcs.git.Git.get_revision")
    p.return_value = MOCK_DEFAULT_GIT_REVISION


@pytest.fixture
def http() -> Iterator[type[httpretty.httpretty]]:
    httpretty.reset()
    with httpretty.enabled(allow_net_connect=False):
        yield httpretty


@pytest.fixture
def fixture_base() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_dir(fixture_base: Path) -> FixtureDirGetter:
    def _fixture_dir(name: str) -> Path:
        return fixture_base / name

    return _fixture_dir


@pytest.fixture
def tmp_dir() -> Iterator[str]:
    dir_ = tempfile.mkdtemp(prefix="poetry_")

    yield Path(dir_).resolve().as_posix()

    remove_directory(dir_, force=True)


@pytest.fixture
def mocked_open_files(mocker: MockerFixture) -> list:
    files = []
    original = Path.open

    def mocked_open(self: Path, *args: Any, **kwargs: Any) -> TextIO:
        if self.name in {"pyproject.toml"}:
            return mocker.MagicMock()
        return original(self, *args, **kwargs)

    mocker.patch("pathlib.Path.open", mocked_open)

    return files


@pytest.fixture
def tmp_venv(tmp_dir: str) -> Iterator[VirtualEnv]:
    venv_path = Path(tmp_dir) / "venv"

    EnvManager.build_venv(str(venv_path))

    venv = VirtualEnv(venv_path)
    yield venv

    shutil.rmtree(str(venv.path))


@pytest.fixture
def installed() -> Repository:
    return Repository("installed")


@pytest.fixture(scope="session")
def current_env() -> SystemEnv:
    return SystemEnv(Path(sys.executable))


@pytest.fixture(scope="session")
def current_python(current_env: SystemEnv) -> tuple[int, int, int]:
    return current_env.version_info[:3]


@pytest.fixture(scope="session")
def default_python(current_python: tuple[int, int, int]) -> str:
    return "^" + ".".join(str(v) for v in current_python[:2])


@pytest.fixture
def repo(http: type[httpretty.httpretty]) -> TestRepository:
    http.register_uri(
        http.GET,
        re.compile("^https?://foo.bar/(.+?)$"),
    )
    return TestRepository(name="foo")


@pytest.fixture
def project_factory(
    tmp_dir: str,
    config: Config,
    repo: TestRepository,
    installed: Repository,
    default_python: str,
    load_required_fixtures: None,
) -> ProjectFactory:
    workspace = Path(tmp_dir)

    def _factory(
        name: str | None = None,
        dependencies: dict[str, str] | None = None,
        dev_dependencies: dict[str, str] | None = None,
        pyproject_content: str | None = None,
        poetry_lock_content: str | None = None,
        install_deps: bool = True,
        source: Path | None = None,
        locker_config: dict[str, Any] | None = None,
    ) -> Poetry:
        project_dir = workspace / f"poetry-fixture-{name}"
        dependencies = dependencies or {}
        dev_dependencies = dev_dependencies or {}

        if pyproject_content or source:
            if source:
                project_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, project_dir)
            else:
                project_dir.mkdir(parents=True, exist_ok=True)

            if pyproject_content:
                with project_dir.joinpath("pyproject.toml").open(
                    "w", encoding="utf-8"
                ) as f:
                    f.write(pyproject_content)
        else:
            layout("src")(
                name,
                "0.1.0",
                author="PyTest Tester <mc.testy@testface.com>",
                readme_format="md",
                python=default_python,
                dependencies=dependencies,
                dev_dependencies=dev_dependencies,
            ).create(project_dir, with_tests=False)

        if poetry_lock_content:
            lock_file = project_dir / "poetry.lock"
            lock_file.write_text(data=poetry_lock_content, encoding="utf-8")

        poetry = Factory().create_poetry(project_dir)

        locker = TestLocker(
            poetry.locker.lock, locker_config or poetry.locker._local_config
        )
        locker.write()

        poetry.set_locker(locker)
        poetry.set_config(config)

        pool = RepositoryPool()
        pool.add_repository(repo)

        poetry.set_pool(pool)

        if install_deps:
            for deps in [dependencies, dev_dependencies]:
                for name, version in deps.items():
                    pkg = get_package(name, version)
                    repo.add_package(pkg)
                    installed.add_package(pkg)

        return poetry

    return _factory


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def set_simple_log_formatter() -> None:
    """
    This fixture removes any formatting added via IOFormatter.
    """
    for name in logging.Logger.manager.loggerDict:
        for handler in logging.getLogger(name).handlers:
            # replace formatter with simple formatter for testing
            handler.setFormatter(logging.Formatter(fmt="%(message)s"))


@pytest.fixture
def fixture_copier(fixture_base: Path, tmp_dir: str) -> FixtureCopier:
    def _copy(relative_path: str, target: Path | None = None) -> Path:
        path = fixture_base.joinpath(relative_path)
        target = target or Path(tmp_dir, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            return target

        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copyfile(path, target)

        return target

    return _copy


@pytest.fixture
def required_fixtures() -> list[str]:
    return []


@pytest.fixture(autouse=True)
def load_required_fixtures(
    required_fixtures: list[str], fixture_copier: FixtureCopier
) -> None:
    for fixture in required_fixtures:
        fixture_copier(fixture)
