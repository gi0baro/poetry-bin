import json
import os

from io import open
from pathlib import Path
from typing import List

from jsonschema import Draft7Validator

from .. import __path_assets__

SCHEMA_DIR = (
    __path_assets__ / "json" / "schemas" if __path_assets__ else
    Path(__path__[0]) / "schemas"
)


class ValidationError(ValueError):

    pass


def validate_object(obj, schema_name):  # type: (dict, str) -> List[str]
    schema = os.path.join(SCHEMA_DIR, "{}.json".format(schema_name))

    if not os.path.exists(schema):
        raise ValueError("Schema {} does not exist.".format(schema_name))

    with open(schema, encoding="utf-8") as f:
        schema = json.loads(f.read())

    validator = Draft7Validator(schema)
    validation_errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)

    errors = []

    for error in validation_errors:
        message = error.message
        if error.path:
            message = "[{}] {}".format(
                ".".join(str(x) for x in error.absolute_path), message
            )

        errors.append(message)

    return errors
