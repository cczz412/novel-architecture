#!/usr/bin/env python3
"""Build and mechanically check the PREP-only READ1 TRAIN96 package."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD72 = (
    REPO
    / "finetuning/experiments/T5_R04_READ1_TRAIN72_DENSITY_PAIRED_20260810_R01"
    / "READ_1_TARGET_TRAIN72_DENSITY_PAIRED.jsonl"
)
R03 = (
    REPO
    / "finetuning/experiments/"
    "T5_R04_TRAIN96_SOURCE6_RECUT24_MODEL_NEUTRAL_GOLD_20260810_R03"
)
R03_SOURCE = R03 / "SOURCE_INDEX_24.jsonl"
R03_GOLD = R03 / "MODEL_NEUTRAL_GOLD_24.jsonl"
R03_SIDECAR = R03 / "SEMANTIC_REVIEW_SIDECAR.jsonl"
R03_MANIFEST = R03 / "OUTPUT_MANIFEST.json"
R03_RECEIPT = R03 / "FINAL_VALIDATION_RECEIPT.json"
DIAGNOSTIC_FAIL = (
    REPO
    / "runs/T5_R04_READ1_TRAIN72_TOKEN_WEIGHTED_REDUCER_DIAGNOSTIC_R01/"
    "L6_MECHANICAL_FAIL_TICKET.json"
)
R04 = (
    REPO
    / "finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R04"
)
R04_LEDGER = R04 / "EXPERIMENT_DECISION_LEDGER.md"
R04_REGISTRY = R04 / "DECISION_REGISTRY.json"
MODEL = Path(
    "/Users/a1234/挣钱/小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f"
)
VENDOR = (
    REPO
    / "finetuning/experiments/T5_R04_TOKEN_WEIGHTED_GRAD_ACCUM_PREFLIGHT_20260810_R01/"
    "vendor_token_weighted"
)
PREFLIGHT_RECEIPT = VENDOR.parent / "PREPARE_RECEIPT.json"
TRAINER = VENDOR / "mlx_lm/tuner/trainer.py"
L6_ROOT = (
    REPO
    / "finetuning/experiments/T5_R04_TRAIN48_LENGTH_CALIBRATION_20260809_R01"
)
L6_INDEX = L6_ROOT / "L6_SOURCE_INDEX.jsonl"
REAL_INDEX = (
    REPO
    / "finetuning/experiments/T5_R04_LOCAL_REAL_SCREEN24_READ_EVAL_20260809_R01/"
    "REAL24_SOURCE_INDEX.jsonl"
)

TRAIN96 = HERE / "READ_1_TARGET_TRAIN96.jsonl"
TOKEN_STATS = HERE / "TRAIN96_TOKEN_STATS.json"
SPEC = HERE / "SPEC.json"
RUNNER = HERE / "run_train96_token_weighted.py"
SCORER = HERE / "score_train96_l6.py"
RECEIPT = HERE / "PREPARE_RECEIPT.json"
RUN_ROOT = REPO / "runs/T5_R04_READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_R01"

EXPECTED = {
    "old_train72_sha256": "9c1a2202380f5c589d590a34354309643b1bb8fc0a12732184e11a282c924797",
    "r03_source_sha256": "1067ec9ac4808523f543412cd419f133f3c352811467c032641ec1ba0ece350a",
    "r03_gold_sha256": "1bec7dbfc26878e0553e8f34319c072c46da0f6b80e4a3ae19842629451bec6d",
    "r03_sidecar_sha256": "239427e1780304be28eff3301132a5cf9304682798d37adc60fe6d5fed40d9df",
    "r03_manifest_sha256": "7eff5f3f591e6b79a69e005c1d654e9b68cf0e4597c8cdd061fb17fb39703ee4",
    "r03_receipt_sha256": "f79306c8d7eeaafdba7b465437bf455ea64ee8f6dfb479fd3c378d3f5096338c",
    "diagnostic_fail_sha256": "399c7eab1bf4f99cdf5012bf9ee027e15c798567d99a4082d5f15efdae57f62c",
    "preflight_receipt_sha256": "4e46a23ca6da1741c1027884a2a4e9c35cd3fb21576c1f8e58fc97166a08d31c",
    "trainer_sha256": "2ff621480fb043220f8dff29d01f85f6e8f8ffe9b04fb2eebc415a837b0be1c6",
    "vendor_tree_sha256": "2e77413bec6141f2a71b1fac032f5967bdfb9e2b65ba43a1b484d78d4e1f8059",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compact_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode()


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def vendor_tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
        digest.update(b"\0")
    return digest.hexdigest()


def verify_inputs() -> None:
    fixed = {
        OLD72: EXPECTED["old_train72_sha256"],
        R03_SOURCE: EXPECTED["r03_source_sha256"],
        R03_GOLD: EXPECTED["r03_gold_sha256"],
        R03_SIDECAR: EXPECTED["r03_sidecar_sha256"],
        R03_MANIFEST: EXPECTED["r03_manifest_sha256"],
        R03_RECEIPT: EXPECTED["r03_receipt_sha256"],
        DIAGNOSTIC_FAIL: EXPECTED["diagnostic_fail_sha256"],
        PREFLIGHT_RECEIPT: EXPECTED["preflight_receipt_sha256"],
        TRAINER: EXPECTED["trainer_sha256"],
    }
    for path, expected in fixed.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"INPUT_SHA_DRIFT:{path}")
    if vendor_tree_sha(VENDOR) != EXPECTED["vendor_tree_sha256"]:
        raise RuntimeError("VENDOR_TREE_SHA_DRIFT")
    if RUN_ROOT.exists():
        raise RuntimeError("RUN_ROOT_MUST_NOT_EXIST_DURING_PREPARATION")


def assistant_payload(facts: list[dict[str, Any]]) -> str:
    mapped = [
        {
            "fact": fact["fact_sentence"],
            "status": fact["status"],
            "speaker": fact["speaker"],
            "evidence_ids": fact["evidence_ids"],
        }
        for fact in facts
    ]
    return json.dumps({"facts": mapped}, ensure_ascii=False, separators=(",", ":"))


def build_new24(system: str) -> list[dict[str, Any]]:
    sources = read_jsonl(R03_SOURCE)
    gold_rows = read_jsonl(R03_GOLD)
    if len(sources) != 24 or len(gold_rows) != 24:
        raise RuntimeError("R03_NOT_24_CASES")
    gold = {row["case_id"]: row for row in gold_rows}
    if [row["case_id"] for row in sources] != [row["case_id"] for row in gold_rows]:
        raise RuntimeError("R03_SOURCE_GOLD_ORDER_DRIFT")
    rows = []
    for source in sources:
        case_id = source["case_id"]
        source_path = REPO / source["source_path"]
        source_bytes = source_path.read_bytes()
        if sha256_bytes(source_bytes) != source["source_chapter_sha256"]:
            raise RuntimeError(f"SOURCE_CHAPTER_SHA_DRIFT:{case_id}")
        source_text = source_bytes.decode("utf-8", errors="strict")
        target = source_text[source["target_start"] : source["target_end"]]
        if sha256_bytes(target.encode()) != source["target_sha256"]:
            raise RuntimeError(f"TARGET_SHA_DRIFT:{case_id}")
        if "".join(unit["text"] for unit in source["target_units"]) != target:
            raise RuntimeError(f"TXX_REBUILD_FAILED:{case_id}")
        numbered = "".join(
            f"[{unit['id']}]{unit['text']}" for unit in source["target_units"]
        )
        allowlist = "、".join(unit["id"] for unit in source["target_units"])
        user = (
            "【只读范围：只帮助理解，不得作为新增事实或证据】\n"
            f"{target}\n\n"
            "【编号负责区：只抽这里】\n"
            f"{numbered}\n\n"
            "【允许证据 ID】\n"
            f"{allowlist}"
        )
        answer = assistant_payload(gold[case_id]["facts"])
        visible = system + "\n" + user + "\n" + answer
        forbidden = [
            case_id,
            source["source_id"],
            source["review_class"],
            "HARD_ZERO",
            "reviewed_fact_count",
            "target_start",
            "target_end",
            "segment_sha256",
            "密度",
        ]
        leaked = [marker for marker in forbidden if marker and marker in visible]
        if leaked:
            raise RuntimeError(f"MODEL_VISIBLE_INTERNAL_METADATA:{case_id}:{leaked}")
        rows.append(
            {
                "metadata": {
                    "family": "READ",
                    "arm": "READ-1-TARGET",
                    "case_id": case_id,
                    "local_demo_only": True,
                },
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": answer},
                ],
            }
        )
    return rows


def render_train96() -> tuple[bytes, list[dict[str, Any]]]:
    old_rows = read_jsonl(OLD72)
    if len(old_rows) != 72:
        raise RuntimeError("OLD_TRAIN72_ROW_COUNT_DRIFT")
    systems = {row["messages"][0]["content"] for row in old_rows}
    if len(systems) != 1:
        raise RuntimeError("OLD_TRAIN72_SYSTEM_NOT_UNIFORM")
    new_rows = build_new24(next(iter(systems)))
    payload = OLD72.read_bytes() + compact_jsonl(new_rows)
    rows = old_rows + new_rows
    if payload.splitlines(keepends=True)[:72] != OLD72.read_bytes().splitlines(keepends=True):
        raise RuntimeError("OLD72_PREFIX_NOT_BYTE_IDENTICAL")
    return payload, rows


def fact_counts(rows: list[dict[str, Any]]) -> list[int]:
    output = []
    for row in rows:
        answer = json.loads(row["messages"][2]["content"])
        if set(answer) != {"facts"} or not isinstance(answer["facts"], list):
            raise RuntimeError("ASSISTANT_CONTRACT_INVALID")
        for fact in answer["facts"]:
            if set(fact) != {"fact", "status", "speaker", "evidence_ids"}:
                raise RuntimeError("ASSISTANT_FACT_CONTRACT_INVALID")
        output.append(len(answer["facts"]))
    return output


def overlap_check() -> dict[str, int]:
    current = read_jsonl(R03_SOURCE)
    previous = read_jsonl(L6_INDEX) + read_jsonl(REAL_INDEX)
    overlap = 0
    exact_sha = 0
    for row in current:
        for old in previous:
            old_path = old.get("source_path") or old.get("source_file")
            old_start = old.get("target_start", old.get("char_start"))
            old_end = old.get("target_end", old.get("char_end"))
            old_sha = old.get("target_sha256", old.get("segment_sha256"))
            if old_sha == row["target_sha256"]:
                exact_sha += 1
            if (
                old_path == row["source_path"]
                and isinstance(old_start, int)
                and isinstance(old_end, int)
                and max(old_start, row["target_start"]) < min(old_end, row["target_end"])
            ):
                overlap += 1
    if exact_sha or overlap:
        raise RuntimeError(f"L6_OR_REAL24_OVERLAP:sha={exact_sha}:range={overlap}")
    return {"exact_sha_overlap": 0, "coordinate_overlap": 0}


def tokenizer_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        import mlx_lm
        from mlx_lm.tuner.datasets import ChatDataset
        from transformers import AutoTokenizer
        import transformers
    except ImportError as error:
        raise RuntimeError("HOME_BREW_TOKENIZER_RUNTIME_REQUIRED") from error

    tokenizer = AutoTokenizer.from_pretrained(
        str(MODEL), local_files_only=True, trust_remote_code=True
    )
    dataset = ChatDataset(rows, tokenizer, mask_prompt=True)
    counts = fact_counts(rows)
    per_case = []
    truncated = []
    for index, (row, fact_count) in enumerate(zip(rows, counts, strict=True)):
        tokens, offset = dataset.process(row)
        sequence_tokens = len(tokens)
        assistant_tokens = sequence_tokens - offset
        if sequence_tokens > 4608:
            truncated.append(row["metadata"]["case_id"])
        per_case.append(
            {
                "row_index": index + 1,
                "case_id": row["metadata"]["case_id"],
                "source_group": "OLD_TRAIN72" if index < 72 else "R03_NEW24",
                "fact_count": fact_count,
                "sequence_tokens": sequence_tokens,
                "assistant_loss_tokens": assistant_tokens,
            }
        )

    def aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "rows": len(items),
            "facts": sum(item["fact_count"] for item in items),
            "empty_answers": sum(item["fact_count"] == 0 for item in items),
            "assistant_loss_tokens": sum(item["assistant_loss_tokens"] for item in items),
            "sequence_tokens": sum(item["sequence_tokens"] for item in items),
            "max_sequence_tokens": max(item["sequence_tokens"] for item in items),
            "min_sequence_tokens": min(item["sequence_tokens"] for item in items),
        }

    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in per_case:
        buckets[item["fact_count"]].append(item)
    bucket_stats = {
        str(count): {
            "rows": len(items),
            "assistant_loss_tokens": sum(item["assistant_loss_tokens"] for item in items),
            "assistant_loss_tokens_min": min(item["assistant_loss_tokens"] for item in items),
            "assistant_loss_tokens_max": max(item["assistant_loss_tokens"] for item in items),
        }
        for count, items in sorted(buckets.items())
    }
    old = aggregate(per_case[:72])
    new = aggregate(per_case[72:])
    combined = aggregate(per_case)
    return {
        "schema_version": "train96-real-tokenizer-accounting/1.0",
        "purpose_zh": "只记录真实tokenizer下的监督量和长度风险，不据此改权重或重排行序",
        "tokenizer": {
            "model_path": str(MODEL),
            "class": type(tokenizer).__name__,
            "method": "vendored ChatDataset(mask_prompt=true); assistant_loss_tokens=len(tokens)-assistant_offset",
            "python": sys.executable,
            "mlx_lm_version": getattr(mlx_lm, "__version__", "unknown"),
            "transformers_version": transformers.__version__,
            "model_weights_loaded": False,
        },
        "old_train72": old,
        "r03_new24": new,
        "combined": combined,
        "assistant_loss_token_share": {
            "old_train72": old["assistant_loss_tokens"] / combined["assistant_loss_tokens"],
            "r03_new24": new["assistant_loss_tokens"] / combined["assistant_loss_tokens"],
        },
        "fact_count_buckets": bucket_stats,
        "truncated_samples": len(truncated),
        "samples_over_4608": truncated,
        "per_case": per_case,
    }


def build_spec(train_sha: str, stats_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "read1-train96-token-weighted-qualification-spec/1.0",
        "preparation_status": "PREPARED_NOT_AUTHORIZED_NOT_RUN",
        "中文说明": (
            "这个包只准备一次TRAIN96 READ1资格赛：旧density-paired TRAIN72原字节保留，"
            "后接R03审过的24题；从原始base用token-weighted reducer只训练一轮。"
        ),
        "scope": "READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_SINGLE_RUN",
        "run_id": RUN_ROOT.name,
        "run_root": str(RUN_ROOT),
        "run_root_exists_at_prepare": RUN_ROOT.exists(),
        "training_authorized_now": False,
        "training_input": {
            "path": str(TRAIN96),
            "sha256": train_sha,
            "rows": 96,
            "facts": 879,
            "empty_answers": 15,
            "old72_prefix_path": str(OLD72),
            "old72_prefix_sha256": EXPECTED["old_train72_sha256"],
            "old72_prefix_byte_identical": True,
            "new24_order": "R03 SOURCE_INDEX canonical order appended directly",
            "model_visible_internal_density_metadata": False,
        },
        "r03_bindings": {
            "source_index_sha256": EXPECTED["r03_source_sha256"],
            "gold_sha256": EXPECTED["r03_gold_sha256"],
            "sidecar_sha256": EXPECTED["r03_sidecar_sha256"],
            "manifest_sha256": EXPECTED["r03_manifest_sha256"],
            "receipt_sha256": EXPECTED["r03_receipt_sha256"],
            "control_review": "MECHANICAL_PASS_AND_SEMANTIC_PASS",
        },
        "token_accounting": {
            "path": str(TOKEN_STATS),
            "sha256": stats_sha,
            "real_tokenizer": True,
            "used_to_change_order_or_weight": False,
        },
        "training_recipe": {
            "base": "Qwen3-4B-Instruct-2507_cdbee75f original base",
            "read_view": "READ1 TARGET+FOCUS",
            "optimizer": "Adam",
            "batch_size": 2,
            "grad_accumulation_steps": 4,
            "micro_iterations": 48,
            "optimizer_updates": 12,
            "learning_rate": 0.00003,
            "seed": 20260802,
            "num_layers": 16,
            "rank": 32,
            "dropout": 0,
            "scale": 0.125,
            "mask_prompt": True,
            "max_seq_length": 4608,
            "grad_checkpoint": True,
            "save_every": 48,
            "retained_checkpoint": "final_only",
            "retry": 0,
            "fallback": False,
            "checkpoint_sweep": False,
            "derived_trainer_sha256": EXPECTED["trainer_sha256"],
            "derived_vendor_tree_sha256": EXPECTED["vendor_tree_sha256"],
        },
        "l6_evaluation": {
            "base_rows": "reuse frozen same-contract BASE_L6 projection; no new base inference",
            "greedy": True,
            "temperature": 0,
            "max_output_tokens": 2048,
            "mechanical_gate": {
                "json_and_schema": "6/6",
                "LC-L01_and_L02": 0,
                "LC-L03_to_L06_each_at_least": 1,
                "illegal_evidence_repetition_token_limit_duplicates": 0,
            },
            "on_mechanical_pass": "create blind queue and stop for independent review",
            "semantic_gate": "LoRA L6 F1 not below frozen same-contract Base",
            "real24_prepared_or_authorized": False,
        },
        "ticket_contract": {
            "ticket_required_before_run_root_or_model_load": True,
            "schema_version": "read1-train96-token-weighted-qualification-ticket/1.0",
            "authorized_commands_exact": ["train", "infer-l6"],
            "ticket_created_by_this_preparation": False,
        },
        "components": {
            "builder_sha256": sha256(Path(__file__)),
            "runner_sha256": sha256(RUNNER),
            "scorer_sha256": sha256(SCORER),
            "diagnostic_fail_ticket_sha256": EXPECTED["diagnostic_fail_sha256"],
        },
        "forbidden": [
            "当前准备轮创建执行票或run root",
            "训练或推理",
            "改变旧72payload或顺序",
            "重排R03新24",
            "修改Prompt、Gold、权重、学习率或训练剂量",
            "REAL24、READ2、READ4、OUT",
            "API、Notion、Git、CURRENT、生产晋级",
        ],
    }


def validate(
    train_payload: bytes,
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> dict[str, Any]:
    if len(rows) != 96:
        raise RuntimeError("TRAIN96_NOT_96_ROWS")
    old_bytes = OLD72.read_bytes()
    if not train_payload.startswith(old_bytes):
        raise RuntimeError("OLD72_PREFIX_NOT_BYTE_IDENTICAL")
    cases = [row["metadata"]["case_id"] for row in rows]
    counts = fact_counts(rows)
    if len(set(cases)) != 96 or sum(counts) != 879 or counts.count(0) != 15:
        raise RuntimeError("TRAIN96_DENOMINATOR_FACT_OR_EMPTY_DRIFT")
    if [row["case_id"] for row in read_jsonl(R03_SOURCE)] != cases[72:]:
        raise RuntimeError("R03_CANONICAL_APPEND_ORDER_DRIFT")
    systems = {row["messages"][0]["content"] for row in rows}
    if len(systems) != 1:
        raise RuntimeError("SYSTEM_CONTRACT_NOT_UNIFORM")
    if stats["old_train72"]["rows"] != 72 or stats["r03_new24"]["rows"] != 24:
        raise RuntimeError("TOKEN_STATS_GROUP_DENOMINATOR_DRIFT")
    if stats["combined"]["facts"] != 879 or stats["combined"]["empty_answers"] != 15:
        raise RuntimeError("TOKEN_STATS_FACT_DENOMINATOR_DRIFT")
    if stats["truncated_samples"] or stats["combined"]["max_sequence_tokens"] > 4608:
        raise RuntimeError("TOKEN_LENGTH_GATE_FAILED")
    overlap = overlap_check()
    return {
        "rows": 96,
        "facts": 879,
        "empty_answers": 15,
        "old72_prefix_byte_identical": True,
        "r03_new24_canonical_order": True,
        "uniform_system_contract": True,
        "l6_real24_exact_overlap": overlap["exact_sha_overlap"],
        "l6_real24_coordinate_overlap": overlap["coordinate_overlap"],
        "max_sequence_tokens": stats["combined"]["max_sequence_tokens"],
        "truncated_samples": 0,
        "run_root_exists": RUN_ROOT.exists(),
        "model_weights_loaded": False,
        "training_runs": 0,
        "inference_runs": 0,
        "api_calls": 0,
    }


def build() -> dict[str, Any]:
    verify_inputs()
    payload, rows = render_train96()
    stats = tokenizer_stats(rows)
    validation = validate(payload, rows, stats)
    TRAIN96.write_bytes(payload)
    TOKEN_STATS.write_bytes(json_bytes(stats))
    spec = build_spec(sha256(TRAIN96), sha256(TOKEN_STATS))
    SPEC.write_bytes(json_bytes(spec))
    members = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in (Path(__file__), TRAIN96, TOKEN_STATS, SPEC, RUNNER, SCORER)
    }
    receipt = {
        "schema_version": "read1-train96-token-weighted-prepare-receipt/1.0",
        "preparation_status": "PREPARED_NOT_AUTHORIZED_NOT_RUN",
        "conclusion_zh": "TRAIN96 READ1单臂资格包已准备，等待控制窗审计和精确执行票",
        "members": members,
        "upstream": {
            "old_train72_sha256": EXPECTED["old_train72_sha256"],
            "r03_source_sha256": EXPECTED["r03_source_sha256"],
            "r03_gold_sha256": EXPECTED["r03_gold_sha256"],
            "r03_sidecar_sha256": EXPECTED["r03_sidecar_sha256"],
            "r03_manifest_sha256": EXPECTED["r03_manifest_sha256"],
            "r03_receipt_sha256": EXPECTED["r03_receipt_sha256"],
            "diagnostic_fail_sha256": EXPECTED["diagnostic_fail_sha256"],
            "preflight_receipt_sha256": EXPECTED["preflight_receipt_sha256"],
            "trainer_sha256": EXPECTED["trainer_sha256"],
            "vendor_tree_sha256": EXPECTED["vendor_tree_sha256"],
            "r04_ledger_sha256": sha256(R04_LEDGER),
            "r04_registry_sha256": sha256(R04_REGISTRY),
        },
        "validation": validation,
        "token_accounting": {
            "old72_assistant_loss_tokens": stats["old_train72"]["assistant_loss_tokens"],
            "new24_assistant_loss_tokens": stats["r03_new24"]["assistant_loss_tokens"],
            "combined_assistant_loss_tokens": stats["combined"]["assistant_loss_tokens"],
            "new24_share": stats["assistant_loss_token_share"]["r03_new24"],
        },
        "external_actions": {
            "model_loads": 0,
            "training_runs": 0,
            "inference_runs": 0,
            "api_calls": 0,
            "notion_actions": 0,
            "git_actions": 0,
            "current_pointer_changes": 0,
            "production_actions": 0,
        },
    }
    RECEIPT.write_bytes(json_bytes(receipt))
    return receipt


def check(with_tokenizer: bool) -> dict[str, Any]:
    verify_inputs()
    expected_payload, rows = render_train96()
    if TRAIN96.read_bytes() != expected_payload:
        raise RuntimeError("TRAIN96_DETERMINISTIC_RENDER_DRIFT")
    stats = read_json(TOKEN_STATS)
    if with_tokenizer and tokenizer_stats(rows) != stats:
        raise RuntimeError("TOKENIZER_STATS_RERUN_DRIFT")
    validation = validate(expected_payload, rows, stats)
    spec = read_json(SPEC)
    if spec["training_input"]["sha256"] != sha256(TRAIN96):
        raise RuntimeError("SPEC_TRAIN_SHA_DRIFT")
    if spec["token_accounting"]["sha256"] != sha256(TOKEN_STATS):
        raise RuntimeError("SPEC_TOKEN_STATS_SHA_DRIFT")
    receipt = read_json(RECEIPT)
    for name, identity in receipt["members"].items():
        path = HERE / name
        if path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]:
            raise RuntimeError(f"RECEIPT_MEMBER_DRIFT:{name}")
    if RUN_ROOT.exists():
        raise RuntimeError("RUN_ROOT_CREATED_DURING_PREPARATION")
    return validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--with-tokenizer", action="store_true")
    args = parser.parse_args()
    result = build() if args.command == "build" else check(args.with_tokenizer)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
