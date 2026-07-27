from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROUTE_REQUEST_SCHEMA = "v02-r2-route-request.v1"
ROUTE_ANSWER_SCHEMA = "v02-r2-route-answer.v1"
SOURCE_IDENTITY_SCHEMA = "v02-r2-source-identity.v1"
ROUTE_WORKSPACE_MANIFEST_SCHEMA = "v02-r2-route-workspace-manifest.v1"
TERMINAL_FREEZE_SCHEMA = "v02-r2-terminal-freeze-artifacts.v1"
TERMINAL_PARENT_MANIFEST_SCHEMA = "v02-r2-terminal-parent-manifest.v1"
LEDGER_BUNDLE_SCHEMA = "v02-r2-ledger-bundle.v1"
LEDGER_ADJUDICATION_SCHEMA = "v02-r2-ledger-adjudication.v1"
ADJUDICATOR_TICKET_SCHEMA = "v02-r2-adjudicator-ticket.v1"
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUEST_HEAD_PATTERN = re.compile(r"^RH-[A-Z0-9][A-Z0-9._-]*$")
FORBIDDEN_ROUTE_PATH_PARTS = {"gold", "lockbox", "scoring_lockbox"}
FORBIDDEN_ROUTE_TEXT = (
    "config/gold",
    "scoring_lockbox",
    "gold_head_id",
    "required_heads",
    "source_id_groups",
    "semantic_truth_status",
)
WORKSPACE_SINGLETON_ARTIFACTS = {
    "question_set.json": "QUESTION_SET",
}
TERMINAL_SINGLETON_ARTIFACT_TYPES = {
    "QUESTION_SET",
    "GOLD_LOCKBOX",
    "SCORER",
    "MODEL_WORKSPACE_MANIFEST",
    "ADJUDICATOR_TICKET_REGISTRY",
    "RETRIEVAL_POLICY",
    "PROMPT",
    "MODEL_IDENTITY_RECEIPT",
    "RETRY_POLICY",
}


class R2HardeningError(ValueError):
    """R2 开发硬化候选的拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_PATTERN.fullmatch(value))


def _require_hash(value: Any, *, field: str) -> str:
    if not _is_hash(value):
        raise R2HardeningError(f"HASH_INVALID:{field}")
    return value


def _require_nonnegative_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise R2HardeningError(f"NONNEGATIVE_INTEGER_REQUIRED:{field}")
    return value


def _require_nonempty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise R2HardeningError(f"NONEMPTY_STRING_REQUIRED:{field}")
    return value


def _require_string_list(
    value: Any,
    *,
    field: str,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise R2HardeningError(f"STRING_LIST_REQUIRED:{field}")
    if any(not isinstance(item, str) or not item for item in value):
        raise R2HardeningError(f"STRING_LIST_ITEM_INVALID:{field}")
    if len(value) != len(set(value)):
        raise R2HardeningError(f"STRING_LIST_DUPLICATED:{field}")
    return list(value)


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [
            text
            for key, child in value.items()
            for text in [str(key), *_walk_strings(child)]
        ]
    if isinstance(value, list):
        return [text for child in value for text in _walk_strings(child)]
    return []


def _reject_hidden_material(value: Any, *, scope: str) -> None:
    hits: list[str] = []
    for text in _walk_strings(value):
        lowered = text.lower()
        if text.startswith("Z74B-"):
            hits.append(text)
        for fragment in FORBIDDEN_ROUTE_TEXT:
            if fragment.lower() in lowered:
                hits.append(fragment)
    if hits:
        raise R2HardeningError(f"HIDDEN_MATERIAL_FORBIDDEN:{scope}:{sorted(set(hits))}")


def _safe_relative_path(value: Any, *, field: str) -> Path:
    text = _require_nonempty_string(value, field=field)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise R2HardeningError(f"RELATIVE_PATH_REQUIRED:{field}")
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & FORBIDDEN_ROUTE_PATH_PARTS:
        raise R2HardeningError(f"FORBIDDEN_ROUTE_PATH:{field}:{text}")
    return path


def validate_source_identity(
    receipt: Mapping[str, Any],
    *,
    expected_source_id: str,
    expected_chapter: int,
    source_text: str,
    legacy_catalog_bytes: bytes,
    catalog_payload_bytes: bytes,
) -> dict[str, Any]:
    required = {
        "schema_version",
        "source_id",
        "chapter",
        "source_body_sha256",
        "legacy_catalog_sha256",
        "catalog_payload_sha256",
    }
    if set(receipt) != required:
        raise R2HardeningError("SOURCE_IDENTITY_FIELDS_INVALID")
    if receipt["schema_version"] != SOURCE_IDENTITY_SCHEMA:
        raise R2HardeningError("SOURCE_IDENTITY_SCHEMA_INVALID")
    if receipt["source_id"] != expected_source_id:
        raise R2HardeningError("SOURCE_IDENTITY_SOURCE_ID_MISMATCH")
    if receipt["chapter"] != expected_chapter:
        raise R2HardeningError("SOURCE_IDENTITY_CHAPTER_MISMATCH")
    if receipt["source_body_sha256"] != sha256_bytes(source_text.encode("utf-8")):
        raise R2HardeningError("SOURCE_IDENTITY_BODY_SHA_MISMATCH")
    if receipt["legacy_catalog_sha256"] != sha256_bytes(legacy_catalog_bytes):
        raise R2HardeningError("SOURCE_IDENTITY_LEGACY_SHA_MISMATCH")
    if receipt["catalog_payload_sha256"] != sha256_bytes(catalog_payload_bytes):
        raise R2HardeningError("SOURCE_IDENTITY_CATALOG_PAYLOAD_SHA_MISMATCH")
    return {
        "status": "PASS",
        "source_id": expected_source_id,
        "chapter": expected_chapter,
        "source_body_sha256": receipt["source_body_sha256"],
        "legacy_catalog_sha256": receipt["legacy_catalog_sha256"],
        "catalog_payload_sha256": receipt["catalog_payload_sha256"],
    }


def validate_route_request(request: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "run_id",
        "route_id",
        "question_id",
        "request_heads",
        "evidence_window_source_ids",
        "source_catalog_receipt_sha256",
    }
    if set(request) != required:
        raise R2HardeningError("ROUTE_REQUEST_FIELDS_INVALID")
    if request["schema_version"] != ROUTE_REQUEST_SCHEMA:
        raise R2HardeningError("ROUTE_REQUEST_SCHEMA_INVALID")
    for field in ("run_id", "route_id", "question_id"):
        _require_nonempty_string(request[field], field=field)
    _require_hash(
        request["source_catalog_receipt_sha256"],
        field="source_catalog_receipt_sha256",
    )
    evidence_window = _require_string_list(
        request["evidence_window_source_ids"],
        field="evidence_window_source_ids",
    )
    heads = request["request_heads"]
    if not isinstance(heads, list) or not heads:
        raise R2HardeningError("REQUEST_HEADS_REQUIRED")
    head_ids: list[str] = []
    for index, head in enumerate(heads):
        if not isinstance(head, Mapping) or set(head) != {
            "request_head_id",
            "question_span",
            "query_terms",
        }:
            raise R2HardeningError(f"REQUEST_HEAD_FIELDS_INVALID:{index}")
        head_id = _require_nonempty_string(
            head["request_head_id"],
            field=f"request_heads[{index}].request_head_id",
        )
        if not REQUEST_HEAD_PATTERN.fullmatch(head_id):
            raise R2HardeningError(f"REQUEST_HEAD_NAMESPACE_INVALID:{head_id}")
        head_ids.append(head_id)
        _require_nonempty_string(
            head["question_span"],
            field=f"request_heads[{index}].question_span",
        )
        _require_string_list(
            head["query_terms"],
            field=f"request_heads[{index}].query_terms",
        )
    if len(head_ids) != len(set(head_ids)):
        raise R2HardeningError("REQUEST_HEAD_ID_DUPLICATED")
    _reject_hidden_material(request, scope="route_request")
    return {
        "status": "PASS",
        "request_head_count": len(head_ids),
        "evidence_window_source_count": len(evidence_window),
    }


def validate_route_answer(
    answer: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    validate_route_request(request)
    required = {
        "schema_version",
        "run_id",
        "route_id",
        "question_id",
        "status",
        "claims",
        "abstention_reason",
    }
    if set(answer) != required:
        raise R2HardeningError("ROUTE_ANSWER_FIELDS_INVALID")
    if answer["schema_version"] != ROUTE_ANSWER_SCHEMA:
        raise R2HardeningError("ROUTE_ANSWER_SCHEMA_INVALID")
    for field in ("run_id", "route_id", "question_id"):
        if answer[field] != request[field]:
            raise R2HardeningError(f"ROUTE_ANSWER_BINDING_MISMATCH:{field}")
    if answer["status"] not in {"ANSWER", "PARTIAL", "ABSTAIN"}:
        raise R2HardeningError("ROUTE_ANSWER_STATUS_INVALID")
    claims = answer["claims"]
    if not isinstance(claims, list):
        raise R2HardeningError("ROUTE_ANSWER_CLAIMS_NOT_LIST")
    if answer["status"] == "ABSTAIN":
        if claims:
            raise R2HardeningError("ROUTE_ABSTAIN_WITH_CLAIMS")
        _require_nonempty_string(
            answer["abstention_reason"],
            field="abstention_reason",
        )
    else:
        if not claims:
            raise R2HardeningError("ROUTE_ANSWER_WITHOUT_CLAIMS")
        if answer["abstention_reason"] is not None:
            raise R2HardeningError("ROUTE_ANSWER_WITH_ABSTENTION_REASON")

    allowed_heads = {
        head["request_head_id"] for head in request["request_heads"]
    }
    allowed_sources = set(request["evidence_window_source_ids"])
    claim_ids: list[str] = []
    cited_sources: set[str] = set()
    claimed_heads: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, Mapping) or set(claim) != {
            "claim_id",
            "request_head_ids",
            "statement",
            "source_ids",
        }:
            raise R2HardeningError(f"ROUTE_CLAIM_FIELDS_INVALID:{index}")
        claim_id = _require_nonempty_string(
            claim["claim_id"],
            field=f"claims[{index}].claim_id",
        )
        claim_ids.append(claim_id)
        _require_nonempty_string(
            claim["statement"],
            field=f"claims[{index}].statement",
        )
        head_ids = set(
            _require_string_list(
                claim["request_head_ids"],
                field=f"claims[{index}].request_head_ids",
            )
        )
        source_ids = set(
            _require_string_list(
                claim["source_ids"],
                field=f"claims[{index}].source_ids",
            )
        )
        if not head_ids <= allowed_heads:
            raise R2HardeningError(
                f"ROUTE_ANSWER_REQUEST_HEAD_UNAUTHORIZED:{sorted(head_ids - allowed_heads)}"
            )
        if not source_ids <= allowed_sources:
            raise R2HardeningError(
                f"ROUTE_ANSWER_SOURCE_OUTSIDE_WINDOW:{sorted(source_ids - allowed_sources)}"
            )
        cited_sources.update(source_ids)
        claimed_heads.update(head_ids)
    if len(claim_ids) != len(set(claim_ids)):
        raise R2HardeningError("ROUTE_CLAIM_ID_DUPLICATED")
    if answer["status"] == "ANSWER" and claimed_heads != allowed_heads:
        raise R2HardeningError(
            f"ROUTE_ANSWER_HEAD_COVERAGE_INCOMPLETE:{sorted(allowed_heads - claimed_heads)}"
        )
    _reject_hidden_material(answer, scope="route_answer")
    return {
        "status": "PASS",
        "claim_count": len(claims),
        "cited_source_count": len(cited_sources),
    }


def evidence_groups_satisfied(
    *,
    cited_source_ids: Sequence[str],
    source_id_groups: Sequence[Sequence[str]],
) -> bool:
    cited = set(
        _require_string_list(
            list(cited_source_ids),
            field="cited_source_ids",
            allow_empty=True,
        )
    )
    if not isinstance(source_id_groups, Sequence) or not source_id_groups:
        raise R2HardeningError("SOURCE_ID_GROUPS_REQUIRED")
    normalized_groups = [
        set(
            _require_string_list(
                list(group),
                field=f"source_id_groups[{index}]",
            )
        )
        for index, group in enumerate(source_id_groups)
    ]
    return all(bool(cited & group) for group in normalized_groups)


def verify_route_workspace(
    workspace: Path,
    *,
    preregistered_manifest_path: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    if workspace.is_symlink() or preregistered_manifest_path.is_symlink():
        raise R2HardeningError("ROUTE_WORKSPACE_SYMLINK_FORBIDDEN")
    if not workspace.is_dir():
        raise R2HardeningError("ROUTE_WORKSPACE_MISSING")
    if not preregistered_manifest_path.is_file():
        raise R2HardeningError("PREREGISTERED_MANIFEST_MISSING")
    _require_hash(expected_manifest_sha256, field="expected_manifest_sha256")
    if sha256_file(preregistered_manifest_path) != expected_manifest_sha256:
        raise R2HardeningError("PREREGISTERED_MANIFEST_SHA_MISMATCH")
    manifest = json.loads(preregistered_manifest_path.read_text(encoding="utf-8"))
    if set(manifest) != {
        "schema_version",
        "issuer_type",
        "sealed_before_run",
        "files",
    }:
        raise R2HardeningError("ROUTE_WORKSPACE_MANIFEST_FIELDS_INVALID")
    if manifest["schema_version"] != ROUTE_WORKSPACE_MANIFEST_SCHEMA:
        raise R2HardeningError("ROUTE_WORKSPACE_MANIFEST_SCHEMA_INVALID")
    if manifest["issuer_type"] not in {
        "LOCAL_PREREGISTERED_CANDIDATE",
        "EXTERNAL_PREREGISTERED",
    }:
        raise R2HardeningError("ROUTE_WORKSPACE_MANIFEST_ISSUER_UNTRUSTED")
    if manifest["sealed_before_run"] is not True:
        raise R2HardeningError("ROUTE_WORKSPACE_MANIFEST_NOT_PRESEALED")

    root = workspace.resolve()
    actual_files: dict[str, Path] = {}
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            raise R2HardeningError(f"ROUTE_WORKSPACE_SYMLINK_FORBIDDEN:{relative}")
        if not path.resolve().is_relative_to(root):
            raise R2HardeningError(f"ROUTE_WORKSPACE_PATH_ESCAPE:{relative}")
        if path.is_file():
            actual_files[relative] = path

    records = manifest["files"]
    if not isinstance(records, list) or not records:
        raise R2HardeningError("ROUTE_WORKSPACE_MANIFEST_FILES_REQUIRED")
    expected_files: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or set(record) != {
            "path",
            "artifact_type",
            "bytes",
            "sha256",
        }:
            raise R2HardeningError(f"ROUTE_WORKSPACE_FILE_RECORD_INVALID:{index}")
        relative = _safe_relative_path(
            record["path"],
            field=f"files[{index}].path",
        ).as_posix()
        if relative in expected_files:
            raise R2HardeningError(f"ROUTE_WORKSPACE_FILE_DUPLICATED:{relative}")
        _require_nonempty_string(
            record["artifact_type"],
            field=f"files[{index}].artifact_type",
        )
        _require_nonnegative_int(
            record["bytes"],
            field=f"files[{index}].bytes",
        )
        _require_hash(record["sha256"], field=f"files[{index}].sha256")
        expected_files[relative] = record
    if set(actual_files) != set(expected_files):
        raise R2HardeningError("ROUTE_WORKSPACE_FILE_SET_MISMATCH")

    question_records = [
        (relative, record)
        for relative, record in expected_files.items()
        if record["artifact_type"] == "QUESTION_SET"
    ]
    catalog_records = [
        (relative, record)
        for relative, record in expected_files.items()
        if record["artifact_type"] == "SOURCE_CATALOG"
    ]
    if question_records != [("question_set.json", expected_files.get("question_set.json"))]:
        raise R2HardeningError("ROUTE_WORKSPACE_QUESTION_SET_CONTRACT_INVALID")
    expected_catalog_paths = {
        relative
        for relative in expected_files
        if relative.startswith("source_catalog_v2/") and relative.endswith(".json")
    }
    if (
        len(catalog_records) != 3
        or {relative for relative, _ in catalog_records} != expected_catalog_paths
        or len(expected_files) != 4
    ):
        raise R2HardeningError("ROUTE_WORKSPACE_CATALOG_CONTRACT_INVALID")

    forbidden_hits: list[str] = []
    for relative, path in actual_files.items():
        record = expected_files[relative]
        if path.stat().st_size != record["bytes"]:
            raise R2HardeningError(f"ROUTE_WORKSPACE_FILE_SIZE_MISMATCH:{relative}")
        if sha256_file(path) != record["sha256"]:
            raise R2HardeningError(f"ROUTE_WORKSPACE_FILE_SHA_MISMATCH:{relative}")
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="ignore").lower()
        for fragment in FORBIDDEN_ROUTE_TEXT:
            if fragment.lower() in text:
                forbidden_hits.append(f"{relative}:{fragment}")
        try:
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise R2HardeningError(
                f"ROUTE_WORKSPACE_JSON_INVALID:{relative}"
            ) from exc
        _reject_hidden_material(parsed, scope=f"workspace:{relative}")
    if forbidden_hits:
        raise R2HardeningError(
            f"ROUTE_WORKSPACE_HIDDEN_MATERIAL_LEAK:{sorted(forbidden_hits)}"
        )
    return {
        "status": "PASS",
        "file_count": len(actual_files),
        "manifest_sha256": expected_manifest_sha256,
        "all_file_byte_scan": True,
        "issuer_type": manifest["issuer_type"],
        "external_signature_verified": False,
        "model_run_allowed": False,
        "blocking_reason": "EXTERNAL_TRUST_ROOT_NOT_ATTACHED",
    }


def require_model_execution_allowed(
    *,
    workspace_receipt: Mapping[str, Any],
    terminal_receipt: Mapping[str, Any],
) -> None:
    if workspace_receipt.get("model_run_allowed") is not True:
        raise R2HardeningError("MODEL_EXECUTION_BLOCKED_BY_WORKSPACE_TRUST")
    if terminal_receipt.get("terminal_run_allowed") is not True:
        raise R2HardeningError("MODEL_EXECUTION_BLOCKED_BY_TERMINAL_TRUST")


def _verify_bound_file(
    *,
    artifact_root: Path,
    relative_value: Any,
    expected_sha256: Any,
    field: str,
) -> Path:
    relative = _safe_relative_path(relative_value, field=f"{field}_path")
    path = artifact_root / relative
    root = artifact_root.resolve()
    if path.is_symlink() or not path.is_file():
        raise R2HardeningError(f"LEDGER_BOUND_FILE_MISSING:{field}")
    if not path.resolve().is_relative_to(root):
        raise R2HardeningError(f"LEDGER_BOUND_FILE_PATH_ESCAPE:{field}")
    _require_hash(expected_sha256, field=f"{field}_sha256")
    if sha256_file(path) != expected_sha256:
        raise R2HardeningError(f"LEDGER_BOUND_FILE_SHA_MISMATCH:{field}")
    return path


def _load_bound_json(path: Path, *, field: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise R2HardeningError(f"LEDGER_BOUND_JSON_INVALID:{field}") from exc
    if not isinstance(value, Mapping):
        raise R2HardeningError(f"LEDGER_BOUND_JSON_NOT_OBJECT:{field}")
    return value


def validate_ledger_bundle(
    bundle: Mapping[str, Any],
    *,
    artifact_root: Path,
) -> dict[str, Any]:
    if set(bundle) != {
        "schema_version",
        "run_id",
        "route_id",
        "question_id",
        "scoring_executor_id",
        "retrieval",
        "answer",
        "support",
    }:
        raise R2HardeningError("LEDGER_BUNDLE_FIELDS_INVALID")
    if bundle["schema_version"] != LEDGER_BUNDLE_SCHEMA:
        raise R2HardeningError("LEDGER_BUNDLE_SCHEMA_INVALID")
    bindings = {
        field: _require_nonempty_string(bundle[field], field=field)
        for field in ("run_id", "route_id", "question_id")
    }
    scoring_executor_id = _require_nonempty_string(
        bundle["scoring_executor_id"],
        field="scoring_executor_id",
    )
    retrieval = bundle["retrieval"]
    answer = bundle["answer"]
    support = bundle["support"]
    for name, record in (
        ("retrieval", retrieval),
        ("answer", answer),
        ("support", support),
    ):
        if not isinstance(record, Mapping):
            raise R2HardeningError(f"LEDGER_RECORD_INVALID:{name}")
        for field, expected in bindings.items():
            if record.get(field) != expected:
                raise R2HardeningError(f"LEDGER_BINDING_MISMATCH:{name}:{field}")

    retrieval_fields = {
        "run_id",
        "route_id",
        "question_id",
        "route_manifest_path",
        "route_manifest_sha256",
        "plan_path",
        "plan_sha256",
        "index_payload_path",
        "index_payload_sha256",
        "ranked_windows",
        "candidate_chars",
        "elapsed_ms",
    }
    answer_fields = {
        "run_id",
        "route_id",
        "question_id",
        "request_path",
        "request_sha256",
        "raw_response_path",
        "raw_response_sha256",
        "answer_payload_path",
        "answer_payload_sha256",
        "source_ids_used",
        "answer_executor_id",
        "usage",
    }
    support_fields = {
        "run_id",
        "route_id",
        "question_id",
        "claim_id",
        "source_ids",
        "adjudicator_ticket_id",
        "ticket_receipt_path",
        "adjudicator_ticket_receipt_sha256",
        "adjudication_payload_path",
        "adjudication_payload_sha256",
    }
    for name, record, expected_fields in (
        ("retrieval", retrieval, retrieval_fields),
        ("answer", answer, answer_fields),
        ("support", support, support_fields),
    ):
        if set(record) != expected_fields:
            raise R2HardeningError(f"LEDGER_RECORD_FIELDS_INVALID:{name}")

    bound_files = (
        (
            retrieval["route_manifest_path"],
            retrieval["route_manifest_sha256"],
            "route_manifest",
        ),
        (retrieval["plan_path"], retrieval["plan_sha256"], "plan"),
        (
            retrieval["index_payload_path"],
            retrieval["index_payload_sha256"],
            "index_payload",
        ),
        (answer["request_path"], answer["request_sha256"], "request"),
        (
            answer["raw_response_path"],
            answer["raw_response_sha256"],
            "raw_response",
        ),
        (
            answer["answer_payload_path"],
            answer["answer_payload_sha256"],
            "answer_payload",
        ),
        (
            support["ticket_receipt_path"],
            support["adjudicator_ticket_receipt_sha256"],
            "ticket_receipt",
        ),
        (
            support["adjudication_payload_path"],
            support["adjudication_payload_sha256"],
            "adjudication_payload",
        ),
    )
    bound_paths: dict[str, Path] = {}
    for relative, sha256, field in bound_files:
        bound_paths[field] = _verify_bound_file(
            artifact_root=artifact_root,
            relative_value=relative,
            expected_sha256=sha256,
            field=field,
        )

    request_payload = _load_bound_json(bound_paths["request"], field="request")
    answer_payload = _load_bound_json(
        bound_paths["answer_payload"],
        field="answer_payload",
    )
    ticket_receipt = _load_bound_json(
        bound_paths["ticket_receipt"],
        field="ticket_receipt",
    )
    adjudication_payload = _load_bound_json(
        bound_paths["adjudication_payload"],
        field="adjudication_payload",
    )
    validate_route_request(request_payload)
    validate_route_answer(answer_payload, request=request_payload)
    for field, expected in bindings.items():
        if request_payload.get(field) != expected:
            raise R2HardeningError(f"LEDGER_REQUEST_BINDING_MISMATCH:{field}")
        if answer_payload.get(field) != expected:
            raise R2HardeningError(f"LEDGER_ANSWER_PAYLOAD_BINDING_MISMATCH:{field}")

    for field in (
        "route_manifest_sha256",
        "plan_sha256",
        "index_payload_sha256",
    ):
        _require_hash(retrieval.get(field), field=f"retrieval.{field}")
    for field in ("candidate_chars", "elapsed_ms"):
        _require_nonnegative_int(retrieval.get(field), field=f"retrieval.{field}")
    ranked_windows = retrieval.get("ranked_windows")
    if not isinstance(ranked_windows, list):
        raise R2HardeningError("RETRIEVAL_RANKED_WINDOWS_NOT_LIST")
    retrieval_sources: set[str] = set()
    ranks: list[int] = []
    for index, window in enumerate(ranked_windows):
        if not isinstance(window, Mapping) or set(window) != {
            "window_id",
            "rank",
            "source_ids",
            "char_count",
        }:
            raise R2HardeningError(f"RETRIEVAL_WINDOW_FIELDS_INVALID:{index}")
        _require_nonempty_string(
            window["window_id"],
            field=f"retrieval.ranked_windows[{index}].window_id",
        )
        ranks.append(
            _require_nonnegative_int(
                window["rank"],
                field=f"retrieval.ranked_windows[{index}].rank",
            )
        )
        _require_nonnegative_int(
            window["char_count"],
            field=f"retrieval.ranked_windows[{index}].char_count",
        )
        retrieval_sources.update(
            _require_string_list(
                window["source_ids"],
                field=f"retrieval.ranked_windows[{index}].source_ids",
            )
        )
    if len(ranks) != len(set(ranks)):
        raise R2HardeningError("RETRIEVAL_WINDOW_RANK_DUPLICATED")

    for field in (
        "request_sha256",
        "raw_response_sha256",
        "answer_payload_sha256",
    ):
        _require_hash(answer.get(field), field=f"answer.{field}")
    answer_sources = set(
        _require_string_list(
            answer.get("source_ids_used"),
            field="answer.source_ids_used",
            allow_empty=True,
        )
    )
    if answer_sources != {
        source_id
        for claim in answer_payload["claims"]
        for source_id in claim["source_ids"]
    }:
        raise R2HardeningError("ANSWER_LEDGER_SOURCE_IDS_MISMATCH")
    answer_executor_id = _require_nonempty_string(
        answer.get("answer_executor_id"),
        field="answer.answer_executor_id",
    )
    if not answer_sources <= retrieval_sources:
        raise R2HardeningError(
            f"ANSWER_SOURCE_OUTSIDE_RETRIEVAL:{sorted(answer_sources - retrieval_sources)}"
        )
    usage = answer.get("usage")
    if not isinstance(usage, Mapping) or set(usage) != {
        "input_tokens",
        "output_tokens",
    }:
        raise R2HardeningError("ANSWER_USAGE_FIELDS_INVALID")
    for field in ("input_tokens", "output_tokens"):
        _require_nonnegative_int(usage[field], field=f"answer.usage.{field}")

    for field in (
        "adjudicator_ticket_receipt_sha256",
        "adjudication_payload_sha256",
    ):
        _require_hash(support.get(field), field=f"support.{field}")
    _require_nonempty_string(
        support.get("claim_id"),
        field="support.claim_id",
    )
    _require_nonempty_string(
        support.get("adjudicator_ticket_id"),
        field="support.adjudicator_ticket_id",
    )
    support_sources = set(
        _require_string_list(
            support.get("source_ids"),
            field="support.source_ids",
        )
    )
    if not support_sources <= answer_sources:
        raise R2HardeningError(
            f"SUPPORT_SOURCE_OUTSIDE_ANSWER:{sorted(support_sources - answer_sources)}"
        )
    if set(ticket_receipt) != {
        "schema_version",
        "ticket_id",
        "issuer",
        "adjudicator_executor_id",
        "scoring_executor_id",
        "independence_basis",
    }:
        raise R2HardeningError("ADJUDICATOR_TICKET_RECEIPT_FIELDS_INVALID")
    if ticket_receipt["schema_version"] != ADJUDICATOR_TICKET_SCHEMA:
        raise R2HardeningError("ADJUDICATOR_TICKET_SCHEMA_INVALID")
    if ticket_receipt["ticket_id"] != support["adjudicator_ticket_id"]:
        raise R2HardeningError("ADJUDICATOR_TICKET_ID_MISMATCH")
    if ticket_receipt["scoring_executor_id"] != scoring_executor_id:
        raise R2HardeningError("ADJUDICATOR_TICKET_SCORER_BINDING_MISMATCH")
    adjudicator_executor_id = _require_nonempty_string(
        ticket_receipt["adjudicator_executor_id"],
        field="ticket_receipt.adjudicator_executor_id",
    )
    _require_nonempty_string(
        ticket_receipt["issuer"],
        field="ticket_receipt.issuer",
    )
    _require_nonempty_string(
        ticket_receipt["independence_basis"],
        field="ticket_receipt.independence_basis",
    )
    if adjudicator_executor_id in {scoring_executor_id, answer_executor_id}:
        raise R2HardeningError("ADJUDICATOR_EXECUTOR_NOT_INDEPENDENT")

    expected_adjudication_fields = {
        "schema_version",
        "run_id",
        "route_id",
        "question_id",
        "claim_id",
        "answer_payload_sha256",
        "adjudicator_ticket_id",
        "adjudicator_ticket_receipt_sha256",
        "source_ids",
        "evidence_supports",
    }
    if set(adjudication_payload) != expected_adjudication_fields:
        raise R2HardeningError("LEDGER_ADJUDICATION_FIELDS_INVALID")
    if adjudication_payload["schema_version"] != LEDGER_ADJUDICATION_SCHEMA:
        raise R2HardeningError("LEDGER_ADJUDICATION_SCHEMA_INVALID")
    for field, expected in bindings.items():
        if adjudication_payload[field] != expected:
            raise R2HardeningError(f"LEDGER_ADJUDICATION_BINDING_MISMATCH:{field}")
    if adjudication_payload["claim_id"] != support["claim_id"]:
        raise R2HardeningError("LEDGER_ADJUDICATION_CLAIM_MISMATCH")
    if adjudication_payload["answer_payload_sha256"] != answer[
        "answer_payload_sha256"
    ]:
        raise R2HardeningError("LEDGER_ADJUDICATION_ANSWER_SHA_MISMATCH")
    if adjudication_payload["adjudicator_ticket_id"] != support[
        "adjudicator_ticket_id"
    ]:
        raise R2HardeningError("LEDGER_ADJUDICATION_TICKET_MISMATCH")
    if adjudication_payload["adjudicator_ticket_receipt_sha256"] != support[
        "adjudicator_ticket_receipt_sha256"
    ]:
        raise R2HardeningError("LEDGER_ADJUDICATION_TICKET_SHA_MISMATCH")
    if set(adjudication_payload["source_ids"]) != support_sources:
        raise R2HardeningError("LEDGER_ADJUDICATION_SOURCE_IDS_MISMATCH")
    if not isinstance(adjudication_payload["evidence_supports"], bool):
        raise R2HardeningError("LEDGER_ADJUDICATION_EVIDENCE_NOT_BOOL")
    return {
        "status": "PASS",
        "retrieval_source_count": len(retrieval_sources),
        "answer_source_count": len(answer_sources),
        "total_tokens": usage["input_tokens"] + usage["output_tokens"],
        "adjudicator_executor_id": adjudicator_executor_id,
    }


def verify_terminal_freeze_artifacts(
    contract: Mapping[str, Any],
    *,
    artifact_root: Path,
    expected_contract_sha256: str,
) -> dict[str, Any]:
    _require_hash(expected_contract_sha256, field="expected_contract_sha256")
    if sha256_bytes(canonical_bytes(contract)) != expected_contract_sha256:
        raise R2HardeningError("TERMINAL_FREEZE_CONTRACT_SHA_MISMATCH")
    if set(contract) != {
        "schema_version",
        "issuer",
        "signed_at",
        "parent_manifest_path",
        "parent_manifest_sha256",
        "artifacts",
    }:
        raise R2HardeningError("TERMINAL_FREEZE_FIELDS_INVALID")
    if contract["schema_version"] != TERMINAL_FREEZE_SCHEMA:
        raise R2HardeningError("TERMINAL_FREEZE_SCHEMA_INVALID")
    _require_nonempty_string(contract["issuer"], field="issuer")
    _require_nonempty_string(contract["signed_at"], field="signed_at")
    _require_hash(
        contract["parent_manifest_sha256"],
        field="parent_manifest_sha256",
    )
    parent_manifest_relative = _safe_relative_path(
        contract["parent_manifest_path"],
        field="parent_manifest_path",
    )
    parent_manifest_path = artifact_root / parent_manifest_relative
    root = artifact_root.resolve()
    if parent_manifest_path.is_symlink() or not parent_manifest_path.is_file():
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_MISSING")
    if not parent_manifest_path.resolve().is_relative_to(root):
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_PATH_ESCAPE")
    if sha256_file(parent_manifest_path) != contract["parent_manifest_sha256"]:
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_SHA_MISMATCH")
    try:
        parent_manifest = json.loads(parent_manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_JSON_INVALID") from exc
    if not isinstance(parent_manifest, Mapping) or set(parent_manifest) != {
        "schema_version",
        "artifacts",
    }:
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_FIELDS_INVALID")
    if parent_manifest["schema_version"] != TERMINAL_PARENT_MANIFEST_SCHEMA:
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_SCHEMA_INVALID")
    artifacts = contract["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise R2HardeningError("TERMINAL_FREEZE_ARTIFACTS_REQUIRED")
    paths: set[str] = set()
    artifact_types: list[str] = []
    for index, record in enumerate(artifacts):
        if not isinstance(record, Mapping) or set(record) != {
            "artifact_type",
            "relative_path",
            "bytes",
            "sha256",
        }:
            raise R2HardeningError(f"TERMINAL_FREEZE_ARTIFACT_INVALID:{index}")
        relative = _safe_relative_path(
            record["relative_path"],
            field=f"artifacts[{index}].relative_path",
        )
        relative_text = relative.as_posix()
        if relative_text in paths:
            raise R2HardeningError(f"TERMINAL_FREEZE_ARTIFACT_DUPLICATED:{relative_text}")
        paths.add(relative_text)
        _require_nonempty_string(
            record["artifact_type"],
            field=f"artifacts[{index}].artifact_type",
        )
        artifact_types.append(record["artifact_type"])
        _require_nonnegative_int(
            record["bytes"],
            field=f"artifacts[{index}].bytes",
        )
        _require_hash(record["sha256"], field=f"artifacts[{index}].sha256")
        path = artifact_root / relative
        if path.is_symlink() or not path.is_file():
            raise R2HardeningError(
                f"TERMINAL_FREEZE_ARTIFACT_MISSING:{relative_text}"
            )
        if not path.resolve().is_relative_to(root):
            raise R2HardeningError(
                f"TERMINAL_FREEZE_ARTIFACT_PATH_ESCAPE:{relative_text}"
            )
        if path.stat().st_size != record["bytes"]:
            raise R2HardeningError(
                f"TERMINAL_FREEZE_ARTIFACT_SIZE_MISMATCH:{relative_text}"
            )
        if sha256_file(path) != record["sha256"]:
            raise R2HardeningError(
                f"TERMINAL_FREEZE_ARTIFACT_SHA_MISMATCH:{relative_text}"
            )
    if parent_manifest["artifacts"] != artifacts:
        raise R2HardeningError("TERMINAL_PARENT_MANIFEST_ARTIFACTS_MISMATCH")
    singleton_counts = {
        artifact_type: artifact_types.count(artifact_type)
        for artifact_type in TERMINAL_SINGLETON_ARTIFACT_TYPES
    }
    if any(count != 1 for count in singleton_counts.values()):
        raise R2HardeningError("TERMINAL_SINGLETON_ARTIFACT_SET_INVALID")
    if artifact_types.count("ROUTE_MANIFEST") < 1:
        raise R2HardeningError("TERMINAL_ROUTE_MANIFEST_REQUIRED")
    unknown_types = sorted(
        set(artifact_types)
        - TERMINAL_SINGLETON_ARTIFACT_TYPES
        - {"ROUTE_MANIFEST"}
    )
    if unknown_types:
        raise R2HardeningError(
            f"TERMINAL_ARTIFACT_TYPE_UNKNOWN:{unknown_types}"
        )
    return {
        "status": "PASS",
        "artifact_count": len(artifacts),
        "contract_sha256": expected_contract_sha256,
        "external_signature_verified": False,
        "terminal_run_allowed": False,
        "blocking_reason": "EXTERNAL_TRUST_ROOT_NOT_ATTACHED",
    }
