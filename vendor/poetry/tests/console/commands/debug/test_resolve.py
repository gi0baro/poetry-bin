import pytest

from poetry.factory import Factory
from tests.helpers import get_package


@pytest.fixture()
def tester(command_tester_factory):
    return command_tester_factory("debug resolve")


def test_debug_resolve_gives_resolution_results(tester, repo):
    cachy2 = get_package("cachy", "0.2.0")
    cachy2.add_dependency(Factory.create_dependency("msgpack-python", ">=0.5 <0.6"))

    repo.add_package(get_package("cachy", "0.1.0"))
    repo.add_package(cachy2)
    repo.add_package(get_package("msgpack-python", "0.5.3"))

    tester.execute("cachy")

    expected = """\
Resolving dependencies...

Resolution results:

msgpack-python 0.5.3
cachy          0.2.0
"""

    assert expected == tester.io.fetch_output()


def test_debug_resolve_tree_option_gives_the_dependency_tree(tester, repo):
    cachy2 = get_package("cachy", "0.2.0")
    cachy2.add_dependency(Factory.create_dependency("msgpack-python", ">=0.5 <0.6"))

    repo.add_package(get_package("cachy", "0.1.0"))
    repo.add_package(cachy2)
    repo.add_package(get_package("msgpack-python", "0.5.3"))

    tester.execute("cachy --tree")

    expected = """\
Resolving dependencies...

Resolution results:

cachy 0.2.0
`-- msgpack-python >=0.5 <0.6
"""

    assert expected == tester.io.fetch_output()


def test_debug_resolve_git_dependency(tester, repo):
    repo.add_package(get_package("pendulum", "2.0.3"))
    repo.add_package(get_package("cleo", "0.6.5"))

    tester.execute("git+https://github.com/demo/demo.git")

    expected = """\
Resolving dependencies...

Resolution results:

pendulum 2.0.3
demo     0.1.2
"""

    assert expected == tester.io.fetch_output()
