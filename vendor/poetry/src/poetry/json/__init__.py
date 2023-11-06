from __future__ import annotations

import json

from importlib import resources
from typing import Any

import fastjsonschema

from fastjsonschema.exceptions import JsonSchemaException


class ValidationError(ValueError):
    pass


def validate_object(obj: dict[str, Any]) -> list[str]:
    schema = json.loads(resources.read_text(f"{__name__}.schemas", "poetry.json"))

    validate = fastjsonschema.compile(schema)

    errors = []
    try:
        validate(obj)
    except JsonSchemaException as e:
        errors = [e.message]

    core_schema = json.loads(
        resources.read_text("poetry.core.json.schemas", "poetry-schema.json")
    )

    properties = {*schema["properties"].keys(), *core_schema["properties"].keys()}
    additional_properties = set(obj.keys()) - properties
    for key in additional_properties:
        errors.append(f"Additional properties are not allowed ('{key}' was unexpected)")

    return errors
