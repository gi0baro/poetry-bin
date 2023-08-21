from __future__ import annotations

import os
import platform
import sys
import sysconfig
import warnings

from pathlib import Path
from typing import Any

from packaging.tags import Tag
from packaging.tags import interpreter_name
from packaging.tags import interpreter_version
from packaging.tags import sys_tags
from poetry.core.constraints.version import Version

from poetry.utils.env.system_env import SystemEnv


class NullEnv(SystemEnv):
    def __init__(
        self, path: Path | None = None, base: Path | None = None, execute: bool = False
    ) -> None:
        if path is None:
            path = Path(sys.prefix)

        super().__init__(path, base=base, auto_path=False)

        self._execute = execute
        self.executed: list[list[str]] = []

    @property
    def python(self) -> str:
        return sys.executable

    @property
    def sys_path(self) -> list[str]:
        return sys.path

    def get_version_info(self) -> tuple[Any, ...]:
        return tuple(sys.version_info)

    def get_python_implementation(self) -> str:
        return platform.python_implementation()

    def get_pip_command(self, embedded: bool = False) -> list[str]:
        return [sys.executable, self.pip_embedded if embedded else self.pip]

    def get_paths(self) -> dict[str, str]:
        # We can't use sysconfig.get_paths() because
        # on some distributions it does not return the proper paths
        # (those used by pip for instance). We go through distutils
        # to get the proper ones.
        import site

        from distutils.command.install import SCHEME_KEYS
        from distutils.core import Distribution

        d = Distribution()
        d.parse_config_files()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "setup.py install is deprecated")
            obj = d.get_command_obj("install", create=True)
        assert obj is not None
        obj.finalize_options()

        paths = sysconfig.get_paths().copy()
        for key in SCHEME_KEYS:
            if key == "headers":
                # headers is not a path returned by sysconfig.get_paths()
                continue

            paths[key] = getattr(obj, f"install_{key}")

        if site.check_enableusersite():
            usersite = getattr(obj, "install_usersite", None)
            userbase = getattr(obj, "install_userbase", None)
            if usersite is not None and userbase is not None:
                paths["usersite"] = usersite
                paths["userbase"] = userbase

        return paths

    def get_supported_tags(self) -> list[Tag]:
        return list(sys_tags())

    def get_marker_env(self) -> dict[str, Any]:
        if hasattr(sys, "implementation"):
            info = sys.implementation.version
            iver = f"{info.major}.{info.minor}.{info.micro}"
            kind = info.releaselevel
            if kind != "final":
                iver += kind[0] + str(info.serial)

            implementation_name = sys.implementation.name
        else:
            iver = "0"
            implementation_name = ""

        return {
            "implementation_name": implementation_name,
            "implementation_version": iver,
            "os_name": os.name,
            "platform_machine": platform.machine(),
            "platform_release": platform.release(),
            "platform_system": platform.system(),
            "platform_version": platform.version(),
            "python_full_version": platform.python_version(),
            "platform_python_implementation": platform.python_implementation(),
            "python_version": ".".join(platform.python_version().split(".")[:2]),
            "sys_platform": sys.platform,
            "version_info": sys.version_info,
            "interpreter_name": interpreter_name(),
            "interpreter_version": interpreter_version(),
        }

    def get_pip_version(self) -> Version:
        from pip import __version__

        return Version.parse(__version__)

    @property
    def paths(self) -> dict[str, str]:
        if self._paths is None:
            self._paths = self.get_paths()
            self._paths["platlib"] = str(self._path / "platlib")
            self._paths["purelib"] = str(self._path / "purelib")
            self._paths["scripts"] = str(self._path / "scripts")
            self._paths["data"] = str(self._path / "data")

        return self._paths

    def _run(self, cmd: list[str], **kwargs: Any) -> str:
        self.executed.append(cmd)

        if self._execute:
            return super()._run(cmd, **kwargs)
        return ""

    def execute(self, bin: str, *args: str, **kwargs: Any) -> int:
        self.executed.append([bin, *list(args)])

        if self._execute:
            return super().execute(bin, *args, **kwargs)
        return 0

    def _bin(self, bin: str) -> str:
        return bin
