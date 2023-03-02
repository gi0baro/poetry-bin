from __future__ import annotations

import json

from importlib import resources
from typing import Any

import jsonschema


class ValidationError(ValueError):
    pass


def validate_object(obj: dict[str, Any]) -> list[str]:
    schema = json.loads(resources.read_text(f"{__name__}.schemas", "poetry.json"))

    validator = jsonschema.Draft7Validator(schema)
    validation_errors = sorted(
        validator.iter_errors(obj),
        key=lambda e: e.path,  # type: ignore[no-any-return]
    )

    errors = []

    for error in validation_errors:
        message = error.message
        if error.path:
            path = ".".join(str(x) for x in error.absolute_path)
            message = f"[{path}] {message}"

        errors.append(message)

    core_schema = json.loads(
        resources.read_text("poetry.core.json.schemas", "poetry-schema.json")
    )

    properties = {*schema["properties"].keys(), *core_schema["properties"].keys()}
    additional_properties = set(obj.keys()) - properties
    for key in additional_properties:
        errors.append(f"Additional properties are not allowed ('{key}' was unexpected)")

    return errors
