"""R01 shared shapes and deterministic checks; no story adoption or permissions."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import secrets

from jsonschema import Draft202012Validator, FormatChecker


_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (_ROOT / "contracts/CHAPTER_STRUCTURE_CONTRACT.schema.json").read_text()
)
CONTRACT_TYPES = {
    name: Draft202012Validator(
        {
            "$schema": SCHEMA["$schema"],
            "$defs": SCHEMA["$defs"],
            "$ref": f"#/$defs/{name}",
        },
        format_checker=FormatChecker(),
    )
    for name in SCHEMA["$defs"]
}
_LOCAL = {
    "fact_items": ("item_id", "fi", "FACT_ITEM", "FactItemRefInput"),
    "materials": ("material_id", "mt", "MATERIAL", "MaterialRefInput"),
    "source_bindings": ("binding_id", "sb", "SOURCE_BINDING", "SourceBindingRefInput"),
    "presentation_items": (
        "item_id",
        "pi",
        "PRESENTATION_ITEM",
        "PresentationItemRefInput",
    ),
}


class StructureError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str = "INVALID_REQUEST") -> None:
    if not condition:
        raise StructureError(code)


def _json_values(value: object) -> None:
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        _require(abs(value) <= 9007199254740991)
    elif type(value) is str:
        _require(not any(0xD800 <= ord(c) <= 0xDFFF for c in value))
    elif type(value) is list:
        for item in value:
            _json_values(item)
    elif type(value) is dict:
        for key, item in value.items():
            _require(type(key) is str)
            _json_values(key)
            _json_values(item)
    else:
        # All numeric machine fields in R01 are integers; raw text is never parsed.
        raise StructureError("INVALID_REQUEST")


def canonical_bytes(value: object) -> bytes:
    _json_values(value)
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def digest(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def raw_digest(value: str) -> str:
    _json_values(value)
    return sha256(value.encode("utf-8")).hexdigest()


def decode_request(raw: object) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def no_float(token):
        raise StructureError("INVALID_REQUEST")

    try:
        if isinstance(raw, bytes):
            _require(not raw.startswith(b"\xef\xbb\xbf"))
            raw = raw.decode("utf-8", errors="strict")
        if isinstance(raw, str):
            raw = json.loads(
                raw,
                object_pairs_hook=pairs,
                parse_float=no_float,
                parse_constant=no_float,
            )
        _require(type(raw) is dict)
        _json_values(raw)
        return deepcopy(raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise StructureError("INVALID_REQUEST") from exc


def validate_shape(name: str, value: object) -> None:
    _json_values(value)
    if not CONTRACT_TYPES[name].is_valid(value):
        raise StructureError("INVALID_REQUEST")


def load_capacity(path: Path) -> dict:
    """Explicit host configuration, never guessed from a request or defaulted."""
    try:
        policy = decode_request(path.read_bytes())
        values = [
            policy["owner"][key]
            for key in (
                "container_max_utf8_bytes",
                "objects_max",
                "versions_per_object_max",
                "committed_operations_max",
                "version_record_max_utf8_bytes",
                "write_request_max_utf8_bytes",
                "write_response_max_utf8_bytes",
                "business_items_per_version_max",
            )
        ]
        values += [
            policy["read"][key]
            for key in (
                "max_input_refs",
                "max_returned_business_items",
                "max_response_bytes",
            )
        ]
        values += [
            policy["max_new_id_mappings_per_operation"],
            policy["grant_max_lifetime_seconds"],
        ]
        _require(all(type(x) is int and x > 0 for x in values))
        return policy
    except (OSError, KeyError, StructureError) as exc:
        raise StructureError("CAPACITY_POLICY_UNAVAILABLE") from exc


def business_items(content: dict) -> int:
    return 1 + sum(
        len(content[key]) for key in ("fact_items", "materials", "presentation_items")
    )


def validate_native(ref: dict) -> None:
    """Only per-source constraints copied from the approved exact read scope."""
    validate_shape("NativeSourceRef", ref)
    item = ref["native_ref"]
    if ref["ref_kind"] == "LEDGER_SOURCE_ITEM":
        kind = item["source_kind"]
        ledger = item["logical_ledger_name"]
        compiler, basis = item["compiler_version"], item["input_basis_sha256"]
        _require(
            (compiler is not None and basis is not None)
            if kind == "projection"
            else (compiler is None and basis is None)
        )
        _require(
            ledger is None
            if kind == "directory_capability_snapshot"
            else ledger is not None
        )
        _require(kind != "chapter_revision" or ledger == "章节账")
    # C11/C10 identities are preserved by their copied schema. Existence, source
    # bytes and authorization remain an actual source-path precondition, not a
    # conclusion from schema or a substitute "current" lookup.


def validate_content(content: dict, self_ref: dict | None = None) -> None:
    validate_shape("StructureContent", content)
    indexes = {}
    for array, (key, *_rest) in _LOCAL.items():
        ids = [x[key] for x in content[array]]
        _require(len(ids) == len(set(ids)))
        indexes[array] = {x[key]: x for x in content[array]}
    facts, materials, bindings = (
        indexes[k] for k in ("fact_items", "materials", "source_bindings")
    )
    selected = content["selected_facts"]
    _require(
        [x["seq"] for x in selected] == list(range(1, len(selected) + 1)),
        "SEQ_NOT_TOTAL_ORDER",
    )
    _require(len({x["item_ref"] for x in selected}) == len(selected))
    _require(all(x["item_ref"] in facts for x in selected))
    for item in materials.values():
        _require(raw_digest(item["raw_content"]) == item["raw_content_sha256"])
    for item in facts.values():
        _require(
            bool(
                item["source_refs"]
                or item["material_refs"]
                or item["source_binding_refs"]
            )
        )
        _require(all(ref in materials for ref in item["material_refs"]))
        _require(all(ref in bindings for ref in item["source_binding_refs"]))
        for ref in item["source_refs"]:
            validate_native(ref)
    for item in content["presentation_items"]:
        _require(all(ref in facts for ref in item["member_refs"]))
        _require(all(ref in materials for ref in item["material_refs"]))
        _require(all(ref in bindings for ref in item["source_binding_refs"]))
    for ref in content["basis_refs"]:
        validate_native(ref)
    for binding in bindings.values():
        _require(all(ref in materials for ref in binding["material_refs"]))
        if binding["resolution_status"] == "UNRESOLVED":
            _require(
                bool(binding["material_refs"]) and bool(binding["unresolved_reasons"])
            )
        if binding["source_ref"] is not None:
            validate_native(binding["source_ref"])
        details = binding["details"]
        kind = binding["source_kind"]
        if kind == "AUTHOR_DECLARATION":
            _require(details["statement_material_ref"] in materials)
            actor = details["author_ref"]
            if actor is not None:
                _require(actor["actor_kind"] == "AUTHOR")
            for span in details["accepted_span_refs"]:
                _require(span["material_ref"] in materials)
                text = materials[span["material_ref"]]["raw_content"]
                _require(0 <= span["start"] < span["end"] <= len(text))
                _require(
                    raw_digest(text[span["start"] : span["end"]])
                    == span["slice_sha256"]
                )
        elif kind == "SYSTEM_PROPOSAL":
            _require(details["candidate_material_ref"] in materials)
            _require(
                details["candidate_material_sha256"]
                == materials[details["candidate_material_ref"]]["raw_content_sha256"]
            )
            for ref in details["input_refs"]:
                validate_native(ref)
        elif kind == "CHAPTER_LOCAL_DELTA":
            source = details["structure_revision_ref"]
            if source is not None and self_ref is not None:
                _require(
                    any(
                        source[key] != self_ref[key]
                        for key in (
                            "project_id",
                            "branch_id",
                            "owner",
                            "object_type",
                            "id",
                            "rev",
                        )
                    )
                )
        elif kind == "PROSE_EXTRACTION":
            anchor, revision = details["anchor_ref"], details["chapter_revision_ref"]
            if anchor is not None:
                _require(anchor["start"] < anchor["end"])
                if revision is not None:
                    _require(all(anchor[k] == revision[k] for k in revision))


def new_id(prefix: str, occupied: set[str]) -> str:
    try:
        for _ in range(8):
            candidate = prefix + "_" + secrets.token_hex(16)
            if candidate not in occupied:
                occupied.add(candidate)
                return candidate
    except OSError as exc:
        raise StructureError("ID_ALLOCATION_FAILED") from exc
    raise StructureError("ID_ALLOCATION_FAILED")


def resolve_local_ids(
    content: dict,
    scope: str,
    history: list[dict],
    object_placeholder: str | None,
    occupied: set[str],
    max_mappings: int,
) -> tuple[dict, list[dict]]:
    validate_shape("StructureContentInput", content)
    known = {array: set() for array in _LOCAL}
    for old in history:
        for array, (key, *_rest) in _LOCAL.items():
            known[array].update(x[key] for x in old["structure_content"][array])
    mapping = {}
    kinds = {}

    def define(value: str, prefix: str, kind: str, existing: set[str]):
        if value.startswith("NEW:"):
            _require(value.split(":")[1] == scope and value not in mapping)
            mapping[value] = new_id(prefix, occupied)
            kinds[value] = kind
        else:
            _require(object_placeholder is None and value in existing)

    if object_placeholder is not None:
        validate_shape("NewPlaceholder", object_placeholder)
        define(object_placeholder, "cs", "STRUCTURE_OBJECT", set())
    for array, (key, prefix, kind, _typ) in _LOCAL.items():
        ids = [item[key] for item in content[array]]
        _require(len(ids) == len(set(ids)))
        for item in content[array]:
            define(item[key], prefix, kind, known[array])
    _require(len(mapping) <= max_mappings, "CAPACITY_EXCEEDED")
    expected_kind = {typ: kind for _, _, kind, typ in _LOCAL.values()}

    def transform(value, shape):
        if "$ref" in shape:
            name = shape["$ref"].rsplit("/", 1)[1]
            if name in expected_kind:
                if value.startswith("NEW:"):
                    _require(value in mapping and kinds[value] == expected_kind[name])
                    return mapping[value]
                return value
            if name == "NativeSourceRef":
                return deepcopy(value)
            return transform(value, SCHEMA["$defs"][name])
        for branch_key in ("oneOf", "anyOf"):
            if branch_key in shape:
                for branch in shape[branch_key]:
                    validator = Draft202012Validator(
                        {**branch, "$defs": SCHEMA["$defs"]}
                    )
                    if validator.is_valid(value):
                        return transform(value, branch)
                raise StructureError("INVALID_REQUEST")
        if shape.get("type") == "object":
            return {
                k: transform(v, shape.get("properties", {}).get(k, {}))
                for k, v in value.items()
            }
        if shape.get("type") == "array":
            return [transform(v, shape.get("items", {})) for v in value]
        return deepcopy(value)

    resolved = transform(content, SCHEMA["$defs"]["StructureContentInput"])
    validate_content(resolved)
    rows = [
        {"placeholder": p, "local_kind": kinds[p], "resolved_id": mapping[p]}
        for p in sorted(mapping)
    ]
    return resolved, rows


def version_digest(ref: dict, content: dict) -> str:
    identity = {
        k: ref[k]
        for k in ("project_id", "branch_id", "owner", "object_type", "id", "rev")
    }
    return digest({"identity": identity, "structure_content": content})
