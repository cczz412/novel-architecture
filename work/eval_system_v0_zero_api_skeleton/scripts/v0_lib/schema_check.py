from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "v0_skeleton_contract.schema.json"
)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_def(def_name: str, instance: Any, schema: dict[str, Any] | None = None) -> None:
    schema = schema or load_schema()
    Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{def_name}",
        }
    ).validate(instance)
