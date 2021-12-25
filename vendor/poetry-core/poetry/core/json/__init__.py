import json

from importlib import resources
from typing import List

from jsonschema import Draft7Validator


class ValidationError(ValueError):

    pass


def validate_object(obj, schema_name):  # type: (dict, str) -> List[str]
    try:
        schema = json.loads(
            resources.read_text(
                f"{__name__}.schemas", "{}.json".format(schema_name)
            )
        )
    except Exception:
        raise ValueError("Schema {} does not exist.".format(schema_name))

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
