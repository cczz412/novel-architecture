from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
CONTRACT_PATH = SCHEMAS / "v0_skeleton_contract.schema.json"
FIXTURE_PROFILE_PATH = SCHEMAS / "v0_synthetic_fixture_profile.schema.json"


def load_schema(*, profile: str = "contract") -> dict[str, Any]:
    path = FIXTURE_PROFILE_PATH if profile == "fixture" else CONTRACT_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def validate_def(
    def_name: str,
    instance: Any,
    schema: dict[str, Any] | None = None,
    *,
    profile: str = "contract",
) -> None:
    schema = schema or load_schema(profile=profile)
    Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$defs": schema["$defs"],
            "$ref": f"#/$defs/{def_name}",
        }
    ).validate(instance)
