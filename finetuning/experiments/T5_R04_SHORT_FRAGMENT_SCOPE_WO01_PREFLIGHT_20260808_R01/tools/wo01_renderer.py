from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ARM_ORDER = ("TARGET_ONLY", "SMALL_HALO", "CURRENT_WINDOW")
SMALL_HALO_CHARACTERS_EACH_SIDE = 8
CASE_ID_PATTERN = re.compile(r"^MICRO24B-S\d{2}$")
BEFORE_ID_PATTERN = re.compile(r"^B\d{2}$")
TARGET_ID_PATTERN = re.compile(r"^T\d{2}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def strict_read_utf8(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    if text.encode("utf-8") != raw:
        raise RuntimeError(f"UTF8_ROUNDTRIP_FAILED:{path}")
    return raw, text


def read_jsonl_strict(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    raw, text = strict_read_utf8(path)
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    return raw, rows


def source_projection(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": sample["case_id"],
        "source": sample["source"],
        "micro_atomizer": sample["micro_atomizer"],
    }


def validate_projection(sample: dict[str, Any]) -> dict[str, Any]:
    case_id = sample["case_id"]
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise RuntimeError(f"CASE_ID_INVALID:{case_id}")
    source = sample["source"]
    atomizer = sample["micro_atomizer"]
    before = source["read_only_before"]
    target = source["target"]
    after = source["read_only_after"]
    if not isinstance(before, str) or not isinstance(target, str) or not isinstance(after, str):
        raise RuntimeError(f"SOURCE_FIELD_NOT_STRING:{case_id}")
    if not before or not target or not after:
        raise RuntimeError(f"THREE_WAY_SCOPE_NOT_AVAILABLE:{case_id}")
    if sha256_bytes(target.encode("utf-8")) != source["target_sha256"]:
        raise RuntimeError(f"TARGET_SHA_MISMATCH:{case_id}")

    before_units = atomizer["before_units"]
    target_units = atomizer["target_units"]
    if not before_units or not target_units:
        raise RuntimeError(f"ATOMIZER_UNITS_MISSING:{case_id}")
    if "".join(unit["text"] for unit in before_units) != before:
        raise RuntimeError(f"BEFORE_UNITS_NOT_EXACT:{case_id}")
    if "".join(unit["text"] for unit in target_units) != target:
        raise RuntimeError(f"TARGET_UNITS_NOT_EXACT:{case_id}")
    if any(not BEFORE_ID_PATTERN.fullmatch(unit["id"]) for unit in before_units):
        raise RuntimeError(f"BEFORE_ID_INVALID:{case_id}")
    if any(not TARGET_ID_PATTERN.fullmatch(unit["id"]) for unit in target_units):
        raise RuntimeError(f"TARGET_ID_INVALID:{case_id}")

    return {
        "case_id": case_id,
        "before": before,
        "target": target,
        "after": after,
        "before_units": before_units,
        "target_units": target_units,
    }


def context_for_arm(validated: dict[str, Any], arm: str) -> tuple[str, str]:
    if arm == "TARGET_ONLY":
        return "", ""
    if arm == "SMALL_HALO":
        return (
            validated["before"][-SMALL_HALO_CHARACTERS_EACH_SIDE:],
            validated["after"][:SMALL_HALO_CHARACTERS_EACH_SIDE],
        )
    if arm == "CURRENT_WINDOW":
        return validated["before"], validated["after"]
    raise RuntimeError(f"UNKNOWN_ARM:{arm}")


def numbered_before(validated: dict[str, Any], arm: str, before_text: str) -> str:
    if not before_text:
        return "（无）"
    if arm == "CURRENT_WINDOW":
        return "\n".join(
            f"[{unit['id']}]{unit['text']}" for unit in validated["before_units"]
        )
    return f"[B01]{before_text}"


def render_model_visible(
    sample: dict[str, Any], arm: str, system_prompt: str
) -> dict[str, Any]:
    validated = validate_projection(source_projection(sample))
    before_text, after_text = context_for_arm(validated, arm)
    before = numbered_before(validated, arm, before_text)
    target = "\n".join(
        f"[{unit['id']}]{unit['text']}" for unit in validated["target_units"]
    )
    after = after_text or "（无）"
    user = (
        f"【编号只读上文】\n{before}\n\n"
        f"【编号负责区】\n{target}\n\n"
        f"【未编号只读下文】\n{after}\n"
    )
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ]
    }


def parse_user_sections(user: str) -> dict[str, str]:
    pattern = re.compile(
        r"\A【编号只读上文】\n(?P<before>.*?)\n\n"
        r"【编号负责区】\n(?P<target>.*?)\n\n"
        r"【未编号只读下文】\n(?P<after>.*?)\n\Z",
        re.DOTALL,
    )
    match = pattern.fullmatch(user)
    if match is None:
        raise RuntimeError("MODEL_USER_PAYLOAD_SHAPE_INVALID")
    return match.groupdict()


def remove_p3_case_label(user: str, case_id: str) -> str:
    prefix = f"【题号】\n{case_id}\n\n"
    if not user.startswith(prefix):
        raise RuntimeError(f"P3_CASE_LABEL_PREFIX_MISSING:{case_id}")
    return user[len(prefix) :]


def hidden_sidecar(
    sample: dict[str, Any],
    arm: str,
    model_visible: dict[str, Any],
    canonical_file_sha256: str,
    row_index: int,
) -> dict[str, Any]:
    validated = validate_projection(source_projection(sample))
    before_text, after_text = context_for_arm(validated, arm)
    return {
        "row_index": row_index,
        "arm": arm,
        "case_id": sample["case_id"],
        "canonical_file_sha256": canonical_file_sha256,
        "canonical_row_sha256": sha256_bytes(stable_json_bytes(sample)),
        "gold_binding_sha256": sha256_bytes(stable_json_bytes(sample.get("facts", []))),
        "target_sha256": sha256_bytes(validated["target"].encode("utf-8")),
        "allowed_evidence_ids": [unit["id"] for unit in validated["target_units"]],
        "read_only_source_ranges": {
            "before": {
                "field": "source.read_only_before",
                "start_char": len(validated["before"]) - len(before_text),
                "end_char_exclusive": len(validated["before"]),
            },
            "after": {
                "field": "source.read_only_after",
                "start_char": 0,
                "end_char_exclusive": len(after_text),
            },
        },
        "model_visible_request_sha256": sha256_bytes(stable_json_bytes(model_visible)),
    }


def contains_forbidden_visible_metadata(value: Any) -> list[str]:
    forbidden = (
        "TARGET_ONLY",
        "SMALL_HALO",
        "CURRENT_WINDOW",
        "MICRO24B-S",
        "case_id",
        "arm",
        "halo",
        "start_char",
        "end_char",
        "byte_start",
        "byte_end",
        "absolute",
    )
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return [token for token in forbidden if token in text]
