from __future__ import annotations

import json

from importlib import resources
from typing import Any

import fastjsonschema

from fastjsonschema.exceptions import JsonSchemaException


class ValidationError(ValueError):
    pass


def validate_object(obj: dict[str, Any], schema_name: str) -> list[str]:
    try:
        schema = json.loads(
            resources.read_text(f"{__name__}.schemas", f"{schema_name}.json")
        )
    except Exception:
        raise ValueError(f"Schema {schema_name} does not exist.")

    validate = fastjsonschema.compile(schema)

    errors = []
    try:
        validate(obj)
    except JsonSchemaException as e:
        errors = [e.message]

    return errors
