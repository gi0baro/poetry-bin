import pytest

from poetry.utils._compat import Path
from poetry.utils.env import MockEnv


@pytest.fixture(autouse=True)
def setup(mocker):
    mocker.patch(
        "poetry.utils.env.EnvManager.get",
        return_value=MockEnv(
            path=Path("/prefix"), base=Path("/base/prefix"), is_venv=True
        ),
    )


@pytest.fixture
def tester(command_tester_factory):
    return command_tester_factory("env info")


def test_env_info_displays_complete_info(tester):
    tester.execute()

    expected = """
Virtualenv
Python:         3.7.0
Implementation: CPython
Path:           {prefix}
Valid:          True

System
Platform: darwin
OS:       posix
Python:   {base_prefix}
""".format(
        prefix=str(Path("/prefix")), base_prefix=str(Path("/base/prefix"))
    )

    assert expected == tester.io.fetch_output()


def test_env_info_displays_path_only(tester):
    tester.execute("--path")
    expected = str(Path("/prefix"))
    assert expected + "\n" == tester.io.fetch_output()
