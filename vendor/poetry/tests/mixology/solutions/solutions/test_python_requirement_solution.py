import pytest

from clikit.io.buffered_io import BufferedIO

from poetry.core.packages.dependency import Dependency
from poetry.mixology.failure import SolveFailure
from poetry.mixology.incompatibility import Incompatibility
from poetry.mixology.incompatibility_cause import PythonCause
from poetry.mixology.term import Term
from poetry.puzzle.exceptions import SolverProblemError
from poetry.utils._compat import PY36


@pytest.mark.skipif(
    not PY36, reason="Error solutions are only available for Python ^3.6"
)
def test_it_provides_the_correct_solution():
    from poetry.mixology.solutions.solutions import PythonRequirementSolution

    incompatibility = Incompatibility(
        [Term(Dependency("foo", "^1.0"), True)], PythonCause("^3.5", ">=3.6")
    )
    exception = SolverProblemError(SolveFailure(incompatibility))
    solution = PythonRequirementSolution(exception)

    title = "Check your dependencies Python requirement."
    description = """\
The Python requirement can be specified via the `python` or `markers` properties

For foo, a possible solution would be to set the `python` property to ">=3.6,<4.0"\
"""
    links = [
        "https://python-poetry.org/docs/dependency-specification/#python-restricted-dependencies",
        "https://python-poetry.org/docs/dependency-specification/#using-environment-markers",
    ]

    assert title == solution.solution_title
    assert (
        description == BufferedIO().remove_format(solution.solution_description).strip()
    )
    assert links == solution.documentation_links
