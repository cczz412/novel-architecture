"""r02 分阶段子进程。

每个阶段只读取自己的 inbox。业务函数没有仓库根路径；Python audit hook
会拒绝 inbox/outbox 之外的运行期数据文件读取与一切网络访问。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

from .core import (
    Z96CoreError,
    apply_empirical_token_upper_bound,
    audit_render,
    recall_anchor_candidates,
    render_candidate,
    score_recall,
    sha256_bytes,
    split_atomic_claims,
    stable_json_bytes,
    validate_candidate_input,
)


class StageRuntimeError(RuntimeError):
    """阶段输入、权限或输出不满足冻结合同。"""


STAGE_INPUTS: dict[str, tuple[str, ...]] = {
    "freeze_claims": ("generation_cases.json",),
    "freeze_render_expectations": ("generation_cases.json",),
    "candidate": (
        "generation_cases.json",
        "atomic_claims.json",
        "token_bound_contract.json",
    ),
    "render": ("atomic_claims.json", "frozen_candidates.json"),
    "freeze_scores": (
        "x04_human_ledger.json",
        "z89_adjudication.json",
    ),
    "score": ("frozen_candidates.json", "scoring_answers.json"),
    "render_audit": ("frozen_render.json", "render_expectations.json"),
    "token_calibration": ("calibration_bundle.json",),
}

def _stable_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = stable_json_bytes(value)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StageReader:
    """只接受本阶段精确文件名的受控 reader。"""

    def __init__(self, stage: str, inbox: Path) -> None:
        if stage not in STAGE_INPUTS:
            raise StageRuntimeError(f"未知阶段：{stage}")
        self.stage = stage
        self.inbox = inbox.resolve()
        self.allowed = set(STAGE_INPUTS[stage])
        self.rows: list[dict[str, Any]] = []

    def json(self, name: str) -> Any:
        if name not in self.allowed:
            raise StageRuntimeError(f"{self.stage} 未获准读取：{name}")
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise StageRuntimeError("reader 拒绝绝对路径或上跳路径")
        path = self.inbox / name
        if path.is_symlink():
            raise StageRuntimeError(f"reader 拒绝符号链接：{name}")
        resolved = path.resolve(strict=True)
        if resolved.parent != self.inbox:
            raise StageRuntimeError(f"reader 路径逃出 inbox：{name}")
        data = resolved.read_bytes()
        row = {
            "name": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "parser": "json",
        }
        self.rows.append(row)
        return json.loads(data.decode("utf-8"))


def _install_audit_guard(inbox: Path, outbox: Path) -> list[dict[str, Any]]:
    """拒绝阶段业务对 inbox/outbox 外的数据文件和网络的访问。"""

    allowed_roots = (inbox.resolve(), outbox.resolve())
    events: list[dict[str, Any]] = []

    def under(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket.") or event in {
            "urllib.Request",
            "http.client.connect",
        }:
            events.append({"event": event, "decision": "REJECT"})
            raise PermissionError("r02 阶段禁止网络")
        if event == "open" and args:
            raw = args[0]
            if isinstance(raw, int):
                return
            try:
                path = Path(os.fspath(raw)).resolve()
            except (TypeError, ValueError, OSError):
                return
            matched_root = next(
                (root for root in allowed_roots if under(path, root)),
                None,
            )
            if matched_root is not None:
                root_label = "INBOX" if matched_root == allowed_roots[0] else "OUTBOX"
                events.append(
                    {
                        "event": "open",
                        "path": f"{root_label}/{path.relative_to(matched_root).as_posix()}",
                        "decision": "PASS",
                    }
                )
                return
            events.append(
                {
                    "event": "open",
                    "path": str(path),
                    "decision": "REJECT",
                }
            )
            raise PermissionError(f"r02 阶段拒绝 inbox/outbox 外读取：{path}")

    sys.addaudithook(hook)
    return events


def _case_map(generation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for dataset in generation.get("datasets", []):
        catalog = dataset.get("catalog_entries")
        if not isinstance(catalog, list) or not catalog:
            raise StageRuntimeError("generation dataset 缺 catalog_entries")
        for order, row in enumerate(catalog):
            if not isinstance(row, dict) or row.get("order") != order:
                raise StageRuntimeError("catalog_entries order 不连续")
        for case in dataset.get("cases", []):
            case_id = str(case.get("case_id") or "")
            if not case_id or case_id in result:
                raise StageRuntimeError("generation case_id 为空或重复")
            result[case_id] = {
                **case,
                "dataset_id": dataset["dataset_id"],
                "chapter": dataset["chapter"],
                "catalog_entries": catalog,
            }
    return result


def _stage_freeze_claims(reader: StageReader) -> dict[str, Any]:
    generation = reader.json("generation_cases.json")
    rows: list[dict[str, Any]] = []
    for case_id, case in sorted(_case_map(generation).items()):
        claims = split_atomic_claims(case_id, str(case["event_text"]))
        rows.append({"case_id": case_id, "claims": claims})
    return {
        "schema_version": "z96-r02-atomic-claims-v1",
        "status": "PASS",
        "cases": rows,
        "forbidden_fields_absent": True,
    }


def _stage_freeze_render_expectations(reader: StageReader) -> dict[str, Any]:
    generation = reader.json("generation_cases.json")
    rows = []
    for case_id, case in sorted(_case_map(generation).items()):
        event_text = str(case["event_text"])
        rows.append(
            {
                "case_id": case_id,
                "source_event_text": event_text,
                "source_event_sha256": sha256_bytes(event_text.encode("utf-8")),
                "source_length": len(event_text),
            }
        )
    return {
        "schema_version": "z96-r02-render-expectations-v1",
        "status": "PASS",
        "cases": rows,
    }


def _stage_candidate(reader: StageReader) -> dict[str, Any]:
    generation = reader.json("generation_cases.json")
    atomic = reader.json("atomic_claims.json")
    token_contract = reader.json("token_bound_contract.json")
    cases = _case_map(generation)
    claims_by_case = {
        str(row["case_id"]): row["claims"] for row in atomic.get("cases", [])
    }
    slope = float(token_contract["formula"]["tokens_per_nonblank_char"])
    intercept = int(token_contract["formula"]["fixed_margin_tokens"])
    rows: list[dict[str, Any]] = []
    for case_id, case in sorted(cases.items()):
        claims = claims_by_case.get(case_id)
        if not isinstance(claims, list) or not claims:
            raise StageRuntimeError(f"{case_id} 缺独立冻结原子主张")
        candidate_input = {
            "case_id": case_id,
            "event_text": case["event_text"],
            "claims": claims,
            "cited_anchor_ids": case["cited_anchor_ids"],
            "catalog_entries": case["catalog_entries"],
        }
        validate_candidate_input(candidate_input)
        recall = recall_anchor_candidates(
            claims,
            list(map(str, case["cited_anchor_ids"])),
            case["catalog_entries"],
        )
        catalog_by_id = {
            str(item["anchor_id"]): item for item in case["catalog_entries"]
        }
        island_contexts = []
        for island in recall["evidence_islands"]:
            left_boundary_id = island["left_boundary_anchor_id"]
            right_boundary_id = island["right_boundary_anchor_id"]
            island_contexts.append(
                {
                    "island_id": island["island_id"],
                    "selected_spans": [
                        {
                            "anchor_id": anchor_id,
                            "quote": str(catalog_by_id[anchor_id]["quote"]),
                        }
                        for anchor_id in island["anchor_ids"]
                    ],
                    "left_boundary_context": (
                        {
                            "anchor_id": left_boundary_id,
                            "quote": str(catalog_by_id[left_boundary_id]["quote"]),
                        }
                        if left_boundary_id is not None
                        else None
                    ),
                    "right_boundary_context": (
                        {
                            "anchor_id": right_boundary_id,
                            "quote": str(catalog_by_id[right_boundary_id]["quote"]),
                        }
                        if right_boundary_id is not None
                        else None
                    ),
                }
            )
        model_visible_payload = {
            "contract_version": "z96-r02-closure-model-visible-v1",
            "case_id": case_id,
            "event": case["event_text"],
            "atomic_claims": claims,
            "evidence_islands": island_contexts,
        }
        model_visible = [
            {
                "role": "system",
                "content": (
                    "只核对给定原子主张与各证据岛；不得补写候选外证据，"
                    "不得改写原子主张。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    model_visible_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ]
        budget = apply_empirical_token_upper_bound(
            model_visible,
            slope,
            fixed_margin_tokens=intercept,
        )
        rows.append(
            {
                "case_id": case_id,
                "dataset_id": case["dataset_id"],
                "chapter": case["chapter"],
                "event_id": case["event_id"],
                "event_text": case["event_text"],
                "cited_anchor_ids": case["cited_anchor_ids"],
                "catalog_order": [
                    str(item["anchor_id"]) for item in case["catalog_entries"]
                ],
                "candidate_anchor_ids": recall["candidate_anchor_ids"],
                "recall_trace": recall["trace"],
                "evidence_islands": recall["evidence_islands"],
                "model_visible_messages": model_visible,
                "token_upper_bound": budget,
                "status": "PASS",
            }
        )
    return {
        "schema_version": "z96-r02-frozen-candidates-v1",
        "status": "PASS",
        "cases": rows,
        "token_contract_sha256": sha256_bytes(stable_json_bytes(token_contract)),
        "candidate_input_forbidden_fields_absent": True,
    }


def _stage_render(reader: StageReader) -> dict[str, Any]:
    atomic = reader.json("atomic_claims.json")
    candidates = reader.json("frozen_candidates.json")
    claims_by_case = {
        str(row["case_id"]): row["claims"] for row in atomic.get("cases", [])
    }
    rows = []
    for candidate in candidates.get("cases", []):
        case_id = str(candidate["case_id"])
        rows.append(
            render_candidate(
                claims_by_case[case_id],
                candidate,
            )
        )
    return {
        "schema_version": "z96-r02-frozen-render-v1",
        "status": "PASS",
        "cases": rows,
    }


def _extract_z89_missing(reason: str) -> list[str]:
    values = re.findall(r"(?:所需|未挂的)(E\d{4})", reason)
    return list(dict.fromkeys(values))


def _stage_freeze_scores(reader: StageReader) -> dict[str, Any]:
    x04 = reader.json("x04_human_ledger.json")
    z89 = reader.json("z89_adjudication.json")
    rows: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    for row in x04.get("rows", []):
        case_id = f"X04:{row['event_id']}"
        missing = list(map(str, row.get("missing_required_anchor_ids") or []))
        cited = list(map(str, row.get("cited_anchor_ids") or []))
        rows.append(
            {
                "case_id": case_id,
                "dataset_id": "X04",
                "required_anchor_ids": list(dict.fromkeys(cited + missing)),
                "independent_missing_anchor_ids": missing,
                "source_verdict": row.get("verdict"),
            }
        )
        for anchor_id in missing:
            occurrences.append(
                {
                    "occurrence_id": f"X04:{row['event_id']}:{anchor_id}",
                    "case_id": case_id,
                    "event_id": row["event_id"],
                    "missing_anchor_id": anchor_id,
                }
            )
    if len(occurrences) != 85:
        raise StageRuntimeError(f"X04 缺锚发生次不是85：{len(occurrences)}")
    if len({row["occurrence_id"] for row in occurrences}) != 85:
        raise StageRuntimeError("X04 缺锚发生次存在重复键")
    for row in z89.get("gold_rows", []):
        if row.get("verdict") != "coverage_only_invalid_support":
            continue
        event_ids = list(map(str, row.get("candidate_event_ids") or []))
        missing = _extract_z89_missing(str(row.get("reason") or ""))
        if len(event_ids) != 1 or len(missing) != 1:
            raise StageRuntimeError("Z89 锚不托判词缺唯一事件或唯一缺锚")
        rows.append(
            {
                "case_id": f"Z89:{event_ids[0]}",
                "dataset_id": "Z89",
                "required_anchor_ids": [],
                "independent_missing_anchor_ids": missing,
                "historical_part_id": row.get("part_id"),
            }
        )
    return {
        "schema_version": "z96-r02-scoring-answers-v1",
        "status": "PASS",
        "score_only_canary": "SCORE-ONLY-CANARY-Z96-R02-7F3D1A",
        "cases": rows,
        "x04_occurrences": occurrences,
    }


def _stage_score(reader: StageReader) -> dict[str, Any]:
    candidates = reader.json("frozen_candidates.json")
    answers = reader.json("scoring_answers.json")
    candidate_by_case = {
        str(row["case_id"]): row for row in candidates.get("cases", [])
    }
    answer_rows = []
    disposition_rows = []
    total_required = 0
    total_recalled = 0
    for answer in answers.get("cases", []):
        case_id = str(answer["case_id"])
        candidate = candidate_by_case.get(case_id)
        if candidate is None:
            raise StageRuntimeError(f"评分答案找不到冻结候选：{case_id}")
        required = list(map(str, answer.get("required_anchor_ids") or []))
        if not required:
            required = list(candidate["cited_anchor_ids"])
        required = list(
            dict.fromkeys(
                required
                + list(map(str, answer.get("independent_missing_anchor_ids") or []))
            )
        )
        frozen_sha_before = sha256_bytes(stable_json_bytes(candidate))
        scored = score_recall(candidate, {"required_anchor_ids": required})
        frozen_sha_after = sha256_bytes(stable_json_bytes(candidate))
        if frozen_sha_before != frozen_sha_after:
            raise StageRuntimeError("评分器改写了冻结候选")
        independent = list(
            map(str, answer.get("independent_missing_anchor_ids") or [])
        )
        recalled = [
            anchor_id
            for anchor_id in independent
            if anchor_id in candidate["candidate_anchor_ids"]
        ]
        total_required += len(independent)
        total_recalled += len(recalled)
        answer_rows.append(
            {
                **scored,
                "dataset_id": answer["dataset_id"],
                "independent_missing_anchor_ids": independent,
                "recalled_independent_missing_anchor_ids": recalled,
                "frozen_candidate_sha256": frozen_sha_before,
                "candidate_unchanged_after_score": True,
            }
        )
    for occurrence in answers.get("x04_occurrences", []):
        candidate = candidate_by_case[occurrence["case_id"]]
        passed = occurrence["missing_anchor_id"] in candidate["candidate_anchor_ids"]
        disposition_rows.append(
            {
                **occurrence,
                "status": "PASS" if passed else "REJECT",
                "candidate_note": (
                    "候选召回包含该独立缺锚"
                    if passed
                    else "候选召回未包含该独立缺锚"
                ),
                "sample_or_formal_record_mutated": False,
            }
        )
    recall = total_recalled / total_required if total_required else 0.0
    return {
        "schema_version": "z96-r02-offline-score-v1",
        "status": "PASS" if recall == 1.0 else "REJECT",
        "independent_missing_span": {
            "denominator": total_required,
            "recalled": total_recalled,
            "recall": recall,
        },
        "x04_disposition": {
            "occurrence_denominator": 85,
            "rows": disposition_rows,
            "pass": sum(row["status"] == "PASS" for row in disposition_rows),
            "reject": sum(row["status"] == "REJECT" for row in disposition_rows),
            "unresolved": 0,
            "unique_missing_anchor_ids": len(
                {row["missing_anchor_id"] for row in disposition_rows}
            ),
        },
        "cases": answer_rows,
        "candidate_mutated": False,
        "score_only_canary": answers["score_only_canary"],
    }


def _stage_render_audit(reader: StageReader) -> dict[str, Any]:
    rendered = reader.json("frozen_render.json")
    expectations = reader.json("render_expectations.json")
    rendered_rows = rendered.get("cases", [])
    expectation_rows = expectations.get("cases", [])
    expected_by_case = {
        str(row["case_id"]): row for row in expectation_rows
    }
    rendered_case_ids = [str(row["case_id"]) for row in rendered_rows]
    expectation_case_ids = [str(row["case_id"]) for row in expectation_rows]
    one_to_one = (
        len(rendered_case_ids) == len(set(rendered_case_ids))
        and len(expectation_case_ids) == len(set(expectation_case_ids))
        and set(rendered_case_ids) == set(expectation_case_ids)
    )
    if not one_to_one:
        raise StageRuntimeError("渲染记录与独立期望不是全量一一对应")
    rows = []
    for row in rendered_rows:
        case_id = str(row["case_id"])
        rows.append(audit_render(row, expected_by_case[case_id]))
    status = "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "REJECT"
    return {
        "schema_version": "z96-r02-render-audit-v1",
        "status": status,
        "one_to_one_case_set": one_to_one,
        "cases": rows,
    }


def _stage_token_calibration(reader: StageReader) -> dict[str, Any]:
    bundle = reader.json("calibration_bundle.json")
    ratios: list[float] = []
    rows: list[dict[str, Any]] = []
    for row in bundle.get("samples", []):
        messages = row["messages"]
        text = json.dumps(
            messages,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        count = sum(1 for char in text if not char.isspace())
        prompt_tokens = int(row["prompt_tokens"])
        ratio = prompt_tokens / count
        ratios.append(ratio)
        rows.append(
            {
                "sample_id": row["sample_id"],
                "source_group": row["source_group"],
                "request_sha256": row["request_sha256"],
                "usage_source_sha256": row["usage_source_sha256"],
                "nonblank_message_codepoints": count,
                "prompt_tokens": prompt_tokens,
                "prompt_tokens_per_nonblank_char": ratio,
            }
        )
    if len(rows) != 39:
        raise StageRuntimeError(f"token 校准成功请求不是39：{len(rows)}")
    maximum = max(ratios)
    slope = 0.75
    margin = 64
    covered = sum(
        math.ceil(slope * row["nonblank_message_codepoints"]) + margin
        >= row["prompt_tokens"]
        for row in rows
    )
    if covered != len(rows):
        raise StageRuntimeError("经验保守上界未覆盖全部封存 usage")
    return {
        "schema_version": "z96-r02-empirical-token-upper-bound-v1",
        "status": "PASS",
        "route": "sealed_usage_empirical_conservative_upper_bound",
        "tokenizer_probe": bundle["tokenizer_probe"],
        "not_actual_token_count": True,
        "scope": (
            "仅适用于 DeepSeek V4 同模型族、相近 messages 形态的 r02 审计；"
            "不是跨模型数学普适上界。"
        ),
        "formula": {
            "character_measure": "stable_compact_messages_json_nonblank_unicode_codepoints",
            "tokens_per_nonblank_char": slope,
            "fixed_margin_tokens": margin,
            "expression": "ceil(0.75*C)+64",
        },
        "calibration": {
            "samples": len(rows),
            "covered_samples": covered,
            "observed_ratio_min": min(ratios),
            "observed_ratio_max": maximum,
            "slope_over_observed_max": slope / maximum,
            "rows": rows,
        },
    }


STAGE_HANDLERS: dict[str, Callable[[StageReader], dict[str, Any]]] = {
    "freeze_claims": _stage_freeze_claims,
    "freeze_render_expectations": _stage_freeze_render_expectations,
    "candidate": _stage_candidate,
    "render": _stage_render,
    "freeze_scores": _stage_freeze_scores,
    "score": _stage_score,
    "render_audit": _stage_render_audit,
    "token_calibration": _stage_token_calibration,
}


def run(stage: str, inbox: Path, outbox: Path) -> dict[str, Any]:
    inbox = inbox.resolve(strict=True)
    outbox = outbox.resolve()
    outbox.mkdir(parents=True, exist_ok=False)
    audit_events = _install_audit_guard(inbox, outbox)
    reader = StageReader(stage, inbox)
    try:
        output = STAGE_HANDLERS[stage](reader)
    except (KeyError, TypeError, ValueError, Z96CoreError) as exc:
        raise StageRuntimeError(str(exc)) from exc
    output_name = {
        "freeze_claims": "atomic_claims.json",
        "freeze_render_expectations": "render_expectations.json",
        "candidate": "frozen_candidates.json",
        "render": "frozen_render.json",
        "freeze_scores": "scoring_answers.json",
        "score": "offline_score.json",
        "render_audit": "render_audit.json",
        "token_calibration": "token_bound_contract.json",
    }[stage]
    _stable_write(outbox / output_name, output)
    receipt = {
        "schema_version": "z96-r02-stage-receipt-v1",
        "stage": stage,
        "status": output.get("status"),
        "input_allowlist": sorted(STAGE_INPUTS[stage]),
        "reads": reader.rows,
        "rejected_reader_reads": 0,
        "output": {
            "name": output_name,
            "sha256": _sha256_file(outbox / output_name),
            "bytes": (outbox / output_name).stat().st_size,
        },
        "audit_open_events": audit_events,
        "network_attempts": 0,
    }
    _stable_write(outbox / "stage_receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=sorted(STAGE_HANDLERS), required=True)
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--outbox", type=Path, required=True)
    parser.add_argument("--probe-path", type=Path)
    args = parser.parse_args()
    if args.probe_path is not None:
        inbox = args.inbox.resolve(strict=True)
        outbox = args.outbox.resolve()
        outbox.mkdir(parents=True, exist_ok=False)
        _install_audit_guard(inbox, outbox)
        args.probe_path.read_bytes()
        return 2
    run(args.stage, args.inbox, args.outbox)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
