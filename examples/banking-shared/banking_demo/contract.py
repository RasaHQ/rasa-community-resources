"""Our versioned domain schemas; no vendor schema or network resolution."""

from importlib.resources import files
import json

from jsonschema import Draft202012Validator, FormatChecker


CONTRACT = json.loads(files("banking_demo").joinpath("contracts", "banking-v1.json").read_text())
VERSION = CONTRACT["version"]


def schema(tool, direction):
    return CONTRACT["tools"][tool][direction]


def validate(tool, direction, value):
    Draft202012Validator(schema(tool, direction), format_checker=FormatChecker()).validate(value)


def public_result(tool, profile, value):
    metadata = {"contract_version": VERSION, "profile": profile,
                "mapping_kind": "illustrative", "fixture": "shared-banking-contract"}
    result = {"state": "supplied", **value, **metadata}
    try:
        validate(tool, "output", result)
    except Exception:
        # Never serialize a validation error: it can contain a raw adapter value.
        result = {**metadata, "state": "unavailable", "reason": "invalid_domain_result"}
    return result
