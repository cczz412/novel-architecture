#!/usr/bin/env python3
"""第91道续令②：六份新采样的实验合同变体运行壳。

现役 6 字合同和 Z91 v1 运行器均保持不变。本壳只在当前 Python 进程内
临时接入“完整短主谓句旁账”规则，退出后恢复 v1 模块原状。
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import z91_crossbook_exam_run as v1  # noqa: E402
from pipeline_common import model_benchmark  # noqa: E402
from zbatch_modules import neutral_extract  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402


DEFAULT_RUN_DIR = ROOT / "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723"
V1_RUN_DIR = ROOT / "runs/Z91_双臂跨书基线_步二双臂_v1.0_20260723"
SOURCE_FACT_DIR = V1_RUN_DIR / "review/source_facts"
CONTRACT_PATH = Path(__file__).with_name("short_summary_exception_v1.json")
RUBRIC_PATH = Path(__file__).with_name("blind_probe_rubric_v1.3.json")
BLIND_REVIEW_PATH = Path(__file__).with_name("z91_blind_review_v1_3.py")
CONTRACT_VERSION = "z91-crossbook-six-sample-v2-short-summary-ledger"
LEDGER_RELATIVE = Path("candidate/z91_v2_short_summary_ledger.json")

_V1_BUILD_PREPARED_BASE = v1._build_prepared_base
_V1_MECHANICAL_PASS = v1._mechanical_pass
_V1_MECHANICAL_FAIL = v1._mechanical_fail
_V1_SAMPLE_COMPLETION = v1._sample_completion
_V1_COMPLETION_DOCUMENT = v1._completion_document
_V1_RUN_CLAIM = v1._run_claim
_V1_SAMPLE_SPECS = v1.sample_specs


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return model_benchmark.sha256_file(path)


def _contract() -> dict[str, Any]:
    value = read_json(CONTRACT_PATH)
    if value.get("schema_version") != "z91-short-summary-exception-contract-v1":
        raise ZBatchError("Z91 v2 短摘要合同身份漂移")
    return value


def _rubric() -> dict[str, Any]:
    value = read_json(RUBRIC_PATH)
    if value.get("schema_version") != "z91-crossbook-blind-probe-rubric-v1.3":
        raise ZBatchError("Z91 v1.3 判分覆盖层身份漂移")
    base = value.get("base_rubric") or {}
    base_path = ROOT / str(base.get("path") or "")
    if not base_path.is_file() or sha256_file(base_path) != base.get("sha256"):
        raise ZBatchError("Z91 v1.3 没有钉住已拍 v1.2 基尺")
    return value


def _contract_sha() -> str:
    _contract()
    return sha256_file(CONTRACT_PATH)


def _rubric_sha() -> str:
    _rubric()
    return sha256_file(RUBRIC_PATH)


def sample_specs_v2() -> list[dict[str, Any]]:
    rows = copy.deepcopy(_V1_SAMPLE_SPECS())
    for row in rows:
        row["logical_request_id"] = f"Z91V2-{row['sample_id']}"
    return rows


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _build_prepared_base_v2(
    run_dir: Path, source_fact_seal: Path
) -> tuple[dict[str, bytes], dict[str, Any]]:
    payloads, preflight = _V1_BUILD_PREPARED_BASE(run_dir, source_fact_seal)
    contract_sha = _contract_sha()
    rubric_sha = _rubric_sha()
    payloads["prepared/contracts/short_summary_exception_v1.json"] = (
        CONTRACT_PATH.read_bytes()
    )
    payloads["prepared/contracts/blind_probe_rubric_v1.3.json"] = (
        RUBRIC_PATH.read_bytes()
    )
    subject_policy = _contract()["complete_subject_predicate_rule"][
        "subject_allowlist"
    ]
    for case_key, subjects in subject_policy["by_case"].items():
        body_key = f"inputs/cases/{case_key}/chapter_body.txt"
        body_bytes = payloads.get(body_key)
        if not isinstance(body_bytes, bytes):
            raise ZBatchError(f"短摘要主语表缺少冻结正文：{case_key}")
        body = body_bytes.decode("utf-8")
        missing = [subject for subject in subjects if subject not in body]
        if missing:
            raise ZBatchError(
                f"短摘要主语不在 {case_key} 冻结正文：{missing}"
            )

    plan = json.loads(payloads["prepared/run_plan.json"])
    plan.update(
        {
            "schema_version": "z91-six-sample-run-plan-v2",
            "contract_version": CONTRACT_VERSION,
            "rubric_version": "v1.3",
            "rubric_v1_3_sha256": rubric_sha,
            "short_summary_contract_sha256": contract_sha,
            "production_six_char_rule_changed": False,
            "fresh_logical_request_ids": True,
        }
    )
    payloads["prepared/run_plan.json"] = _json_bytes(plan)

    preflight = dict(preflight)
    preflight.update(
        {
            "schema_version": "z91-step2-v2-preflight-v1",
            "contract_version": CONTRACT_VERSION,
            "rubric_v1_3_sha256": rubric_sha,
            "short_summary_contract_sha256": contract_sha,
            "production_six_char_rule_changed": False,
            "old_v1_run_modified": False,
        }
    )
    payloads["prepared/preflight.json"] = _json_bytes(preflight)

    manifest = json.loads(payloads["run_manifest.json"])
    manifest.update(
        {
            "schema_version": "z91-step2-v2-run-manifest-v1",
            "contract_version": CONTRACT_VERSION,
            "rubric_v1_3_sha256": rubric_sha,
            "short_summary_contract_sha256": contract_sha,
            "production_six_char_rule_changed": False,
        }
    )
    payloads["run_manifest.json"] = _json_bytes(manifest)
    return payloads, preflight


def _strip_for_parse(summary: str) -> tuple[str, str]:
    contract = _contract()["complete_subject_predicate_rule"]
    compact = "".join(
        character
        for character in unicodedata.normalize("NFC", summary)
        if not character.isspace()
    )
    terminal = ""
    terminals = set(contract["terminal_punctuation"])
    if compact and compact[-1] in terminals:
        terminal = compact[-1]
        compact = compact[:-1]
    if any(character in terminals or unicodedata.category(character).startswith("P") for character in compact):
        raise ZBatchError("短摘要含句中标点，不能机械认作单一完整主谓句")
    return compact, terminal


def _allowed_subjects(case_key: str | None = None) -> set[str]:
    policy = _contract()["complete_subject_predicate_rule"]["subject_allowlist"]
    subjects = set(policy["global_pronouns"])
    by_case = policy["by_case"]
    if case_key is None:
        for rows in by_case.values():
            subjects.update(rows)
    else:
        rows = by_case.get(case_key)
        if not isinstance(rows, list):
            raise ZBatchError(f"短摘要主语表缺少用例 {case_key}")
        subjects.update(rows)
    return subjects


def parse_complete_subject_predicate(
    summary: str, *, case_key: str | None = None
) -> dict[str, str] | None:
    """按冻结词表找显式主语和谓语；只判句型，不作语义真值判断。"""

    if not isinstance(summary, str):
        return None
    contract = _contract()
    length = neutral_extract.nonspace_chars(summary)
    length_rule = contract["length_rule"]
    if not (
        int(length_rule["exception_min_nonspace_chars"])
        <= length
        <= int(length_rule["exception_max_nonspace_chars"])
    ):
        return None
    try:
        core, terminal = _strip_for_parse(summary)
    except ZBatchError:
        return None
    if len(core) < 2:
        return None

    rule = contract["complete_subject_predicate_rule"]
    forbidden_exact = set(rule["subject_forbidden_exact"])
    forbidden_initial = tuple(rule["sentence_initial_forbidden_adverbials"])
    forbidden_suffix = tuple(rule["subject_forbidden_suffix"])
    allowed_subjects = _allowed_subjects(case_key)
    if core.startswith(forbidden_initial):
        return None
    modifiers = sorted(set(rule["predicate_prefix_modifiers"]), key=lambda x: (-len(x), x))
    heads = sorted(set(rule["predicate_heads"]), key=lambda x: (-len(x), x))
    heads_requiring_tail = set(rule["predicate_heads_requiring_lexical_tail"])
    aspect_only = set(rule["aspect_only_tail_characters"])
    subject_re = re.compile(r"^[\u3400-\u9fffA-Za-z0-9·]+$")
    candidates: list[dict[str, str]] = []
    for split in range(1, len(core)):
        subject = core[:split]
        predicate = core[split:]
        if (
            not subject_re.fullmatch(subject)
            or subject not in allowed_subjects
            or subject in forbidden_exact
            or subject.endswith(forbidden_suffix)
        ):
            continue
        modifier = ""
        predicate_body = predicate
        for value in modifiers:
            if predicate.startswith(value) and len(predicate) > len(value):
                modifier = value
                predicate_body = predicate[len(value) :]
                break
        for head in heads:
            if not predicate_body.startswith(head):
                continue
            tail = predicate_body[len(head) :]
            if len(tail) > 2 or any(
                unicodedata.category(character).startswith("P") for character in tail
            ):
                continue
            if head in heads_requiring_tail and not any(
                character not in aspect_only for character in tail
            ):
                continue
            candidates.append(
                {
                    "subject": subject,
                    "subject_allowlist_scope": case_key or "contract_union_for_test",
                    "predicate": predicate,
                    "predicate_modifier": modifier,
                    "predicate_head": head,
                    "predicate_tail": tail,
                    "terminal_punctuation": terminal,
                }
            )
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            len(row["subject"]),
            -len(row["predicate_head"]),
            row["subject"],
            row["predicate"],
        )
    )
    return candidates[0]


_LENGTH_REASON = re.compile(r"^(EV-C\d{4}-\d{2})事件摘要长度非法$")


def _short_exception_rows(
    model_data: Mapping[str, Any],
    shared_reasons: Sequence[str],
    catalog: Sequence[Mapping[str, Any]],
    case_key: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    events = model_data.get("events")
    event_map = {
        str(row.get("event_id")): row
        for row in events
        if isinstance(events, list) and isinstance(row, Mapping)
    } if isinstance(events, list) else {}
    catalog_ids = {
        str(row.get("anchor_id"))
        for row in catalog
        if isinstance(row, Mapping) and isinstance(row.get("anchor_id"), str)
    }
    rows: list[dict[str, Any]] = []
    effective = list(shared_reasons)
    labels = tuple(neutral_extract.CLASSIFICATION_LABELS)
    for reason in shared_reasons:
        match = _LENGTH_REASON.fullmatch(reason)
        if not match:
            continue
        event_id = match.group(1)
        event = event_map.get(event_id)
        if not isinstance(event, Mapping) or set(event) != neutral_extract.EVENT_KEYS:
            continue
        summary = event.get("event")
        parsed = (
            parse_complete_subject_predicate(summary, case_key=case_key)
            if isinstance(summary, str)
            else None
        )
        anchors = event.get("anchors")
        anchor_ids = [
            anchor.get("anchor_id")
            for anchor in anchors
            if isinstance(anchor, Mapping) and set(anchor) == neutral_extract.ANCHOR_KEYS
        ] if isinstance(anchors, list) else []
        anchors_legal = bool(anchor_ids) and len(anchor_ids) == len(anchors) and (
            len(anchor_ids) == len(set(anchor_ids))
            and all(isinstance(value, str) and value in catalog_ids for value in anchor_ids)
        )
        if (
            parsed is None
            or not anchors_legal
            or any(label in summary for label in labels)
        ):
            continue
        effective.remove(reason)
        rows.append(
            {
                "event_id": event_id,
                "event": summary,
                "nonspace_chars": neutral_extract.nonspace_chars(summary),
                "shared_reason": reason,
                "decision": "short_summary_violation_observed_but_sample_effective",
                **parsed,
                "anchor_ids": anchor_ids,
                "entered_formal_record": False,
                "changed_shared_contract": False,
            }
        )
    return rows, sorted(set(effective))


def _mechanical_pass_v2(
    sample_root: Path,
    sample: Mapping[str, Any],
    response: Mapping[str, Any],
    raw_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    model_data, content, reasoning, finish = model_benchmark.response_envelope(
        response,
        str(sample["model"]),
        require_nonempty_reasoning=bool(sample["require_reasoning"]),
    )
    if response.get("model") != sample["model"]:
        raise v1.Z91RunHardStop(
            "response_model_mismatch",
            f"响应型号 {response.get('model')!r} 不是冻结精确型号 {sample['model']}",
        )
    catalog_path = (
        sample_root.parents[1]
        / f"inputs/cases/{sample['case_key']}/evidence_catalog.json"
    )
    catalog_doc = read_json(catalog_path)
    catalog = catalog_doc.get("entries") if isinstance(catalog_doc, Mapping) else None
    if not isinstance(catalog, list):
        raise v1.Z91RunHardStop("catalog_contract", "冻结证据目录缺 entries")
    shared_reasons, shared_audit = neutral_extract.audit_event_envelope(
        model_data, int(sample["chapter"]), catalog
    )
    exception_rows, effective_reasons = _short_exception_rows(
        model_data, shared_reasons, catalog, str(sample["case_key"])
    )
    length_reasons = [reason for reason in shared_reasons if _LENGTH_REASON.fullmatch(reason)]
    shared_gate = not length_reasons
    exception_gate = all(reason not in effective_reasons for reason in length_reasons)
    effective_gate = not effective_reasons
    if not effective_gate:
        reason_code = (
            "structure_overreach"
            if any("字段" in reason or "外壳" in reason for reason in effective_reasons)
            else "mechanical_contract"
        )
        raise v1.Z91RunHardStop(
            reason_code,
            f"{sample['sample_id']} v2有效机械合同失败：{effective_reasons}；不做补跑或修补",
        )

    ledger = {
        "schema_version": "z91-short-summary-side-ledger-v1",
        "contract_version": CONTRACT_VERSION,
        "short_summary_contract_sha256": _contract_sha(),
        "rubric_v1_3_sha256": _rubric_sha(),
        "sample_id": sample["sample_id"],
        "chapter": sample["chapter"],
        "raw_response_sha256": sha256_file(raw_path),
        "model_json_sha256": v1.canonical_sha(model_data),
        "catalog_sha256": sha256_file(catalog_path),
        "shared_reasons": list(shared_reasons),
        "effective_reasons": effective_reasons,
        "status": "pass_with_side_ledger" if exception_rows else "pass_no_exception",
        "exception_count": len(exception_rows),
        "entries": exception_rows,
    }
    ledger_path = sample_root / LEDGER_RELATIVE
    if ledger_path.exists():
        if read_json(ledger_path) != ledger:
            raise ZBatchError("短摘要旁账不能由原始响应和冻结合同重建")
    else:
        v1.write_json_exclusive(ledger_path, ledger)

    materialized = neutral_extract.materialize_events(
        model_data, catalog, int(sample["chapter"])
    )
    program_audit = {
        "schema_version": "z91-v2-effective-program-audit-v1",
        "chapter": sample["chapter"],
        "status": "pass",
        "shared_audit": shared_audit,
        "shared_reasons": list(shared_reasons),
        "effective_reasons": effective_reasons,
        "short_summary_violation_count": len(exception_rows),
        "short_summary_ledger_sha256": sha256_file(ledger_path),
        "scope_note": "共享6字审计原样保留；本层只登记实验合同的有效判词。",
    }
    mechanical = {
        "schema_version": "z91-mechanical-three-gates-v2",
        "status": "pass",
        "sample_id": sample["sample_id"],
        "json_and_schema_gate": True,
        "catalog_anchor_gate": len(shared_audit["missing_catalog_anchor_ids"]) == 0,
        "length_and_contiguous_id_gate": (
            finish == "stop"
            and shared_audit["event_ids_contiguous"]
            and shared_audit["invalid_event_id_count"] == 0
            and effective_gate
        ),
        "shared_six_char_gate": shared_gate,
        "z91_v2_exception_gate": exception_gate,
        "effective_gate": effective_gate,
        "event_count": shared_audit["event_count"],
        "anchor_reference_count": shared_audit["anchor_reference_count"],
        "outside_catalog_anchor_count": len(shared_audit["missing_catalog_anchor_ids"]),
        "invalid_event_id_count": shared_audit["invalid_event_id_count"],
        "events_without_anchors": shared_audit["events_without_anchors"],
        "finish_reason": finish,
        "response_model": response.get("model"),
        "content_sha256": model_benchmark.sha256_bytes(content.encode("utf-8")),
        "reasoning_content_sha256": model_benchmark.sha256_bytes(
            reasoning.encode("utf-8")
        ),
        "raw_response_path": raw_path.relative_to(sample_root).as_posix(),
        "raw_response_sha256": sha256_file(raw_path),
        "short_summary_contract_sha256": _contract_sha(),
        "rubric_v1_3_sha256": _rubric_sha(),
        "short_summary_ledger_path": LEDGER_RELATIVE.as_posix(),
        "short_summary_ledger_sha256": sha256_file(ledger_path),
        "short_summary_violation_count": len(exception_rows),
    }
    if not all(
        mechanical[field]
        for field in (
            "json_and_schema_gate",
            "catalog_anchor_gate",
            "length_and_contiguous_id_gate",
            "z91_v2_exception_gate",
            "effective_gate",
        )
    ):
        raise v1.Z91RunHardStop("mechanical_gate", "Z91 v2 机械闸没有全过")
    return model_data, materialized, program_audit, mechanical


def _mechanical_fail_v2(*args: Any, **kwargs: Any) -> dict[str, Any]:
    value = _V1_MECHANICAL_FAIL(*args, **kwargs)
    value.update(
        {
            "schema_version": "z91-mechanical-three-gates-v2",
            "short_summary_contract_sha256": _contract_sha(),
            "rubric_v1_3_sha256": _rubric_sha(),
            "effective_gate": False,
        }
    )
    return value


def _sample_completion_v2(*args: Any, **kwargs: Any) -> dict[str, Any]:
    value = _V1_SAMPLE_COMPLETION(*args, **kwargs)
    mechanical = args[3] if len(args) >= 4 else kwargs["mechanical"]
    value.update(
        {
            "schema_version": "z91-sample-completion-v2",
            "rubric_v1_3_sha256": _rubric_sha(),
            "short_summary_contract_sha256": _contract_sha(),
            "short_summary_violation_count": int(
                mechanical["short_summary_violation_count"]
            ),
        }
    )
    return value


def _completion_document_v2(*args: Any, **kwargs: Any) -> dict[str, Any]:
    value = _V1_COMPLETION_DOCUMENT(*args, **kwargs)
    completions = args[1] if len(args) >= 2 else kwargs["completions"]
    value.update(
        {
            "schema_version": "z91-step2-completion-v2",
            "rubric_v1_3_sha256": _rubric_sha(),
            "short_summary_contract_sha256": _contract_sha(),
            "short_summary_violation_count": sum(
                int(row["short_summary_violation_count"]) for row in completions
            ),
        }
    )
    return value


def _run_claim_v2(*args: Any, **kwargs: Any) -> dict[str, Any]:
    value = _V1_RUN_CLAIM(*args, **kwargs)
    value.update(
        {
            "schema_version": "z91-six-sample-run-claim-v2",
            "contract_version": CONTRACT_VERSION,
            "rubric_v1_3_sha256": _rubric_sha(),
            "short_summary_contract_sha256": _contract_sha(),
            "fresh_six_sample_rerun": True,
            "production_six_char_rule_changed": False,
        }
    )
    return value


@contextmanager
def _activated() -> Iterator[None]:
    patches = {
        "CONTRACT_VERSION": CONTRACT_VERSION,
        "sample_specs": sample_specs_v2,
        "_build_prepared_base": _build_prepared_base_v2,
        "_mechanical_pass": _mechanical_pass_v2,
        "_mechanical_fail": _mechanical_fail_v2,
        "_sample_completion": _sample_completion_v2,
        "_completion_document": _completion_document_v2,
        "_run_claim": _run_claim_v2,
        "RUNTIME_DEPENDENCIES": tuple(
            dict.fromkeys(
                (
                    *v1.RUNTIME_DEPENDENCIES,
                    Path(__file__).resolve(),
                    CONTRACT_PATH,
                    RUBRIC_PATH,
                    BLIND_REVIEW_PATH,
                )
            )
        ),
    }
    originals = {name: getattr(v1, name) for name in patches}
    try:
        for name, value in patches.items():
            setattr(v1, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(v1, name, value)


def _copy_source_facts(run_dir: Path) -> Path:
    if not SOURCE_FACT_DIR.is_dir():
        raise ZBatchError("v1 来源事实封签目录缺失")
    target = run_dir / "review/source_facts"
    for source in sorted(path for path in SOURCE_FACT_DIR.iterdir() if path.is_file()):
        destination = target / source.name
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise ZBatchError(f"新运行来源事实副本漂移：{destination}")
        else:
            v1.write_bytes_exclusive(destination, source.read_bytes())
    seal = target / "source_fact_seal.json"
    if sha256_file(seal) != "b191b0d6174040613c2593671af834e21d899b3b02b63b60495a20ea17828279":
        raise ZBatchError("复用的来源事实 seal SHA 漂移")
    return seal


def prepare(run_dir: Path) -> dict[str, Any]:
    if run_dir.resolve() == V1_RUN_DIR.resolve():
        raise ZBatchError("v2 禁止写入 v1 硬停目录")
    seal = _copy_source_facts(run_dir)
    with _activated():
        return v1.prepare(run_dir, seal)


def verify_prepared(run_dir: Path) -> dict[str, Any]:
    with _activated():
        return v1.verify_prepared(run_dir)


def _v2_completion_audit(run_dir: Path) -> dict[str, Any]:
    completion = read_json(run_dir / "completion.json")
    ledgers = [
        read_json(run_dir / f"samples/{sample['sample_id']}" / LEDGER_RELATIVE)
        for sample in sample_specs_v2()
    ]
    count = sum(int(row["exception_count"]) for row in ledgers)
    if (
        completion.get("rubric_v1_3_sha256") != _rubric_sha()
        or completion.get("short_summary_contract_sha256") != _contract_sha()
        or completion.get("short_summary_violation_count") != count
    ):
        raise ZBatchError("Z91 v2 完成票不能由六份短摘要旁账重建")
    receipt = {
        "schema_version": "z91-v2-contract-completion-audit-v1",
        "status": "pass_rebuilt_from_six_raw_samples_and_side_ledgers",
        "run_id": run_dir.name,
        "logical_samples": 6,
        "rubric_v1_3_sha256": _rubric_sha(),
        "short_summary_contract_sha256": _contract_sha(),
        "short_summary_violation_count": count,
        "production_six_char_rule_changed": False,
        "v1_run_modified": False,
        "deepseek_official_api_used": False,
    }
    path = run_dir / "audit/v2_contract_audit.json"
    if path.exists():
        if read_json(path) != receipt:
            raise ZBatchError("Z91 v2 既有合同审计票漂移")
    else:
        v1.write_json_exclusive(path, receipt)
    return receipt


def run(run_dir: Path, **kwargs: Any) -> dict[str, Any]:
    with _activated():
        result = v1.run(run_dir, **kwargs)
    _v2_completion_audit(run_dir)
    return result


def audit(run_dir: Path) -> dict[str, Any]:
    with _activated():
        result = v1.audit_completed(run_dir)
    _v2_completion_audit(run_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("prepare", "零调用复制封签并冻结 v2 六样本"),
        ("verify", "零调用回读准备件"),
        ("run", "在线型号闸后发送六份全新样本"),
        ("audit", "从六份原始响应与旁账重建完成态"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)
    run_dir = args.run_dir.resolve()
    if args.command == "prepare":
        result = prepare(run_dir)
    elif args.command == "verify":
        result = verify_prepared(run_dir)
    elif args.command == "run":
        result = run(run_dir)
    else:
        result = audit(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
