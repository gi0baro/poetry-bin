from __future__ import annotations

import json
import re
import site

from pathlib import Path
from typing import Any

from packaging.tags import Tag
from poetry.core.constraints.version import Version

from poetry.utils._compat import WINDOWS
from poetry.utils.env.base_env import Env
from poetry.utils.env.script_strings import GET_BASE_PREFIX, GET_SYS_PATH, GET_PYTHON_VERSION, GET_PATHS, GET_SYS_TAGS, GET_ENVIRONMENT_INFO


class SystemEnv(Env):
    """
    A system (i.e. not a virtualenv) Python environment.
    """

    def __init__(self, path: Path, base: Path | None = None, auto_path: bool = True) -> None:
        self._is_windows = bool(WINDOWS)
        if auto_path and path:
            path = Path(
                self._run(
                    [str(path), "-W", "ignore", "-c", GET_BASE_PREFIX],
                ).strip()
            )
        super().__init__(path, base=base)

    @property
    def sys_path(self) -> list[str]:
        output = self.run_python_script(GET_SYS_PATH)
        return json.loads(output)

    def get_version_info(self) -> tuple[Any, ...]:
        output = self.run_python_script(GET_PYTHON_VERSION)
        return tuple([int(s) for s in output.strip().split(".")])

    def get_python_implementation(self) -> str:
        return self.marker_env["platform_python_implementation"]

    def get_paths(self) -> dict[str, str]:
        output = self.run_python_script(GET_PATHS)
        return json.loads(output)

    def get_supported_tags(self) -> list[Tag]:
        output = self.run_python_script(GET_SYS_TAGS)
        return [Tag(*t) for t in json.loads(output)]

    def get_marker_env(self) -> dict[str, Any]:
        output = self.run_python_script(GET_ENVIRONMENT_INFO)
        return json.loads(output)

    def get_pip_version(self) -> Version:
        output = self.run_pip("--version").strip()
        m = re.match("pip (.+?)(?: from .+)?$", output)
        if not m:
            return Version.parse("0.0")
        return Version.parse(m.group(1))

    def is_venv(self) -> bool:
        return self._path != self._base

    def _get_lib_dirs(self) -> list[Path]:
        return super()._get_lib_dirs() + [Path(d) for d in site.getsitepackages()]
