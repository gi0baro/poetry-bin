"""
An implementation of JSON Schema for Python

The main functionality is provided by the validator classes for each of the
supported JSON Schema versions.

Most commonly, `validate` is the quickest way to simply validate a given
instance under a schema, and will create a validator for you.
"""

import sys

from pathlib import Path

if getattr(sys, "oxidized", False):
    parents = 2 if sys.platform.startswith("win") else 3
    __path_assets__ = Path(__path__[0]).parents[parents] / "assets" / "jsonschema"
else:
    __path_assets__ = Path(__path__[0])


from jsonschema.exceptions import (
    ErrorTree, FormatError, RefResolutionError, SchemaError, ValidationError
)
from jsonschema._format import (
    FormatChecker,
    draft3_format_checker,
    draft4_format_checker,
    draft6_format_checker,
    draft7_format_checker,
)
from jsonschema._types import TypeChecker
from jsonschema.validators import (
    Draft3Validator,
    Draft4Validator,
    Draft6Validator,
    Draft7Validator,
    RefResolver,
    validate,
)

__version__ = "3.2.0"
