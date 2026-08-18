"""Validate C10 v1/v2/v3/v4 records, formal fixtures, semantics, and legacy seams."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


CONTRACT_ID = "C10_INTAKE_MATERIAL_IDENTITY"
V1_VERSION = "v1"
V2_VERSION = "v2"
V3_VERSION = "v3"
V4_VERSION = "v4"
SUPPORTED_VERSIONS = (V1_VERSION, V2_VERSION, V3_VERSION, V4_VERSION)
LATEST_VERSION = V4_VERSION

# Existing product runtime imports VERSION for the legacy default writer.
# Keep it at v1; selective v2 Setting, v3 Title, and future v4 Tags writers dispatch explicitly.
VERSION = V1_VERSION
COORDINATE_BASIS = "DECODED_UNICODE_CODEPOINT_V1"

ROLES_BY_VERSION: dict[str, tuple[str | None, ...]] = {
    V1_VERSION: ("INTRO", "CHAPTER", None),
    V2_VERSION: ("INTRO", "CHAPTER", "SETTING", None),
    V3_VERSION: ("INTRO", "CHAPTER", "SETTING", "TITLE", None),
    V4_VERSION: ("INTRO", "CHAPTER", "SETTING", "TITLE", "TAGS", None),
}
CANDIDATE_ROLES_BY_VERSION: dict[str, tuple[str, ...]] = {
    V1_VERSION: ("INTRO",),
    V2_VERSION: ("INTRO", "SETTING"),
    V3_VERSION: ("INTRO", "SETTING", "TITLE"),
    V4_VERSION: ("INTRO", "SETTING", "TITLE", "TAGS"),
}

CONTRACTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = CONTRACTS_DIR.parents[1]
SCHEMA_PATH = CONTRACTS_DIR / f"{CONTRACT_ID}.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / f"{CONTRACT_ID}.fixtures.jsonl"
ARCHITECTURE_PATH = REPO_ROOT / "novel-mvp" / "ARCHITECTURE.md"

LEGACY_SHA256 = {
    "novel-mvp/contracts/C1_CHAPTER_DOC.md": (
        "0363659ee3c9c754f6c5d4a96c131647bf0e5fb4f6cc2b5c6716f711b8d325f8"
    ),
    "novel-mvp/contracts/C2_SEGMENT.md": (
        "50ca44b1b638ddf7b8012c3b7bc0a2cda7c2c6c4412b7f900e0573852aea1829"
    ),
}

FROZEN_FIXTURE_PREFIX_SHA256 = {
    "v1_first_6_lines": "3a80d8f4eba77190a2e3615c1b2e1412cf3c85b7bb49796cc685b94daf14daa6",
    "v2_next_6_lines": "5911ee952834a45fce57984228e99f63bb73fbe76cce0f0eaefa2e19830726ba",
    "v3_next_8_lines": "4f9a4768881ab200a73861ee565c40b50179474911f69d71aff604e67abecc23",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractValidationError(ValueError):
    """Raised when a C10 record or fixture violates the frozen contract."""


def _fail(path: str, message: str) -> None:
    raise ContractValidationError(f"{path}: {message}")


def _require_exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    actual = set(value)
    if actual != expected:
        _fail(
            path,
            f"field mismatch missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}",
        )
    return value


def _require_non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(path, "must be a non-empty string")
    return value


def _require_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        _fail(path, "must be 64 lowercase hex characters")
    return value


def _require_int(value: Any, path: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        _fail(path, f"must be an integer >= {minimum}")
    return value


def _require_nullable_non_empty_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, path)


def _require_rfc3339_with_timezone(value: Any, path: str) -> str:
    text = _require_non_empty_string(value, path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        _fail(path, f"must be RFC 3339 date-time: {exc}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(path, "must include timezone")
    return text


def validate_record(
    record: Any,
    path: str = "record",
    *,
    supported_versions: tuple[str, ...] = SUPPORTED_VERSIONS,
) -> dict[str, Any]:
    """Validate one C10 record with explicit version dispatch."""

    record = _require_exact_keys(
        record,
        {
            "contract",
            "version",
            "material_unit_id",
            "source_ref",
            "identity_revisions",
        },
        path,
    )
    if record["contract"] != CONTRACT_ID:
        _fail(f"{path}.contract", f"must equal {CONTRACT_ID}")

    version = _require_non_empty_string(record["version"], f"{path}.version")
    if version not in supported_versions:
        if supported_versions == (V1_VERSION,):
            _fail(f"{path}.version", f"must equal {V1_VERSION}")
        _fail(f"{path}.version", f"unsupported version {version}")
    if version not in ROLES_BY_VERSION:
        _fail(f"{path}.version", f"no role policy for {version}")

    _require_non_empty_string(record["material_unit_id"], f"{path}.material_unit_id")

    source_ref = _require_exact_keys(
        record["source_ref"],
        {
            "source_id",
            "source_sha256",
            "coordinate_basis",
            "start",
            "end",
            "slice_sha256",
        },
        f"{path}.source_ref",
    )
    _require_non_empty_string(source_ref["source_id"], f"{path}.source_ref.source_id")
    _require_sha256(source_ref["source_sha256"], f"{path}.source_ref.source_sha256")
    if source_ref["coordinate_basis"] != COORDINATE_BASIS:
        _fail(
            f"{path}.source_ref.coordinate_basis",
            f"must equal {COORDINATE_BASIS}",
        )
    start = _require_int(source_ref["start"], f"{path}.source_ref.start", minimum=0)
    end = _require_int(source_ref["end"], f"{path}.source_ref.end", minimum=1)
    if start >= end:
        _fail(f"{path}.source_ref", "requires start < end")
    _require_sha256(source_ref["slice_sha256"], f"{path}.source_ref.slice_sha256")

    revisions = record["identity_revisions"]
    if not isinstance(revisions, list) or not revisions:
        _fail(f"{path}.identity_revisions", "must be a non-empty array")

    allowed_roles = ROLES_BY_VERSION[version]
    confirmed_roles = tuple(role for role in allowed_roles if role is not None)
    candidate_roles = CANDIDATE_ROLES_BY_VERSION[version]

    for index, revision in enumerate(revisions, start=1):
        revision_path = f"{path}.identity_revisions[{index - 1}]"
        revision = _require_exact_keys(
            revision,
            {
                "revision_no",
                "role",
                "state",
                "basis",
                "actor",
                "recorded_at",
                "reason",
            },
            revision_path,
        )
        revision_no = _require_int(
            revision["revision_no"],
            f"{revision_path}.revision_no",
            minimum=1,
        )
        if revision_no != index:
            _fail(
                f"{revision_path}.revision_no",
                f"must be consecutive and equal {index}",
            )

        role = revision["role"]
        state = revision["state"]
        if role not in allowed_roles:
            role_text = ", ".join("null" if item is None else item for item in allowed_roles)
            _fail(f"{revision_path}.role", f"{version} role must be one of {role_text}")
        if state not in ("CONFIRMED", "CANDIDATE", "UNKNOWN"):
            _fail(f"{revision_path}.state", "unsupported state")

        basis = _require_exact_keys(
            revision["basis"],
            {"type", "reference"},
            f"{revision_path}.basis",
        )
        actor = _require_exact_keys(
            revision["actor"],
            {"type", "reference"},
            f"{revision_path}.actor",
        )
        basis_type = basis["type"]
        actor_type = actor["type"]
        if basis_type not in (
            "USER_DECLARATION",
            "STRUCTURED_ENTRY",
            "CONTENT_CLASSIFICATION_CANDIDATE",
            "NO_ASSERTION",
        ):
            _fail(f"{revision_path}.basis.type", "unsupported basis")
        if actor_type not in ("USER", "SYSTEM", "PARSER", "MODEL"):
            _fail(f"{revision_path}.actor.type", "unsupported actor")

        basis_ref = _require_nullable_non_empty_string(
            basis["reference"],
            f"{revision_path}.basis.reference",
        )
        actor_ref = _require_nullable_non_empty_string(
            actor["reference"],
            f"{revision_path}.actor.reference",
        )
        _require_rfc3339_with_timezone(
            revision["recorded_at"],
            f"{revision_path}.recorded_at",
        )
        reason = _require_nullable_non_empty_string(
            revision["reason"],
            f"{revision_path}.reason",
        )

        if state == "CONFIRMED":
            if role not in confirmed_roles:
                _fail(f"{revision_path}.role", "confirmed identity requires a non-null role")
            if basis_type == "USER_DECLARATION":
                expected_actor = "USER"
            elif basis_type == "STRUCTURED_ENTRY":
                expected_actor = "SYSTEM"
            else:
                _fail(
                    f"{revision_path}.basis.type",
                    "confirmed identity requires explicit authority",
                )
            if actor_type != expected_actor:
                _fail(f"{revision_path}.actor.type", f"must equal {expected_actor}")
            if basis_ref is None or actor_ref is None:
                _fail(revision_path, "confirmed identity requires basis and actor references")
            if reason is None:
                _fail(f"{revision_path}.reason", "confirmed identity requires a reason")
        elif state == "CANDIDATE":
            if role not in candidate_roles:
                _fail(
                    f"{revision_path}.role",
                    f"{version} candidate role must be one of {', '.join(candidate_roles)}",
                )
            if basis_type != "CONTENT_CLASSIFICATION_CANDIDATE":
                _fail(f"{revision_path}.basis.type", "candidate requires candidate basis")
            if actor_type not in ("PARSER", "MODEL"):
                _fail(
                    f"{revision_path}.actor.type",
                    "candidate writer must be PARSER or MODEL",
                )
            if basis_ref is None or actor_ref is None:
                _fail(revision_path, "candidate identity requires basis and actor references")
            if reason is None:
                _fail(f"{revision_path}.reason", "candidate identity requires a reason")
        else:
            if role is not None:
                _fail(f"{revision_path}.role", "unknown identity requires null role")
            if basis_type != "NO_ASSERTION" or basis_ref is not None:
                _fail(
                    f"{revision_path}.basis",
                    "unknown identity requires NO_ASSERTION and null reference",
                )
            if actor_type != "SYSTEM":
                _fail(f"{revision_path}.actor.type", "unknown identity must be written by SYSTEM")

    return record


def validate_record_v1(record: Any, path: str = "v1_reader") -> dict[str, Any]:
    """Frozen v1-reader view: accept v1 only and reject v2/v3."""

    return validate_record(record, path, supported_versions=(V1_VERSION,))


def validate_record_v2(record: Any, path: str = "v2_reader") -> dict[str, Any]:
    """Frozen v2-reader view: accept v1/v2 and reject v3/Title."""

    return validate_record(record, path, supported_versions=(V1_VERSION, V2_VERSION))


def validate_record_v3(record: Any, path: str = "v3_reader") -> dict[str, Any]:
    """Frozen v3-reader view: accept v1/v2/v3 and reject v4/Tags."""

    return validate_record(
        record,
        path,
        supported_versions=(V1_VERSION, V2_VERSION, V3_VERSION),
    )


def current_identity(record: dict[str, Any]) -> dict[str, Any]:
    return record["identity_revisions"][-1]


def c1_emission_eligible(record: dict[str, Any]) -> bool:
    identity = current_identity(record)
    return identity["state"] == "CONFIRMED" and identity["role"] == "CHAPTER"


def validate_fixture(fixture: Any, path: str = "fixture") -> dict[str, Any]:
    fixture = _require_exact_keys(
        fixture,
        {"fixture_contract", "case_id", "source", "records", "expected"},
        path,
    )
    fixture_contract = fixture["fixture_contract"]
    fixture_versions = {
        "C10_FIXTURE_V1": V1_VERSION,
        "C10_FIXTURE_V2": V2_VERSION,
        "C10_FIXTURE_V3": V3_VERSION,
        "C10_FIXTURE_V4": V4_VERSION,
    }
    if fixture_contract not in fixture_versions:
        _fail(
            f"{path}.fixture_contract",
            "must be C10_FIXTURE_V1, C10_FIXTURE_V2, C10_FIXTURE_V3, or C10_FIXTURE_V4",
        )
    fixture_version = fixture_versions[fixture_contract]
    case_id = _require_non_empty_string(fixture["case_id"], f"{path}.case_id")

    source = _require_exact_keys(
        fixture["source"],
        {"source_id", "encoding", "normalization", "original_bytes_base64", "source_sha256"},
        f"{path}.source",
    )
    source_id = _require_non_empty_string(source["source_id"], f"{path}.source.source_id")
    encoding = _require_non_empty_string(source["encoding"], f"{path}.source.encoding")
    if source["normalization"] != "none":
        _fail(f"{path}.source.normalization", "must equal none")
    encoded = _require_non_empty_string(
        source["original_bytes_base64"],
        f"{path}.source.original_bytes_base64",
    )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        _fail(f"{path}.source.original_bytes_base64", f"invalid base64: {exc}")
    wanted_source_sha = _require_sha256(
        source["source_sha256"],
        f"{path}.source.source_sha256",
    )
    actual_source_sha = hashlib.sha256(raw).hexdigest()
    if actual_source_sha != wanted_source_sha:
        _fail(f"{path}.source.source_sha256", "does not match original bytes")
    try:
        decoded = raw.decode(encoding, errors="strict")
    except (LookupError, UnicodeDecodeError) as exc:
        _fail(f"{path}.source.encoding", f"strict decode failed: {exc}")

    records = fixture["records"]
    if not isinstance(records, list) or not records:
        _fail(f"{path}.records", "must be a non-empty array")
    unit_ids: set[str] = set()
    spans: list[tuple[int, int]] = []
    for index, record in enumerate(records):
        record_path = f"{path}.records[{index}]"
        record = validate_record(record, record_path)
        if record["version"] != fixture_version:
            _fail(record_path, f"must use {fixture_version} inside {fixture_contract}")
        unit_id = record["material_unit_id"]
        if unit_id in unit_ids:
            _fail(record_path, f"duplicate material_unit_id {unit_id}")
        unit_ids.add(unit_id)
        ref = record["source_ref"]
        if ref["source_id"] != source_id or ref["source_sha256"] != wanted_source_sha:
            _fail(record_path, "source_ref does not bind the fixture source")
        if ref["end"] > len(decoded):
            _fail(f"{record_path}.source_ref.end", "exceeds decoded source length")
        sliced = decoded[ref["start"] : ref["end"]]
        actual_slice_sha = hashlib.sha256(sliced.encode("utf-8")).hexdigest()
        if actual_slice_sha != ref["slice_sha256"]:
            _fail(
                f"{record_path}.source_ref.slice_sha256",
                "does not match exact decoded slice",
            )
        spans.append((ref["start"], ref["end"]))

    spans.sort()
    for previous, current in zip(spans, spans[1:]):
        if current[0] < previous[1]:
            _fail(f"{path}.records", f"overlapping spans {previous} and {current}")

    expected = _require_exact_keys(
        fixture["expected"],
        {"valid", "c1_eligible_units", "m3_direct_units", "exact_source_coverage", "current_roles"},
        f"{path}.expected",
    )
    if expected["valid"] is not True:
        _fail(f"{path}.expected.valid", "formal fixtures must be valid")
    expected_c1 = expected["c1_eligible_units"]
    actual_c1 = [record["material_unit_id"] for record in records if c1_emission_eligible(record)]
    if expected_c1 != actual_c1:
        _fail(f"{path}.expected.c1_eligible_units", f"expected {expected_c1}, got {actual_c1}")
    if expected["m3_direct_units"] != []:
        _fail(f"{path}.expected.m3_direct_units", "C10 never grants direct M3 consumption")
    if expected["exact_source_coverage"] is not True:
        _fail(f"{path}.expected.exact_source_coverage", "formal fixtures require exact coverage")
    cursor = 0
    for start, end in spans:
        if start != cursor:
            _fail(f"{path}.records", f"source coverage gap before {start}")
        cursor = end
    if cursor != len(decoded):
        _fail(f"{path}.records", f"source coverage ends at {cursor}, expected {len(decoded)}")
    actual_roles = {
        record["material_unit_id"]: current_identity(record)["role"]
        for record in records
    }
    if expected["current_roles"] != actual_roles:
        _fail(
            f"{path}.expected.current_roles",
            f"expected {expected['current_roles']}, got {actual_roles}",
        )
    return {
        "case_id": case_id,
        "version": fixture_version,
        "records": len(records),
        "spans": spans,
    }


def _schema_validator_for(
    schema: dict[str, Any],
    record_def: str | None = None,
) -> Draft202012Validator:
    document = copy.deepcopy(schema)
    if record_def is not None:
        document.pop("oneOf", None)
        document["$ref"] = f"#/$defs/{record_def}"
    return Draft202012Validator(
        document,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def validate_schema_constants() -> dict[str, Draft202012Validator]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        _fail("schema", f"invalid Draft 2020-12 schema: {exc.message}")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("schema.$schema", "unexpected JSON Schema dialect")
    refs = [item.get("$ref") for item in schema.get("oneOf", [])]
    if refs != [
        "#/$defs/v1_record",
        "#/$defs/v2_record",
        "#/$defs/v3_record",
        "#/$defs/v4_record",
    ]:
        _fail("schema.oneOf", "must dispatch exactly v1 then v2 then v3 then v4")

    defs = schema.get("$defs", {})
    record_base = defs.get("record_base", {})
    properties = record_base.get("properties", {})
    expected_top_fields = {
        "contract",
        "version",
        "material_unit_id",
        "source_ref",
        "identity_revisions",
    }
    if set(properties) != expected_top_fields or set(record_base.get("required", [])) != expected_top_fields:
        _fail("schema.$defs.record_base", "top-level field set drift")
    if record_base.get("additionalProperties") is not False:
        _fail("schema.$defs.record_base.additionalProperties", "must be false")
    if properties.get("contract", {}).get("const") != CONTRACT_ID:
        _fail("schema.$defs.record_base.properties.contract", "contract const drift")
    if properties.get("version", {}).get("enum") != [
        V1_VERSION,
        V2_VERSION,
        V3_VERSION,
        V4_VERSION,
    ]:
        _fail("schema.$defs.record_base.properties.version", "version enum drift")

    v1_const = defs["v1_record"]["allOf"][1]["properties"]["version"].get("const")
    v2_const = defs["v2_record"]["allOf"][1]["properties"]["version"].get("const")
    v3_const = defs["v3_record"]["allOf"][1]["properties"]["version"].get("const")
    v4_const = defs["v4_record"]["allOf"][1]["properties"]["version"].get("const")
    if (v1_const, v2_const, v3_const, v4_const) != (
        V1_VERSION,
        V2_VERSION,
        V3_VERSION,
        V4_VERSION,
    ):
        _fail("schema.$defs.*_record", "version branch drift")

    v1_roles = defs["v1_revision"]["allOf"][1]["properties"]["role"].get("enum")
    v2_roles = defs["v2_revision"]["allOf"][1]["properties"]["role"].get("enum")
    v3_roles = defs["v3_revision"]["allOf"][1]["properties"]["role"].get("enum")
    v4_roles = defs["v4_revision"]["allOf"][1]["properties"]["role"].get("enum")
    if v1_roles != ["INTRO", "CHAPTER", None]:
        _fail("schema.$defs.v1_revision", "v1 role enum drift")
    if v2_roles != ["INTRO", "CHAPTER", "SETTING", None]:
        _fail("schema.$defs.v2_revision", "v2 role enum drift")
    if v3_roles != ["INTRO", "CHAPTER", "SETTING", "TITLE", None]:
        _fail("schema.$defs.v3_revision", "v3 role enum drift")
    if v4_roles != ["INTRO", "CHAPTER", "SETTING", "TITLE", "TAGS", None]:
        _fail("schema.$defs.v4_revision", "v4 role enum drift")
    v1_candidate = defs["v1_revision"]["allOf"][3]["then"]["properties"]["role"]
    v2_candidate = defs["v2_revision"]["allOf"][3]["then"]["properties"]["role"]
    v3_candidate = defs["v3_revision"]["allOf"][3]["then"]["properties"]["role"]
    v4_candidate = defs["v4_revision"]["allOf"][3]["then"]["properties"]["role"]
    if v1_candidate.get("const") != "INTRO":
        _fail("schema.$defs.v1_revision", "v1 candidate role drift")
    if v2_candidate.get("enum") != ["INTRO", "SETTING"]:
        _fail("schema.$defs.v2_revision", "v2 candidate role drift")
    if v3_candidate.get("enum") != ["INTRO", "SETTING", "TITLE"]:
        _fail("schema.$defs.v3_revision", "v3 candidate role drift")
    if v4_candidate.get("enum") != ["INTRO", "SETTING", "TITLE", "TAGS"]:
        _fail("schema.$defs.v4_revision", "v4 candidate role drift")

    return {
        "all": _schema_validator_for(schema),
        "v1": _schema_validator_for(schema, "v1_record"),
        "v2": _schema_validator_for(schema, "v2_record"),
        "v3": _schema_validator_for(schema, "v3_record"),
        "v4": _schema_validator_for(schema, "v4_record"),
    }


def validate_registry() -> None:
    contract_docs = sorted(CONTRACTS_DIR.glob("C10_*.md"))
    expected_doc = CONTRACTS_DIR / f"{CONTRACT_ID}.md"
    if contract_docs != [expected_doc]:
        _fail("contracts", f"C10 contract ID collision: {[path.name for path in contract_docs]}")
    architecture = ARCHITECTURE_PATH.read_text(encoding="utf-8")
    if architecture.count("| C10 |") != 1:
        _fail("ARCHITECTURE.md", "must contain exactly one C10 registry row")
    row = next(line for line in architecture.splitlines() if line.startswith("| C10 |"))
    if f"contracts/{CONTRACT_ID}.md" not in row:
        _fail("ARCHITECTURE.md", "C10 row does not link the formal contract")
    if (
        "v4" not in row
        or "Tags 产品未实现" not in row
        or "NON_BLOCKING_ADOPTION_STATUS_DEBT" not in row
    ):
        _fail(
            "ARCHITECTURE.md",
            "C10 row must register v4, pending Tags product adoption, and Title adoption debt",
        )


def validate_legacy_shas() -> dict[str, str]:
    result: dict[str, str] = {}
    for relative_path, wanted in LEGACY_SHA256.items():
        actual = hashlib.sha256((REPO_ROOT / relative_path).read_bytes()).hexdigest()
        if actual != wanted:
            _fail(relative_path, f"legacy SHA drift expected={wanted} actual={actual}")
        result[relative_path] = actual
    return result


def validate_frozen_fixture_prefixes() -> dict[str, str]:
    lines = FIXTURE_PATH.read_bytes().splitlines(keepends=True)
    if len(lines) < 20 or not all(line.endswith(b"\n") for line in lines[:20]):
        _fail("fixtures", "frozen v1/v2/v3 fixture prefix line shape drift")
    actual = {
        "v1_first_6_lines": hashlib.sha256(b"".join(lines[:6])).hexdigest(),
        "v2_next_6_lines": hashlib.sha256(b"".join(lines[6:12])).hexdigest(),
        "v3_next_8_lines": hashlib.sha256(b"".join(lines[12:20])).hexdigest(),
    }
    if actual != FROZEN_FIXTURE_PREFIX_SHA256:
        _fail(
            "fixtures",
            f"frozen v1/v2/v3 fixture prefix SHA drift expected={FROZEN_FIXTURE_PREFIX_SHA256} "
            f"actual={actual}",
        )
    return actual


def _expect_failure(action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except ContractValidationError:
        return
    _fail(f"negative_probe.{label}", "invalid input was accepted")


def _require_probe(condition: bool, label: str, message: str) -> None:
    if not condition:
        _fail(f"contract_test.{label}", message)


def run_negative_probes(fixtures: list[dict[str, Any]]) -> int:
    by_id = {fixture["case_id"]: fixture for fixture in fixtures}
    base_record = by_id["CT-FX-01__INTRO_ONLY"]["records"][0]
    probes = 0

    mutated = copy.deepcopy(base_record)
    mutated["may_emit_c1"] = False
    _expect_failure(lambda: validate_record(mutated), "extra_permission_boolean")
    probes += 1

    mutated = copy.deepcopy(base_record)
    mutated["identity_revisions"][0]["actor"]["type"] = "MODEL"
    _expect_failure(lambda: validate_record(mutated), "model_cannot_confirm")
    probes += 1

    mutated = copy.deepcopy(by_id["CT-FX-03__CANDIDATE_INTRO"]["records"][0])
    mutated["identity_revisions"][0]["state"] = "CONFIRMED"
    _expect_failure(lambda: validate_record(mutated), "candidate_basis_cannot_confirm")
    probes += 1

    mutated = copy.deepcopy(by_id["CT-FX-04__UNKNOWN"]["records"][0])
    mutated["identity_revisions"][0]["role"] = "CHAPTER"
    _expect_failure(lambda: validate_record(mutated), "unknown_cannot_default_chapter")
    probes += 1

    mutated = copy.deepcopy(by_id["CT-FX-06__REVISION_INTRO_TO_CHAPTER"]["records"][0])
    mutated["identity_revisions"][1]["revision_no"] = 3
    _expect_failure(lambda: validate_record(mutated), "revision_numbers_must_be_consecutive")
    probes += 1

    mutated = copy.deepcopy(by_id["CT-FX-06__REVISION_INTRO_TO_CHAPTER"]["records"][0])
    mutated["identity_revisions"] = mutated["identity_revisions"][1:]
    _expect_failure(lambda: validate_record(mutated), "revision_chain_must_start_at_one")
    probes += 1

    mutated_fixture = copy.deepcopy(by_id["CT-FX-02__INTRO_PLUS_CHAPTER"])
    source = mutated_fixture["source"]
    decoded = base64.b64decode(source["original_bytes_base64"], validate=True).decode(source["encoding"])
    second_ref = mutated_fixture["records"][1]["source_ref"]
    second_ref["start"] -= 1
    second_ref["slice_sha256"] = hashlib.sha256(
        decoded[second_ref["start"] : second_ref["end"]].encode("utf-8")
    ).hexdigest()
    _expect_failure(lambda: validate_fixture(mutated_fixture), "mixed_spans_must_not_overlap")
    probes += 1

    mutated_fixture = copy.deepcopy(by_id["CT-FX-01__INTRO_ONLY"])
    mutated_fixture["records"][0]["source_ref"]["end"] += 1
    _expect_failure(lambda: validate_fixture(mutated_fixture), "span_must_not_exceed_source")
    probes += 1

    setting_record = by_id["SET-F01__SETTING_ONLY"]["records"][0]

    mutated = copy.deepcopy(setting_record)
    mutated["identity_revisions"][0]["role"] = "TITLE"
    _expect_failure(lambda: validate_record(mutated), "v2_invalid_role")
    probes += 1

    mutated = copy.deepcopy(setting_record)
    mutated["setting_fact"] = True
    _expect_failure(lambda: validate_record(mutated), "setting_truth_field_forbidden")
    probes += 1

    mutated = copy.deepcopy(setting_record)
    mutated["identity_revisions"][0]["actor"]["type"] = "MODEL"
    _expect_failure(lambda: validate_record(mutated), "model_cannot_confirm_setting")
    probes += 1

    mutated = copy.deepcopy(by_id["SET-F04__CANDIDATE_SETTING"]["records"][0])
    mutated["identity_revisions"][0]["actor"] = {
        "type": "USER",
        "reference": "USER-NOT-CANDIDATE-WRITER",
    }
    _expect_failure(lambda: validate_record(mutated), "candidate_setting_authority")
    probes += 1

    mutated = copy.deepcopy(by_id["SET-F05__UNKNOWN"]["records"][0])
    mutated["identity_revisions"][0]["role"] = "SETTING"
    _expect_failure(lambda: validate_record(mutated), "unknown_setting_forbidden")
    probes += 1

    mutated = copy.deepcopy(setting_record)
    mutated["version"] = "v5"
    _expect_failure(lambda: validate_record(mutated), "unknown_version")
    probes += 1

    _expect_failure(lambda: validate_record_v1(setting_record), "old_reader_rejects_v2_setting")
    probes += 1

    mutated = copy.deepcopy(setting_record)
    mutated["version"] = V1_VERSION
    _expect_failure(lambda: validate_record_v1(mutated), "old_reader_rejects_v1_labeled_setting")
    probes += 1

    title_record = by_id["TITLE-F01__TITLE_ONLY"]["records"][0]

    mutated = copy.deepcopy(title_record)
    mutated["title_fact"] = True
    _expect_failure(lambda: validate_record(mutated), "title_truth_field_forbidden")
    probes += 1

    mutated = copy.deepcopy(title_record)
    mutated["identity_revisions"][0]["actor"]["type"] = "MODEL"
    _expect_failure(lambda: validate_record(mutated), "model_cannot_confirm_title")
    probes += 1

    mutated = copy.deepcopy(by_id["TITLE-F06__CANDIDATE_TITLE"]["records"][0])
    mutated["identity_revisions"][0]["actor"] = {
        "type": "USER",
        "reference": "USER-NOT-CANDIDATE-WRITER",
    }
    _expect_failure(lambda: validate_record(mutated), "candidate_title_authority")
    probes += 1

    mutated = copy.deepcopy(by_id["TITLE-F07__UNKNOWN"]["records"][0])
    mutated["identity_revisions"][0]["role"] = "TITLE"
    _expect_failure(lambda: validate_record(mutated), "unknown_title_forbidden")
    probes += 1

    _expect_failure(lambda: validate_record_v2(title_record), "v2_reader_rejects_v3_title")
    probes += 1

    mutated = copy.deepcopy(title_record)
    mutated["version"] = V2_VERSION
    _expect_failure(lambda: validate_record_v2(mutated), "v2_reader_rejects_v2_labeled_title")
    probes += 1

    _expect_failure(lambda: validate_record_v1(title_record), "v1_reader_rejects_v3_title")
    probes += 1

    tags_record = by_id["TAGS-F01__TAGS_ONLY"]["records"][0]

    mutated = copy.deepcopy(tags_record)
    mutated["tag_values"] = ["重生", "权谋", "女强"]
    _expect_failure(lambda: validate_record(mutated), "tags_value_field_forbidden")
    probes += 1

    mutated = copy.deepcopy(tags_record)
    mutated["identity_revisions"][0]["actor"]["type"] = "MODEL"
    _expect_failure(lambda: validate_record(mutated), "model_cannot_confirm_tags")
    probes += 1

    mutated = copy.deepcopy(by_id["TAGS-F04__CANDIDATE_TAGS"]["records"][0])
    mutated["identity_revisions"][0]["actor"] = {
        "type": "USER",
        "reference": "USER-NOT-CANDIDATE-WRITER",
    }
    _expect_failure(lambda: validate_record(mutated), "candidate_tags_authority")
    probes += 1

    mutated = copy.deepcopy(by_id["TAGS-F05__UNKNOWN"]["records"][0])
    mutated["identity_revisions"][0]["role"] = "TAGS"
    _expect_failure(lambda: validate_record(mutated), "unknown_tags_forbidden")
    probes += 1

    _expect_failure(lambda: validate_record_v3(tags_record), "v3_reader_rejects_v4_tags")
    probes += 1
    _expect_failure(lambda: validate_record_v2(tags_record), "v2_reader_rejects_v4_tags")
    probes += 1
    _expect_failure(lambda: validate_record_v1(tags_record), "v1_reader_rejects_v4_tags")
    probes += 1

    for version, reader in (
        (V3_VERSION, validate_record_v3),
        (V2_VERSION, validate_record_v2),
        (V1_VERSION, validate_record_v1),
    ):
        mutated = copy.deepcopy(tags_record)
        mutated["version"] = version
        _expect_failure(
            lambda mutated=mutated, reader=reader: reader(mutated),
            f"{version}_reader_rejects_mislabeled_tags",
        )
        probes += 1

    return probes


def run_setting_contract_tests(
    fixtures: list[dict[str, Any]],
    schema_validators: dict[str, Draft202012Validator],
) -> dict[str, str]:
    by_id = {fixture["case_id"]: fixture for fixture in fixtures}

    setting_only = by_id["SET-F01__SETTING_ONLY"]
    setting_record = validate_record(setting_only["records"][0], "SCT-01")
    setting_identity = current_identity(setting_record)
    _require_probe(
        setting_identity["state"] == "CONFIRMED" and setting_identity["role"] == "SETTING",
        "SCT-01",
        "confirmed Setting record did not survive validation",
    )

    candidate_record = validate_record(
        by_id["SET-F04__CANDIDATE_SETTING"]["records"][0],
        "SCT-02",
    )
    _require_probe(
        current_identity(candidate_record)["state"] == "CANDIDATE"
        and not c1_emission_eligible(candidate_record),
        "SCT-02",
        "candidate Setting gained Chapter authority",
    )

    _require_probe(
        setting_only["expected"]["c1_eligible_units"] == []
        and not c1_emission_eligible(setting_record),
        "SCT-03",
        "Setting-only source emitted Chapter C1 eligibility",
    )

    mixed = by_id["SET-F02__SETTING_PLUS_CHAPTER"]
    validate_fixture(mixed, "SCT-04")
    _require_probe(
        mixed["expected"]["c1_eligible_units"] == ["MU-SET-F02-C"],
        "SCT-04",
        "mixed Setting+Chapter eligibility drift",
    )

    triple = by_id["SET-F03__INTRO_SETTING_CHAPTER"]
    validate_fixture(triple, "SCT-05")
    _require_probe(
        triple["expected"]["c1_eligible_units"] == ["MU-SET-F03-C"]
        and set(triple["expected"]["current_roles"].values()) == {"INTRO", "SETTING", "CHAPTER"},
        "SCT-05",
        "Intro+Setting+Chapter coexistence drift",
    )

    mutated = copy.deepcopy(setting_only)
    mutated["records"][0]["source_ref"]["slice_sha256"] = "0" * 64
    _expect_failure(lambda: validate_fixture(mutated), "SCT-06_exact_slice")

    unknown_record = validate_record(by_id["SET-F05__UNKNOWN"]["records"][0], "SCT-07")
    _require_probe(
        current_identity(unknown_record)["role"] is None
        and not c1_emission_eligible(unknown_record),
        "SCT-07",
        "Unknown defaulted to Chapter",
    )

    v1_fixtures = [item for item in fixtures if item["fixture_contract"] == "C10_FIXTURE_V1"]
    _require_probe(len(v1_fixtures) == 6, "SCT-08", "v1 fixture count drift")
    for fixture in v1_fixtures:
        validate_fixture(fixture, "SCT-08")
        for record in fixture["records"]:
            validate_record_v1(record, "SCT-08.v1_reader")
            errors = list(schema_validators["v1"].iter_errors(record))
            _require_probe(not errors, "SCT-08", f"v1 schema rejected {fixture['case_id']}")

    v1_chapter_records = [
        record
        for fixture in v1_fixtures
        for record in fixture["records"]
        if current_identity(record)["role"] == "CHAPTER"
    ]
    _require_probe(
        bool(v1_chapter_records) and all(c1_emission_eligible(record) for record in v1_chapter_records),
        "SCT-09",
        "v1 Chapter eligibility regressed",
    )

    _expect_failure(lambda: validate_record_v1(setting_record), "SCT-10_old_reader_v2")
    mislabeled = copy.deepcopy(setting_record)
    mislabeled["version"] = V1_VERSION
    _expect_failure(lambda: validate_record_v1(mislabeled), "SCT-10_old_reader_role")
    _require_probe(
        bool(list(schema_validators["v1"].iter_errors(setting_record)))
        and bool(list(schema_validators["v1"].iter_errors(mislabeled))),
        "SCT-10",
        "frozen v1 schema accepted Setting",
    )

    invalid_state = copy.deepcopy(candidate_record)
    revision = invalid_state["identity_revisions"][0]
    revision["state"] = "UNKNOWN"
    revision["basis"] = {"type": "NO_ASSERTION", "reference": None}
    revision["actor"] = {"type": "SYSTEM", "reference": "SCT-11"}
    revision["reason"] = None
    _expect_failure(lambda: validate_record(invalid_state), "SCT-11_setting_unknown")

    _require_probe(
        not c1_emission_eligible(setting_record)
        and setting_only["expected"]["m3_direct_units"] == []
        and not ({"setting_fact", "world_truth", "may_emit_c1", "may_enter_m3"} & set(setting_record)),
        "SCT-12",
        "Setting role gained truth, evidence, or emission authority",
    )
    forbidden_truth = copy.deepcopy(setting_record)
    forbidden_truth["world_truth"] = True
    _expect_failure(lambda: validate_record(forbidden_truth), "SCT-12_truth_field")

    revised = copy.deepcopy(setting_record)
    revised["identity_revisions"].append(
        {
            "revision_no": 2,
            "role": "CHAPTER",
            "state": "CONFIRMED",
            "basis": {"type": "USER_DECLARATION", "reference": "SCT-13-R2"},
            "actor": {"type": "USER", "reference": "USER-SCT-13"},
            "recorded_at": "2026-08-17T14:30:00+08:00",
            "reason": "用户明确改判为章节书稿",
        }
    )
    validate_record(revised, "SCT-13")
    _require_probe(
        current_identity(revised)["role"] == "CHAPTER"
        and c1_emission_eligible(revised)
        and current_identity(setting_record)["role"] == "SETTING",
        "SCT-13",
        "append-only current revision semantics drift",
    )
    broken_revision = copy.deepcopy(revised)
    broken_revision["identity_revisions"][1]["revision_no"] = 3
    _expect_failure(lambda: validate_record(broken_revision), "SCT-13_revision_gap")

    return {f"SCT-{index:02d}": "PASS" for index in range(1, 14)}


def run_title_contract_tests(
    fixtures: list[dict[str, Any]],
    schema_validators: dict[str, Draft202012Validator],
) -> dict[str, str]:
    by_id = {fixture["case_id"]: fixture for fixture in fixtures}

    title_only = by_id["TITLE-F01__TITLE_ONLY"]
    title_record = validate_record(title_only["records"][0], "TCT-01")
    title_identity = current_identity(title_record)
    _require_probe(
        title_identity["state"] == "CONFIRMED" and title_identity["role"] == "TITLE",
        "TCT-01",
        "confirmed Title record did not survive validation",
    )

    candidate_record = validate_record(
        by_id["TITLE-F06__CANDIDATE_TITLE"]["records"][0],
        "TCT-02",
    )
    _require_probe(
        current_identity(candidate_record)["state"] == "CANDIDATE"
        and not c1_emission_eligible(candidate_record),
        "TCT-02",
        "candidate Title gained Chapter authority",
    )

    _require_probe(
        title_only["expected"]["c1_eligible_units"] == []
        and title_only["expected"]["m3_direct_units"] == []
        and not c1_emission_eligible(title_record),
        "TCT-03",
        "Title-only source emitted Chapter or direct M3 eligibility",
    )

    title_chapter = by_id["TITLE-F02__TITLE_PLUS_CHAPTER"]
    validate_fixture(title_chapter, "TCT-04")
    _require_probe(
        title_chapter["expected"]["c1_eligible_units"] == ["MU-TITLE-F02-C"],
        "TCT-04",
        "Title+Chapter eligibility drift",
    )

    title_intro_chapter = by_id["TITLE-F03__TITLE_INTRO_CHAPTER"]
    validate_fixture(title_intro_chapter, "TCT-05")
    _require_probe(
        set(title_intro_chapter["expected"]["current_roles"].values())
        == {"TITLE", "INTRO", "CHAPTER"}
        and title_intro_chapter["expected"]["c1_eligible_units"]
        == ["MU-TITLE-F03-C"],
        "TCT-05",
        "Title+Intro+Chapter coexistence drift",
    )

    title_setting_chapter = by_id["TITLE-F04__TITLE_SETTING_CHAPTER"]
    validate_fixture(title_setting_chapter, "TCT-06")
    _require_probe(
        set(title_setting_chapter["expected"]["current_roles"].values())
        == {"TITLE", "SETTING", "CHAPTER"}
        and title_setting_chapter["expected"]["c1_eligible_units"]
        == ["MU-TITLE-F04-C"],
        "TCT-06",
        "Title+Setting+Chapter coexistence drift",
    )

    all_roles = by_id["TITLE-F05__TITLE_INTRO_SETTING_CHAPTER"]
    validate_fixture(all_roles, "TCT-07")
    _require_probe(
        set(all_roles["expected"]["current_roles"].values())
        == {"TITLE", "INTRO", "SETTING", "CHAPTER"}
        and all_roles["expected"]["c1_eligible_units"] == ["MU-TITLE-F05-C"],
        "TCT-07",
        "Title+Intro+Setting+Chapter coexistence drift",
    )

    exact_slice_failure = copy.deepcopy(title_only)
    exact_slice_failure["records"][0]["source_ref"]["slice_sha256"] = "0" * 64
    _expect_failure(lambda: validate_fixture(exact_slice_failure), "TCT-08_exact_slice")
    _require_probe(
        validate_fixture(all_roles, "TCT-08")["spans"]
        == [(0, 7), (7, 25), (25, 37), (37, 50)],
        "TCT-08",
        "Title mixed-source span identity drift",
    )

    unknown_record = validate_record(by_id["TITLE-F07__UNKNOWN"]["records"][0], "TCT-09")
    _require_probe(
        current_identity(unknown_record)["role"] is None
        and not c1_emission_eligible(unknown_record),
        "TCT-09",
        "Unknown defaulted to Title or Chapter",
    )

    v1_fixtures = [item for item in fixtures if item["fixture_contract"] == "C10_FIXTURE_V1"]
    _require_probe(len(v1_fixtures) == 6, "TCT-10", "v1 fixture count drift")
    for fixture in v1_fixtures:
        validate_fixture(fixture, "TCT-10")
        for record in fixture["records"]:
            validate_record_v1(record, "TCT-10.v1_reader")
            _require_probe(
                not list(schema_validators["v1"].iter_errors(record)),
                "TCT-10",
                f"v1 schema rejected {fixture['case_id']}",
            )

    v2_fixtures = [item for item in fixtures if item["fixture_contract"] == "C10_FIXTURE_V2"]
    _require_probe(len(v2_fixtures) == 6, "TCT-11", "v2 fixture count drift")
    for fixture in v2_fixtures:
        validate_fixture(fixture, "TCT-11")
        for record in fixture["records"]:
            validate_record_v2(record, "TCT-11.v2_reader")
            _require_probe(
                not list(schema_validators["v2"].iter_errors(record)),
                "TCT-11",
                f"v2 schema rejected {fixture['case_id']}",
            )

    _expect_failure(lambda: validate_record_v2(title_record), "TCT-12_v2_reader_v3")
    _expect_failure(lambda: validate_record_v1(title_record), "TCT-12_v1_reader_v3")
    mislabeled = copy.deepcopy(title_record)
    mislabeled["version"] = V2_VERSION
    _expect_failure(lambda: validate_record_v2(mislabeled), "TCT-12_v2_reader_role")
    _require_probe(
        bool(list(schema_validators["v2"].iter_errors(title_record)))
        and bool(list(schema_validators["v2"].iter_errors(mislabeled))),
        "TCT-12",
        "frozen v2 schema accepted Title",
    )

    story_hint = by_id["TITLE-F08__STORY_HINT_TITLE"]
    story_title_record = validate_record(story_hint["records"][0], "TCT-13")
    _require_probe(
        current_identity(story_title_record)["role"] == "TITLE"
        and not c1_emission_eligible(story_title_record)
        and story_hint["expected"]["m3_direct_units"] == []
        and not (
            {"title_fact", "story_fact", "story_evidence", "may_emit_c1", "may_enter_m3"}
            & set(story_title_record)
        ),
        "TCT-13",
        "Title text gained story-fact evidence or emission authority",
    )
    forbidden_story_fact = copy.deepcopy(story_title_record)
    forbidden_story_fact["story_fact"] = "主角重生"
    _expect_failure(lambda: validate_record(forbidden_story_fact), "TCT-13_story_fact")

    return {f"TCT-{index:02d}": "PASS" for index in range(1, 14)}


def run_tags_contract_tests(
    fixtures: list[dict[str, Any]],
    schema_validators: dict[str, Draft202012Validator],
) -> dict[str, str]:
    by_id = {fixture["case_id"]: fixture for fixture in fixtures}

    tags_only = by_id["TAGS-F01__TAGS_ONLY"]
    tags_record = validate_record(tags_only["records"][0], "TGT-01")
    tags_identity = current_identity(tags_record)
    _require_probe(
        tags_identity["state"] == "CONFIRMED" and tags_identity["role"] == "TAGS",
        "TGT-01",
        "confirmed Tags record did not survive validation",
    )

    candidate_record = validate_record(
        by_id["TAGS-F04__CANDIDATE_TAGS"]["records"][0],
        "TGT-02",
    )
    _require_probe(
        current_identity(candidate_record)["state"] == "CANDIDATE"
        and not c1_emission_eligible(candidate_record),
        "TGT-02",
        "candidate Tags gained Chapter authority",
    )

    _require_probe(
        tags_only["expected"]["c1_eligible_units"] == []
        and tags_only["expected"]["m3_direct_units"] == []
        and not c1_emission_eligible(tags_record),
        "TGT-03",
        "Tags-only source emitted Chapter or direct M3 eligibility",
    )

    tags_only_result = validate_fixture(tags_only, "TGT-04")
    _require_probe(
        tags_only_result["records"] == 1
        and tags_only_result["spans"] == [(0, 12)]
        and not (set(tags_record) & {"tag_values", "tag_count", "normalized_tags"}),
        "TGT-04",
        "multi-tag block was not preserved as one material unit",
    )

    tags_chapter = by_id["TAGS-F02__TAGS_PLUS_CHAPTER"]
    validate_fixture(tags_chapter, "TGT-05")
    _require_probe(
        tags_chapter["expected"]["c1_eligible_units"]
        == ["MU-TAGS-F02__TAGS_PLUS_CHAPTER-C"],
        "TGT-05",
        "Tags+Chapter eligibility drift",
    )

    all_roles = by_id["TAGS-F03__FULL_MIXED"]
    validate_fixture(all_roles, "TGT-06")
    _require_probe(
        set(all_roles["expected"]["current_roles"].values())
        == {"TITLE", "INTRO", "SETTING", "TAGS", "CHAPTER"}
        and all_roles["expected"]["c1_eligible_units"]
        == ["MU-TAGS-F03__FULL_MIXED-C"],
        "TGT-06",
        "full mixed-source coexistence drift",
    )

    exact_slice_failure = copy.deepcopy(tags_only)
    exact_slice_failure["records"][0]["source_ref"]["slice_sha256"] = "0" * 64
    _expect_failure(lambda: validate_fixture(exact_slice_failure), "TGT-07_exact_slice")
    disjoint = by_id["TAGS-F08__DISJOINT_TAG_BLOCKS"]
    _require_probe(
        validate_fixture(disjoint, "TGT-07")["spans"]
        == [(0, 9), (9, 22), (22, 31)],
        "TGT-07",
        "disjoint Tags block coverage drift",
    )

    unknown_record = validate_record(by_id["TAGS-F05__UNKNOWN"]["records"][0], "TGT-08")
    _require_probe(
        current_identity(unknown_record)["role"] is None
        and not c1_emission_eligible(unknown_record),
        "TGT-08",
        "Unknown defaulted to Tags or Chapter",
    )

    version_policies = (
        ("C10_FIXTURE_V1", "v1", 6, validate_record_v1),
        ("C10_FIXTURE_V2", "v2", 6, validate_record_v2),
        ("C10_FIXTURE_V3", "v3", 8, validate_record_v3),
    )
    for fixture_contract, schema_key, expected_count, reader in version_policies:
        frozen = [item for item in fixtures if item["fixture_contract"] == fixture_contract]
        _require_probe(
            len(frozen) == expected_count,
            "TGT-09",
            f"{fixture_contract} fixture count drift",
        )
        for fixture in frozen:
            validate_fixture(fixture, "TGT-09")
            for record in fixture["records"]:
                reader(record, "TGT-09.old_reader")
                _require_probe(
                    not list(schema_validators[schema_key].iter_errors(record)),
                    "TGT-09",
                    f"frozen schema rejected {fixture['case_id']}",
                )

    for schema_key, version, reader in (
        ("v1", V1_VERSION, validate_record_v1),
        ("v2", V2_VERSION, validate_record_v2),
        ("v3", V3_VERSION, validate_record_v3),
    ):
        _expect_failure(lambda reader=reader: reader(tags_record), f"TGT-10_{schema_key}_v4")
        mislabeled = copy.deepcopy(tags_record)
        mislabeled["version"] = version
        _expect_failure(
            lambda mislabeled=mislabeled, reader=reader: reader(mislabeled),
            f"TGT-10_{schema_key}_role",
        )
        _require_probe(
            bool(list(schema_validators[schema_key].iter_errors(tags_record)))
            and bool(list(schema_validators[schema_key].iter_errors(mislabeled))),
            "TGT-10",
            f"frozen {schema_key} schema accepted Tags",
        )

    revised = by_id["TAGS-F07__REVISION_TAGS_TO_CHAPTER"]["records"][0]
    validate_record(revised, "TGT-11")
    _require_probe(
        [item["role"] for item in revised["identity_revisions"]] == ["TAGS", "CHAPTER"]
        and c1_emission_eligible(revised),
        "TGT-11",
        "Tags to Chapter revision semantics drift",
    )
    broken_revision = copy.deepcopy(revised)
    broken_revision["identity_revisions"][1]["revision_no"] = 3
    _expect_failure(lambda: validate_record(broken_revision), "TGT-11_revision_gap")

    story_hint = by_id["TAGS-F06__STORY_HINT_TAGS"]
    story_tags_record = validate_record(story_hint["records"][0], "TGT-12")
    forbidden_story_keys = {
        "story_fact",
        "story_evidence",
        "tag_truth",
        "may_emit_c1",
        "may_enter_m3",
    }
    _require_probe(
        current_identity(story_tags_record)["role"] == "TAGS"
        and not c1_emission_eligible(story_tags_record)
        and story_hint["expected"]["m3_direct_units"] == []
        and not (forbidden_story_keys & set(story_tags_record)),
        "TGT-12",
        "Tags text gained story-fact evidence or emission authority",
    )
    forbidden_story_fact = copy.deepcopy(story_tags_record)
    forbidden_story_fact["story_fact"] = "主角重生"
    _expect_failure(lambda: validate_record(forbidden_story_fact), "TGT-12_story_fact")

    for field, value in (
        ("tag_values", ["重生", "权谋", "女强"]),
        ("normalized_tags", ["rebirth", "politics"]),
        ("may_emit_c1", False),
    ):
        extra_field = copy.deepcopy(tags_record)
        extra_field[field] = value
        _expect_failure(
            lambda extra_field=extra_field: validate_record(extra_field),
            f"TGT-13_{field}",
        )

    return {f"TGT-{index:02d}": "PASS" for index in range(1, 14)}


def main() -> int:
    schema_validators = validate_schema_constants()
    fixture_lines = FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
    fixtures = [json.loads(line) for line in fixture_lines if line.strip()]
    expected_case_ids = [
        "CT-FX-01__INTRO_ONLY",
        "CT-FX-02__INTRO_PLUS_CHAPTER",
        "CT-FX-03__CANDIDATE_INTRO",
        "CT-FX-04__UNKNOWN",
        "CT-FX-05__CONFIRMED_CHAPTER",
        "CT-FX-06__REVISION_INTRO_TO_CHAPTER",
        "SET-F01__SETTING_ONLY",
        "SET-F02__SETTING_PLUS_CHAPTER",
        "SET-F03__INTRO_SETTING_CHAPTER",
        "SET-F04__CANDIDATE_SETTING",
        "SET-F05__UNKNOWN",
        "SET-F06__FACT_DENSE_SETTING",
        "TITLE-F01__TITLE_ONLY",
        "TITLE-F02__TITLE_PLUS_CHAPTER",
        "TITLE-F03__TITLE_INTRO_CHAPTER",
        "TITLE-F04__TITLE_SETTING_CHAPTER",
        "TITLE-F05__TITLE_INTRO_SETTING_CHAPTER",
        "TITLE-F06__CANDIDATE_TITLE",
        "TITLE-F07__UNKNOWN",
        "TITLE-F08__STORY_HINT_TITLE",
        "TAGS-F01__TAGS_ONLY",
        "TAGS-F02__TAGS_PLUS_CHAPTER",
        "TAGS-F03__FULL_MIXED",
        "TAGS-F04__CANDIDATE_TAGS",
        "TAGS-F05__UNKNOWN",
        "TAGS-F06__STORY_HINT_TAGS",
        "TAGS-F07__REVISION_TAGS_TO_CHAPTER",
        "TAGS-F08__DISJOINT_TAG_BLOCKS",
    ]
    if [fixture.get("case_id") for fixture in fixtures] != expected_case_ids:
        _fail("fixtures", "twenty-eight-case identity or order drift")

    frozen_fixture_prefixes = validate_frozen_fixture_prefixes()

    for fixture_index, fixture in enumerate(fixtures):
        version_key = {
            "C10_FIXTURE_V1": "v1",
            "C10_FIXTURE_V2": "v2",
            "C10_FIXTURE_V3": "v3",
            "C10_FIXTURE_V4": "v4",
        }.get(fixture.get("fixture_contract"))
        if version_key is None:
            _fail(f"fixtures[{fixture_index}].fixture_contract", "unknown fixture version")
        for record_index, record in enumerate(fixture.get("records", [])):
            for validator_key in ("all", version_key):
                errors = sorted(
                    schema_validators[validator_key].iter_errors(record),
                    key=lambda item: list(item.path),
                )
                if errors:
                    _fail(
                        f"fixtures[{fixture_index}].records[{record_index}]",
                        f"JSON Schema {validator_key} rejected record: {errors[0].message}",
                    )

    fixture_results = [
        validate_fixture(fixture, f"fixtures[{index}]")
        for index, fixture in enumerate(fixtures)
    ]
    negative_probes = run_negative_probes(fixtures)
    setting_contract_tests = run_setting_contract_tests(fixtures, schema_validators)
    title_contract_tests = run_title_contract_tests(fixtures, schema_validators)
    tags_contract_tests = run_tags_contract_tests(fixtures, schema_validators)
    validate_registry()
    legacy_shas = validate_legacy_shas()
    report = {
        "contract": CONTRACT_ID,
        "version": LATEST_VERSION,
        "supported_versions": list(SUPPORTED_VERSIONS),
        "product_writer_compatibility_version": VERSION,
        "status": "PASS",
        "schema": "PASS",
        "fixtures": fixture_results,
        "fixture_count": len(fixture_results),
        "v1_fixture_count": sum(item["version"] == V1_VERSION for item in fixture_results),
        "v2_fixture_count": sum(item["version"] == V2_VERSION for item in fixture_results),
        "v3_fixture_count": sum(item["version"] == V3_VERSION for item in fixture_results),
        "v4_fixture_count": sum(item["version"] == V4_VERSION for item in fixture_results),
        "frozen_fixture_prefix_sha256": frozen_fixture_prefixes,
        "negative_probe_count": negative_probes,
        "setting_contract_tests": setting_contract_tests,
        "title_contract_tests": title_contract_tests,
        "tags_contract_tests": tags_contract_tests,
        "registry": "PASS",
        "legacy_sha256": legacy_shas,
        "setting_product_implementation": "IMPLEMENTED",
        "title_product_implementation": "NOT_IMPLEMENTED",
        "title_adoption_status_debt": "NON_BLOCKING_ADOPTION_STATUS_DEBT",
        "title_content_semantics": "OUT_OF_SCOPE",
        "tags_product_implementation": "NOT_IMPLEMENTED",
        "tags_content_semantics": "OUT_OF_SCOPE",
        "tags_unit_granularity": "ONE_CONTIGUOUS_DECLARED_BLOCK_PER_MATERIAL_UNIT",
        "outline_migration": "NOT_EXECUTED",
        "api_calls": 0,
        "retries": 0,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
