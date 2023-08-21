from __future__ import annotations

import json

from importlib import resources
from typing import Any


class ValidationError(ValueError):
    pass


def validate_object(obj: dict[str, Any], schema_name: str) -> list[str]:
    try:
        schema = json.loads(
            resources.read_text(f"{__name__}.schemas", f"{schema_name}.json")
        )
    except Exception:
        raise ValueError(f"Schema {schema_name} does not exist.")

    from jsonschema import Draft7Validator

    validator = Draft7Validator(schema)
    validation_errors = sorted(validator.iter_errors(obj), key=lambda e: e.path)

    errors = []

    for error in validation_errors:
        message = error.message
        if error.path:
            path = ".".join(map(str, error.absolute_path))
            message = f"[{path}] {message}"

        errors.append(message)

    return errors
