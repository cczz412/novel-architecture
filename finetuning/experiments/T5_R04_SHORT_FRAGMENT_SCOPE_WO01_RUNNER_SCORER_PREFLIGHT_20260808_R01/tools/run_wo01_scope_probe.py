#!/usr/bin/env python3
"""WO-01 专用两消息 runner；默认只允许校验和 TEST_ONLY dry-run。"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from jsonschema import Draft202012Validator

sys.dont_write_bytecode = True


REPO = Path(__file__).resolve().parents[4]
EXP = Path(__file__).resolve().parents[1]
R01 = REPO / "finetuning/experiments/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_PREFLIGHT_20260808_R01"
MODEL = Path("/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f")
M1 = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01"
ADAPTER = M1 / "eval_adapters/c2_full/update_72"
VENDOR = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
SCHEMA = REPO / "finetuning/experiments/T5_R04_P3_C0_SCHEMA_MATERIALIZATION_P4_1_20260808_R01/P3_C0_OUTPUT_STRUCTURAL_SCHEMA.json"
VENDOR_MANIFEST = EXP / "VENDOR_SOURCE_MANIFEST.json"
SCORER = EXP / "tools/score_wo01_scope_probe.py"
SCORING_CONTRACT = EXP / "SCORING_CONTRACT.md"
BOOTSTRAP_CONTRACT = EXP / "BOOTSTRAP_CONTRACT.json"
ADJUDICATION_SCHEMA = EXP / "SEMANTIC_ADJUDICATION_SCHEMA.json"
PREFLIGHT_OUTPUT_MANIFEST = EXP / "OUTPUT_MANIFEST.json"
RUN_AUTHORIZATION_SCHEMA = EXP / "RUN_AUTHORIZATION_SCHEMA.json"

ARMS = ("TARGET_ONLY", "SMALL_HALO", "CURRENT_WINDOW")
CASES_PER_ARM = 24
MAX_OUTPUT_TOKENS = 1024
MIN_FREE_MEMORY_PERCENT = 8
MLX_WIRED_LIMIT_BYTES = 20 * 1024**3
MLX_MEMORY_LIMIT_BYTES = 22 * 1024**3
MLX_CACHE_LIMIT_BYTES = 1 * 1024**3
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
EXPECTED = {
    "r01_manifest": "e4efced726b066002cb91630b77d21ef7a22cf2eb05ef7e4aca59a2482ae694f",
    "target_requests": "05973a07f5edccc034f6bedeb5dd805baf8541f846df4a792a40e652f8e3aca0",
    "small_requests": "123c057aa8d6b72f6523d04a944814d1577245c2f421850640afe71e837275a3",
    "current_requests": "c8c994b756698f652abe7c7be85260bff5142144117ea71f78311e3b22f6f29c",
    "sidecar": "d07111c9ba117576b4ccce7f1a45adb987e18f406c96b5992ef0cd679762cf1c",
    "checkpoint": "321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9",
    "adapter_config": "72df68a7d01b8feae8f92cc0e4f69c832d9ad71886b4f8ea2896a7436d73031e",
    "schema": "7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14",
    "tokenizer_config": "a62ff0a2472a0fa1b8eaabcb57c59b58afa42a22831dc141400b6e0cf2b65ce3",
    "tokenizer_json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "chat_template": "64f85b198065d0fba2a81f37e10ed68161ce2c19a754c7100e67e0ca2ee9c326",
    "model_receipt": "431f5a7e82c46c716ac5419cd59bc4312bbc50292b09f0b3c842ab08b07d8bb6",
    "vendor_manifest": "ff3dd921dbec464e8a992be33f699141dbb72749f7ebdc1816bff30d6ae1c227",
}
REQUEST_PATHS = {
    "TARGET_ONLY": R01 / "sealed_inputs_candidate/TARGET_ONLY_REQUESTS_24.jsonl",
    "SMALL_HALO": R01 / "sealed_inputs_candidate/SMALL_HALO_REQUESTS_24.jsonl",
    "CURRENT_WINDOW": R01 / "sealed_inputs_candidate/CURRENT_WINDOW_REQUESTS_24.jsonl",
}
SIDECAR = R01 / "sealed_inputs_candidate/HIDDEN_REQUEST_SIDECAR_72.jsonl"
RUN_ROOT = REPO / "runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_R01"
RUN_CLAIMS = RUN_ROOT / ".claims"


def assert_safe_path(
    path: Path,
    *,
    root: Path,
    exact: Path | None = None,
    must_exist: bool = False,
) -> Path:
    """Reject lexical escape, resolved escape, and symlinks at every existing level."""
    if not path.is_absolute() or ".." in path.parts:
        raise RuntimeError("RUNTIME_PATH_LEXICALLY_UNSAFE")
    if exact is not None and path != exact:
        raise RuntimeError("RUNTIME_PATH_NOT_FIXED_LOCATION")
    if not root.is_absolute() or ".." in root.parts:
        raise RuntimeError("RUN_ROOT_LEXICALLY_UNSAFE")
    if path != root and root not in path.parents:
        raise RuntimeError("RUNTIME_PATH_OUTSIDE_FIXED_ROOT")
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        if cursor.exists() or cursor.is_symlink():
            if cursor.is_symlink():
                raise RuntimeError(f"RUNTIME_PATH_SYMLINK_FORBIDDEN:{cursor}")
    root_resolved = root.resolve(strict=False)
    resolved = path.resolve(strict=False)
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise RuntimeError("RUNTIME_PATH_RESOLVED_OUTSIDE_FIXED_ROOT")
    if must_exist and not path.exists():
        raise RuntimeError(f"RUNTIME_PATH_MISSING:{path}")
    return path


def prepare_runtime_roots(*, run_root: Path = RUN_ROOT, claims_root: Path = RUN_CLAIMS) -> None:
    assert_safe_path(run_root, root=run_root)
    if run_root.exists() and not run_root.is_dir():
        raise RuntimeError("RUN_ROOT_NOT_DIRECTORY")
    run_root.mkdir(parents=True, exist_ok=True)
    assert_safe_path(run_root, root=run_root, must_exist=True)
    assert_safe_path(claims_root, root=run_root, exact=run_root / ".claims")
    if claims_root.exists() and not claims_root.is_dir():
        raise RuntimeError("RUN_CLAIMS_NOT_DIRECTORY")
    claims_root.mkdir(exist_ok=True)
    assert_safe_path(claims_root, root=run_root, exact=run_root / ".claims", must_exist=True)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def strict_json_loads(payload: bytes | str) -> Any:
    return json.loads(payload, object_pairs_hook=reject_duplicate_keys)


def read_json(path: Path) -> Any:
    return strict_json_loads(path.read_bytes())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [strict_json_loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    with path.open("xb") as handle:
        handle.write(payload)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(stable_json_bytes(row) for row in rows))


def system_free_percent() -> int:
    output = subprocess.run(
        ["memory_pressure", "-Q"],
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", output)
    return int(match.group(1)) if match else -1


def memory_snapshot() -> dict[str, Any]:
    swap = subprocess.run(
        ["sysctl", "-n", "vm.swapusage"],
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    return {
        "system_memory_free_percent": system_free_percent(),
        "swap": swap,
    }


def require_memory_headroom(scope: str) -> dict[str, Any]:
    snapshot = memory_snapshot()
    if snapshot["system_memory_free_percent"] < MIN_FREE_MEMORY_PERCENT:
        raise RuntimeError(
            f"MEMORY_HARD_STOP:{scope}:"
            f"free_percent={snapshot['system_memory_free_percent']}:"
            f"required={MIN_FREE_MEMORY_PERCENT}"
        )
    return snapshot


def verify_model_receipt_members() -> dict[str, Any]:
    """Formal-run gate: bind the receipt, then independently hash all 13 files."""
    receipt_path = MODEL / "MODEL_RECEIPT.json"
    if sha256(receipt_path) != EXPECTED["model_receipt"]:
        raise RuntimeError("MODEL_RECEIPT_SHA_DRIFT")
    receipt = read_json(receipt_path)
    if receipt.get("status") != "COMPLETE_VERIFIED":
        raise RuntimeError("MODEL_RECEIPT_STATUS_INVALID")
    if receipt.get("revision") != MODEL_REVISION:
        raise RuntimeError("MODEL_REVISION_DRIFT")
    files = receipt.get("files")
    if not isinstance(files, list) or len(files) != 13:
        raise RuntimeError("MODEL_RECEIPT_FILE_COUNT_INVALID")
    paths = [row.get("path") for row in files]
    required = {
        "config.json",
        "generation_config.json",
        "model.safetensors.index.json",
        "model-00001-of-00003.safetensors",
        "model-00002-of-00003.safetensors",
        "model-00003-of-00003.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
    }
    if len(set(paths)) != 13 or not required.issubset(paths):
        raise RuntimeError("MODEL_RECEIPT_REQUIRED_MEMBERS_INVALID")
    total_bytes = 0
    verified = []
    for row in files:
        relative = row["path"]
        member = MODEL / relative
        if not member.is_file():
            raise RuntimeError(f"MODEL_MEMBER_MISSING:{relative}")
        actual_bytes = member.stat().st_size
        if actual_bytes != row.get("bytes"):
            raise RuntimeError(f"MODEL_MEMBER_BYTES_DRIFT:{relative}")
        actual_sha = sha256(member)
        if actual_sha != row.get("sha256"):
            raise RuntimeError(f"MODEL_MEMBER_SHA_DRIFT:{relative}")
        total_bytes += actual_bytes
        verified.append(relative)
    if total_bytes != receipt.get("official_total_bytes"):
        raise RuntimeError("MODEL_MEMBER_TOTAL_BYTES_DRIFT")
    return {
        "receipt_sha256": EXPECTED["model_receipt"],
        "revision": MODEL_REVISION,
        "verified_member_count": len(verified),
        "verified_total_bytes": total_bytes,
        "members": verified,
    }


def verify_vendor_sources() -> dict[str, Any]:
    if sha256(VENDOR_MANIFEST) != EXPECTED["vendor_manifest"]:
        raise RuntimeError("VENDOR_MANIFEST_SHA_DRIFT")
    manifest = read_json(VENDOR_MANIFEST)
    if (
        manifest.get("status") != "FROZEN_SOURCE_ONLY_RUNTIME_IDENTITY"
        or manifest.get("mlx_lm_version") != "0.30.7"
        or manifest.get("member_count") != len(manifest.get("members", []))
    ):
        raise RuntimeError("VENDOR_MANIFEST_CONTRACT_INVALID")
    required = {
        "mlx_lm/__init__.py",
        "mlx_lm/_version.py",
        "mlx_lm/utils.py",
        "mlx_lm/generate.py",
        "mlx_lm/sample_utils.py",
    }
    rows = manifest["members"]
    if not required.issubset({row["path"] for row in rows}):
        raise RuntimeError("VENDOR_RUNTIME_IMPORT_SOURCE_MISSING")
    for row in rows:
        member = VENDOR / row["path"]
        if member.is_symlink() or not member.is_file():
            raise RuntimeError(f"VENDOR_MEMBER_MISSING_OR_SYMLINK:{row['path']}")
        if member.stat().st_size != row["bytes"] or sha256(member) != row["sha256"]:
            raise RuntimeError(f"VENDOR_MEMBER_DRIFT:{row['path']}")
    return {
        "manifest_sha256": EXPECTED["vendor_manifest"],
        "tree_digest": manifest["tree_digest"],
        "member_count": manifest["member_count"],
        "mlx_lm_version": manifest["mlx_lm_version"],
        "required_runtime_import_sources": sorted(required),
    }


def current_execution_contract_identity() -> dict[str, Any]:
    required = {
        "scorer_sha256": SCORER,
        "scoring_contract_sha256": SCORING_CONTRACT,
        "bootstrap_contract_sha256": BOOTSTRAP_CONTRACT,
        "semantic_adjudication_schema_sha256": ADJUDICATION_SCHEMA,
        "run_authorization_schema_sha256": RUN_AUTHORIZATION_SCHEMA,
        "output_structural_schema_sha256": SCHEMA,
    }
    for label, path in required.items():
        if not path.is_file():
            raise RuntimeError(f"EXECUTION_CONTRACT_SOURCE_MISSING:{label}")
    if not PREFLIGHT_OUTPUT_MANIFEST.is_file():
        raise RuntimeError("PREFLIGHT_OUTPUT_MANIFEST_NOT_SEALED")
    return {
        "preflight_output_manifest_sha256": sha256(PREFLIGHT_OUTPUT_MANIFEST),
        **{label: sha256(path) for label, path in required.items()},
    }


def freeze_process_identity() -> dict[str, Any]:
    return {
        "runner_sha256": sha256(Path(__file__).resolve()),
        "execution_contract": current_execution_contract_identity(),
        "vendor_identity": verify_vendor_sources(),
    }


def verify_process_identity_unchanged(initial: dict[str, Any]) -> dict[str, Any]:
    observed = freeze_process_identity()
    if observed != initial:
        raise RuntimeError(
            "RUNTIME_CODE_IDENTITY_DRIFT_DURING_RUN:"
            + json.dumps(
                {"initial": initial, "observed": observed},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return observed


def observe_process_identity_for_abort(initial: dict[str, Any]) -> dict[str, Any]:
    """Abort evidence never depends on mutable external ticket bytes or current code."""
    try:
        observed = freeze_process_identity()
        return {"available": True, "identity": observed, "matches_initial": observed == initial}
    except BaseException as error:
        return {
            "available": False,
            "error_type": type(error).__name__,
            "error": str(error),
            "initial_identity_retained": initial,
        }


def verify_frozen_identities() -> dict[str, Any]:
    checks = {
        "r01_manifest": R01 / "OUTPUT_MANIFEST.json",
        "target_requests": REQUEST_PATHS["TARGET_ONLY"],
        "small_requests": REQUEST_PATHS["SMALL_HALO"],
        "current_requests": REQUEST_PATHS["CURRENT_WINDOW"],
        "sidecar": SIDECAR,
        "checkpoint": ADAPTER / "adapters.safetensors",
        "adapter_config": ADAPTER / "adapter_config.json",
        "schema": SCHEMA,
        "tokenizer_config": MODEL / "tokenizer_config.json",
        "tokenizer_json": MODEL / "tokenizer.json",
        "model_receipt": MODEL / "MODEL_RECEIPT.json",
    }
    result: dict[str, Any] = {}
    for identity, path in checks.items():
        if not path.is_file():
            raise RuntimeError(f"FROZEN_SOURCE_MISSING:{identity}:{path}")
        actual = sha256(path)
        if actual != EXPECTED[identity]:
            raise RuntimeError(
                f"FROZEN_SOURCE_SHA_DRIFT:{identity}:expected={EXPECTED[identity]}:actual={actual}"
            )
        result[identity] = {"path": str(path), "sha256": actual, "bytes": path.stat().st_size}

    tokenizer_config = read_json(MODEL / "tokenizer_config.json")
    chat_template = tokenizer_config.get("chat_template")
    if not isinstance(chat_template, str) or text_sha256(chat_template) != EXPECTED["chat_template"]:
        raise RuntimeError("CHAT_TEMPLATE_IDENTITY_DRIFT")
    result["chat_template"] = {
        "source": str(MODEL / "tokenizer_config.json"),
        "sha256": EXPECTED["chat_template"],
    }
    result["vendor"] = verify_vendor_sources()
    return result


def load_execution_plan() -> list[dict[str, Any]]:
    verify_frozen_identities()
    sidecars = read_jsonl(SIDECAR)
    sidecar_index = {(row["arm"], int(row["row_index"])): row for row in sidecars}
    if len(sidecars) != 72 or len(sidecar_index) != 72:
        raise RuntimeError("SIDECAR_NOT_72_UNIQUE_ARM_ROW_INDEX")

    plan: list[dict[str, Any]] = []
    for arm in ARMS:
        requests = read_jsonl(REQUEST_PATHS[arm])
        if len(requests) != CASES_PER_ARM:
            raise RuntimeError(f"REQUEST_COUNT_NOT_24:{arm}:{len(requests)}")
        for row_index, request in enumerate(requests):
            if set(request) != {"messages"} or len(request["messages"]) != 2:
                raise RuntimeError(f"REQUEST_NOT_EXACTLY_TWO_MESSAGES:{arm}:{row_index}")
            if [message.get("role") for message in request["messages"]] != ["system", "user"]:
                raise RuntimeError(f"REQUEST_ROLE_ORDER_INVALID:{arm}:{row_index}")
            sidecar = sidecar_index[(arm, row_index)]
            request_sha = hashlib.sha256(stable_json_bytes(request)).hexdigest()
            if request_sha != sidecar["model_visible_request_sha256"]:
                raise RuntimeError(f"REQUEST_SIDECAR_SHA_MISMATCH:{arm}:{row_index}")
            plan.append(
                {
                    "arm": arm,
                    "row_index": row_index,
                    "case_id": sidecar["case_id"],
                    "request": request,
                    "request_sha256": request_sha,
                    "canonical_row_sha256": sidecar["canonical_row_sha256"],
                    "gold_binding_sha256": sidecar["gold_binding_sha256"],
                    "allowed_evidence_ids": sidecar["allowed_evidence_ids"],
                }
            )
    if len(plan) != 72 or len({(row["arm"], row["case_id"]) for row in plan}) != 72:
        raise RuntimeError("EXECUTION_PLAN_NOT_72_UNIQUE_ARM_CASE")
    return plan


def execution_plan_identity_sha256(plan: list[dict[str, Any]] | None = None) -> str:
    plan = plan or load_execution_plan()
    identity = [
        {
            "sequence_index": index,
            "arm": row["arm"],
            "row_index": row["row_index"],
            "case_id": row["case_id"],
            "request_sha256": row["request_sha256"],
            "gold_binding_sha256": row["gold_binding_sha256"],
        }
        for index, row in enumerate(plan, start=1)
    ]
    return hashlib.sha256(b"".join(stable_json_bytes(row) for row in identity)).hexdigest()


def serialize_messages(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    """The same full-list call is used by TEST_ONLY evidence and the real run path."""
    if len(messages) != 2 or [row.get("role") for row in messages] != ["system", "user"]:
        raise RuntimeError("SERIALIZATION_REQUIRES_EXACT_SYSTEM_USER_MESSAGES")
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


class TestOnlyChatTemplateSerializer:
    """Static spy used only to prove that both message objects reach the serializer."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str:
        if tokenize or not add_generation_prompt:
            raise RuntimeError("TEST_ONLY_SERIALIZER_ARGUMENT_DRIFT")
        self.calls.append(json.loads(json.dumps(messages, ensure_ascii=False)))
        return "".join(
            f"<|{message['role']}|>\n{message['content']}\n" for message in messages
        ) + "<|assistant|>\n"


def build_test_only_serialization_evidence() -> list[dict[str, Any]]:
    plan = load_execution_plan()
    serializer = TestOnlyChatTemplateSerializer()
    evidence = []
    for row in plan:
        prompt = serialize_messages(serializer, row["request"]["messages"])
        captured = serializer.calls[-1]
        evidence.append(
            {
                "fixture_role": "TEST_ONLY_NO_MODEL_NO_TOKENIZER",
                "arm": row["arm"],
                "row_index": row["row_index"],
                "case_id": row["case_id"],
                "request_sha256": row["request_sha256"],
                "message_count_passed_to_serializer": len(captured),
                "roles_passed_to_serializer": [message["role"] for message in captured],
                "system_content_sha256": text_sha256(captured[0]["content"]),
                "user_content_sha256": text_sha256(captured[1]["content"]),
                "serialized_prompt_sha256": text_sha256(prompt),
                "system_content_present_in_serialized_prompt": captured[0]["content"] in prompt,
                "user_content_present_in_serialized_prompt": captured[1]["content"] in prompt,
                "legacy_messages_minus_last_used": False,
            }
        )
    if len(serializer.calls) != 72:
        raise RuntimeError("TEST_ONLY_SERIALIZER_CALL_COUNT_NOT_72")
    return evidence


def validate_authorization_ticket_bytes(
    ticket_bytes: bytes,
    output_dir: Path,
) -> dict[str, Any]:
    ticket = strict_json_loads(ticket_bytes)
    errors = sorted(
        Draft202012Validator(read_json(RUN_AUTHORIZATION_SCHEMA)).iter_errors(ticket),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise RuntimeError(
            "RUN_AUTHORIZATION_SCHEMA_INVALID:"
            + "|".join(error.message for error in errors)
        )
    contract = current_execution_contract_identity()
    vendor = verify_vendor_sources()
    required = {
        "schema_version": "t5-r04-wo01-run-authorization-v1",
        "status": "CZ_EXPLICIT_MODEL_RUN_AUTHORIZATION",
        "model_run_authorized": True,
        "training_authorized": False,
        "api_authorized": False,
        "authorized_request_count": 72,
        "r01_manifest_sha256": EXPECTED["r01_manifest"],
        "checkpoint_sha256": EXPECTED["checkpoint"],
        "schema_sha256": EXPECTED["schema"],
        "chat_template_sha256": EXPECTED["chat_template"],
        "model_receipt_sha256": EXPECTED["model_receipt"],
        "model_revision": MODEL_REVISION,
        "arm_order": list(ARMS),
        "request_plan_sha256": execution_plan_identity_sha256(),
        "runner_sha256": sha256(Path(__file__).resolve()),
        **contract,
        "vendor_manifest_sha256": vendor["manifest_sha256"],
        "vendor_tree_digest": vendor["tree_digest"],
        "mlx_lm_version": vendor["mlx_lm_version"],
    }
    for key, expected in required.items():
        if ticket.get(key) != expected:
            raise RuntimeError(f"RUN_AUTHORIZATION_TICKET_INVALID:{key}")
    if ticket.get("decode") != {
        "sampler": "greedy",
        "temperature": 0.0,
        "max_output_tokens": 1024,
        "retry": 0,
    }:
        raise RuntimeError("RUN_AUTHORIZATION_DECODE_DRIFT")
    if text_sha256(ticket["approval_quote"]) != ticket["approval_quote_sha256"]:
        raise RuntimeError("RUN_AUTHORIZATION_APPROVAL_QUOTE_SHA_DRIFT")
    run_id = ticket.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"WO01-[A-Za-z0-9._-]+", run_id):
        raise RuntimeError("RUN_AUTHORIZATION_RUN_ID_INVALID")
    assert_authorized_output_binding(ticket, output_dir)
    return ticket


def validate_authorization_ticket(path: Path, output_dir: Path) -> dict[str, Any]:
    return validate_authorization_ticket_bytes(path.read_bytes(), output_dir)


def authorization_validation_projection(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS_FULL_RUN_AUTHORIZATION_VALIDATED",
        "schema_version": ticket["schema_version"],
        "run_id": ticket["run_id"],
        "authorized_output_dir": ticket["authorized_output_dir"],
        "authorized_request_count": ticket["authorized_request_count"],
        "arm_order": ticket["arm_order"],
        "request_plan_sha256": ticket["request_plan_sha256"],
        "r01_manifest_sha256": ticket["r01_manifest_sha256"],
        "checkpoint_sha256": ticket["checkpoint_sha256"],
        "schema_sha256": ticket["schema_sha256"],
        "chat_template_sha256": ticket["chat_template_sha256"],
        "model_receipt_sha256": ticket["model_receipt_sha256"],
        "model_revision": ticket["model_revision"],
        "runner_sha256": ticket["runner_sha256"],
        "preflight_output_manifest_sha256": ticket["preflight_output_manifest_sha256"],
        "scorer_sha256": ticket["scorer_sha256"],
        "scoring_contract_sha256": ticket["scoring_contract_sha256"],
        "bootstrap_contract_sha256": ticket["bootstrap_contract_sha256"],
        "semantic_adjudication_schema_sha256": ticket["semantic_adjudication_schema_sha256"],
        "run_authorization_schema_sha256": ticket["run_authorization_schema_sha256"],
        "output_structural_schema_sha256": ticket["output_structural_schema_sha256"],
        "vendor_manifest_sha256": ticket["vendor_manifest_sha256"],
        "vendor_tree_digest": ticket["vendor_tree_digest"],
        "mlx_lm_version": ticket["mlx_lm_version"],
        "decode": ticket["decode"],
        "model_run_authorized": ticket["model_run_authorized"],
        "training_authorized": ticket["training_authorized"],
        "api_authorized": ticket["api_authorized"],
        "decision_id": ticket["decision_id"],
        "source_thread_id": ticket["source_thread_id"],
        "approval_quote_sha256": ticket["approval_quote_sha256"],
        "control_window_dispatch_sha256": ticket["control_window_dispatch_sha256"],
        "control_window_dispatched_at": ticket["control_window_dispatched_at"],
    }


def assert_authorized_output_binding(
    ticket: dict[str, Any],
    output_dir: Path,
    *,
    run_root: Path = RUN_ROOT,
) -> None:
    authorized_output = ticket.get("authorized_output_dir")
    run_id = ticket.get("run_id")
    if not isinstance(authorized_output, str) or not isinstance(run_id, str):
        raise RuntimeError("RUN_AUTHORIZATION_OUTPUT_DIR_MISMATCH")
    authorized_path = Path(authorized_output)
    if not authorized_path.is_absolute() or ".." in authorized_path.parts:
        raise RuntimeError("RUN_AUTHORIZATION_OUTPUT_PATH_UNSAFE")
    if str(output_dir) != authorized_output:
        raise RuntimeError("RUN_AUTHORIZATION_OUTPUT_DIR_MISMATCH")
    expected = run_root / run_id
    try:
        assert_safe_path(authorized_path, root=run_root, exact=expected)
    except RuntimeError as error:
        raise RuntimeError("RUN_AUTHORIZATION_OUTPUT_OUTSIDE_RUN_ROOT") from error


def assert_single_use_available(
    run_id: str,
    output_dir: Path,
    *,
    claims_root: Path = RUN_CLAIMS,
) -> Path:
    claim = claims_root / f"{run_id}.json"
    run_root = claims_root.parent
    assert_safe_path(output_dir, root=run_root, exact=run_root / run_id)
    assert_safe_path(claims_root, root=run_root, exact=run_root / ".claims")
    assert_safe_path(claim, root=run_root, exact=claims_root / f"{run_id}.json")
    if output_dir.exists():
        raise RuntimeError(f"RUN_OUTPUT_ALREADY_EXISTS:{output_dir}")
    if claim.exists():
        raise RuntimeError(f"RUN_ID_ALREADY_CLAIMED:{run_id}")
    return claim


def claim_run_once(
    ticket_bytes: bytes,
    ticket_sha256: str,
    ticket: dict[str, Any],
    output_dir: Path,
    process_identity: dict[str, Any],
) -> tuple[Path, Path, Path, Path]:
    return _claim_run_once_core(
        ticket_bytes,
        ticket_sha256,
        ticket,
        output_dir,
        process_identity,
        claims_root=RUN_CLAIMS,
        start_writer=write_json_exclusive,
    )


def _claim_run_once_core(
    ticket_bytes: bytes,
    ticket_sha256: str,
    ticket: dict[str, Any],
    output_dir: Path,
    process_identity: dict[str, Any],
    *,
    claims_root: Path,
    start_writer: Any,
) -> tuple[Path, Path, Path, Path]:
    run_id = ticket["run_id"]
    run_root = claims_root.parent
    prepare_runtime_roots(run_root=run_root, claims_root=claims_root)
    claim = assert_single_use_available(
        run_id,
        output_dir,
        claims_root=claims_root,
    )
    claim.parent.mkdir(parents=True, exist_ok=True)
    claim_payload = {
        "run_id": run_id,
        "authorized_output_dir": str(output_dir),
        "authorization_ticket_sha256": ticket_sha256,
        "runner_sha256": process_identity["runner_sha256"],
        "r01_manifest_sha256": EXPECTED["r01_manifest"],
        "request_plan_sha256": execution_plan_identity_sha256(),
        "process_identity_at_start": process_identity,
        "status": "RUN_ID_CLAIMED_NO_REUSE",
    }
    with claim.open("xb") as handle:
        handle.write(
            json.dumps(
                claim_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
    authorization_copy = output_dir / "RUN_AUTHORIZATION_TICKET.json"
    start = output_dir / "RUN_START_RECEIPT.json"
    chain = output_dir / "RUN_START_CHAIN_RECEIPT.json"
    try:
        output_dir.mkdir()
        assert_safe_path(output_dir, root=run_root, exact=run_root / run_id, must_exist=True)
        with authorization_copy.open("xb") as handle:
            handle.write(ticket_bytes)
        if sha256(authorization_copy) != claim_payload["authorization_ticket_sha256"]:
            raise RuntimeError("RUN_AUTHORIZATION_COPY_SHA_MISMATCH")
        claim_sha = sha256(claim)
        start_writer(
            start,
            {
                **claim_payload,
                "status": "RUN_STARTED_MODEL_NOT_YET_LOADED",
                "started_at": now(),
                "request_count": 72,
                "arm_order": list(ARMS),
                "claim_sha256": claim_sha,
                "authorization_ticket_copy_sha256": sha256(authorization_copy),
                "authorization_validation": authorization_validation_projection(ticket),
            },
        )
        write_json_exclusive(
            chain,
            {
                "status": "PASS_RUN_START_CHAIN_BOUND_BEFORE_MODEL_LOAD",
                "run_id": run_id,
                "authorization_ticket_copy_sha256": sha256(authorization_copy),
                "claim_sha256": claim_sha,
                "run_start_receipt_sha256": sha256(start),
                "runner_sha256": claim_payload["runner_sha256"],
                "r01_manifest_sha256": claim_payload["r01_manifest_sha256"],
                "request_plan_sha256": claim_payload["request_plan_sha256"],
                "process_identity_at_start": process_identity,
            },
        )
        return claim, start, authorization_copy, chain
    except BaseException as error:
        abort_payload = {
            **claim_payload,
            "status": "HARD_STOP_RUN_START_ABORTED_NO_RETRY",
            "aborted_at": now(),
            "error_type": type(error).__name__,
            "error": str(error),
            "retry_attempted": False,
        }
        write_json_exclusive(
            claims_root / f"{run_id}.ABORTED.json",
            abort_payload,
        )
        if output_dir.is_dir():
            local_abort = output_dir / "RUN_ABORTED_RECEIPT.json"
            if not local_abort.exists():
                try:
                    write_json_exclusive(local_abort, abort_payload)
                except OSError:
                    pass
        raise


def run_model(ticket_path: Path, output_dir: Path) -> None:
    ticket_bytes = ticket_path.read_bytes()
    ticket_sha = hashlib.sha256(ticket_bytes).hexdigest()
    ticket = validate_authorization_ticket_bytes(ticket_bytes, output_dir)
    process_identity = freeze_process_identity()
    plan = load_execution_plan()
    claim, start_receipt, authorization_copy, start_chain = claim_run_once(
        ticket_bytes,
        ticket_sha,
        ticket,
        output_dir,
        process_identity,
    )
    began_all = time.monotonic()
    try:
        memory_before = require_memory_headroom("BEFORE_MODEL_LOAD")
        model_identity = verify_model_receipt_members()
        vendor_identity = verify_vendor_sources()

        sys.path.insert(0, str(VENDOR))
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.generate import stream_generate
        from mlx_lm.sample_utils import make_sampler

        mx.set_wired_limit(MLX_WIRED_LIMIT_BYTES)
        mx.set_memory_limit(MLX_MEMORY_LIMIT_BYTES)
        mx.set_cache_limit(MLX_CACHE_LIMIT_BYTES)
        mx.clear_cache()
        model, tokenizer = load(str(MODEL), adapter_path=str(ADAPTER))
        sampler = make_sampler(temp=0.0)
        rows = []
        peak = 0
        for sequence_index, item in enumerate(plan, start=1):
            require_memory_headroom(
                f"BEFORE_CASE:{item['arm']}:{item['case_id']}"
            )
            prompt = serialize_messages(tokenizer, item["request"]["messages"])
            pieces = []
            final = None
            began = time.monotonic()
            mx.reset_peak_memory()
            for response in stream_generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=MAX_OUTPUT_TOKENS,
                sampler=sampler,
            ):
                pieces.append(response.text)
                final = response
            if final is None:
                raise RuntimeError(
                    f"EMPTY_GENERATION:{item['arm']}:{item['case_id']}"
                )
            peak = max(peak, int(mx.get_peak_memory()))
            raw = "".join(pieces)
            rows.append(
                {
                    "sequence_index": sequence_index,
                    "arm": item["arm"],
                    "row_index": item["row_index"],
                    "case_id": item["case_id"],
                    "request_sha256": item["request_sha256"],
                    "gold_binding_sha256": item["gold_binding_sha256"],
                    "raw_output": raw,
                    "finish_reason": final.finish_reason,
                    "stop_token_id": int(final.token),
                    "stop_token_is_eos_eot": int(final.token)
                    in tokenizer.eos_token_ids,
                    "generation_tokens_including_stop": int(
                        final.generation_tokens
                    ),
                    "output_tokens_excluding_stop": len(
                        tokenizer.encode(raw, add_special_tokens=False)
                    ),
                    "input_tokens": int(final.prompt_tokens),
                    "elapsed_seconds": round(time.monotonic() - began, 3),
                    "full_prompt_sha256": text_sha256(prompt),
                }
            )
            mx.clear_cache()
        raw_path = output_dir / "RAW_OUTPUTS_72.jsonl"
        write_jsonl(raw_path, rows)
        process_identity_at_completion = verify_process_identity_unchanged(
            process_identity
        )
        write_json_exclusive(
            output_dir / "RUN_RECEIPT.json",
            {
                "status": "PASS_WO01_INFERENCE_COMPLETE_PENDING_SCORING",
                "run_id": ticket["run_id"],
                "completed_at": now(),
                "cases": 72,
                "arm_order": list(ARMS),
                "request_plan_sha256": execution_plan_identity_sha256(plan),
                "r01_manifest_sha256": EXPECTED["r01_manifest"],
                "raw_sha256": sha256(raw_path),
                "authorization_ticket_sha256": ticket_sha,
                "authorization_ticket_copy_sha256": sha256(authorization_copy),
                "runner_sha256": sha256(Path(__file__).resolve()),
                "claim_sha256": sha256(claim),
                "run_start_receipt_sha256": sha256(start_receipt),
                "run_start_chain_receipt_sha256": sha256(start_chain),
                "model_identity": model_identity,
                "vendor_identity": vendor_identity,
                "process_identity_at_start": process_identity,
                "process_identity_at_completion": process_identity_at_completion,
                "resource_controls": {
                    "minimum_free_memory_percent": MIN_FREE_MEMORY_PERCENT,
                    "mlx_wired_limit_bytes": MLX_WIRED_LIMIT_BYTES,
                    "mlx_memory_limit_bytes": MLX_MEMORY_LIMIT_BYTES,
                    "mlx_cache_limit_bytes": MLX_CACHE_LIMIT_BYTES,
                    "clear_cache_after_each_case": True,
                },
                "memory_before": memory_before,
                "memory_after": memory_snapshot(),
                "peak_mlx_bytes": peak,
                "elapsed_seconds": round(time.monotonic() - began_all, 3),
                "retry_count": 0,
                "model_run_authorized": True,
                "training_authorized": False,
                "api_authorized": False,
                "training": False,
                "api_called": False,
            },
        )
    except BaseException as error:
        write_json_exclusive(
            output_dir / "RUN_ABORTED_RECEIPT.json",
            {
                "status": "HARD_STOP_RUN_ABORTED_NO_RETRY",
                "run_id": ticket["run_id"],
                "aborted_at": now(),
                "authorization_ticket_sha256": ticket_sha,
                "authorization_ticket_copy_sha256": sha256(authorization_copy),
                "runner_sha256": sha256(Path(__file__).resolve()),
                "claim_sha256": sha256(claim),
                "run_start_receipt_sha256": sha256(start_receipt),
                "run_start_chain_receipt_sha256": sha256(start_chain),
                "r01_manifest_sha256": EXPECTED["r01_manifest"],
                "process_identity_at_start": process_identity,
                "process_identity_observed_at_abort": observe_process_identity_for_abort(
                    process_identity
                ),
                "error_type": type(error).__name__,
                "error": str(error),
                "retry_attempted": False,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "dry-run", "run"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--authorization-ticket", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        identities = verify_frozen_identities()
        plan = load_execution_plan()
        print(
            json.dumps(
                {
                    "status": "PASS_INPUTS_BOUND_RUN_NOT_AUTHORIZED",
                    "identities": identities,
                    "plan_rows": len(plan),
                    "messages_per_request": 2,
                    "model_loaded": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.command == "dry-run":
        if args.output_dir is None:
            parser.error("dry-run 需要 --output-dir")
        if args.output_dir.exists():
            raise RuntimeError(f"OUTPUT_EXISTS_NO_OVERWRITE:{args.output_dir}")
        evidence = build_test_only_serialization_evidence()
        args.output_dir.mkdir(parents=True)
        write_jsonl(args.output_dir / "TEST_ONLY_SERIALIZATION_EVIDENCE_72.jsonl", evidence)
        write_json(
            args.output_dir / "DRY_RUN_RECEIPT.json",
            {
                "status": "PASS_TEST_ONLY_TWO_MESSAGE_SERIALIZATION_72",
                "rows": len(evidence),
                "system_and_user_present": sum(
                    row["system_content_present_in_serialized_prompt"]
                    and row["user_content_present_in_serialized_prompt"]
                    for row in evidence
                ),
                "model_loaded": False,
                "tokenizer_loaded": False,
                "model_run_authorized": False,
            },
        )
        return
    if args.authorization_ticket is None or args.output_dir is None:
        parser.error("run 需要 --authorization-ticket 和 --output-dir")
    run_model(args.authorization_ticket, args.output_dir)


if __name__ == "__main__":
    main()
