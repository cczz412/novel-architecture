#!/usr/bin/env python3
"""Z99 件1：离线挖出盲产候选与现役金标之间的表面差异。

这个工具只比较已经存在的 JSON，不读取小说正文，不调用模型，也不访问网络。
输出中的“候选”只表示 claim 字段没有达到固定的词面相似度阈值，不能据此判定
正式金标存在语义漏项。
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import statistics
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLIND_ROOT = ROOT / "TEMP/gold_blind_produce_returns_20260724"
DEFAULT_GOLD_ROOT = ROOT / "config/gold"
DEFAULT_OUTPUT_DIR = (
    ROOT / "experiments/Z99_external_finalization_supply_20260724/blind_mining"
)

CANDIDATE_STATUS = "candidate_surface_uncovered_pending_semantic_review"
CONTRACT_VERSION = "z99-blind-gold-surface-mining-contract-v1"
ROW_SCHEMA_VERSION = "z99-blind-gold-surface-candidate-row-v1"
SIMILARITY_ALGORITHM_VERSION = "claim-surface-char-ngram-v1"
SIMILARITY_THRESHOLD = 0.500000
SCORE_DECIMAL_PLACES = 6
SEQUENCE_WEIGHT = 0.45
BIGRAM_DICE_WEIGHT = 0.35
TRIGRAM_DICE_WEIGHT = 0.20


class Z99MiningError(ValueError):
    """输入、合同或产物不满足 Z99 件1的机械边界。"""


@dataclass(frozen=True)
class WindowSpec:
    slot: str
    title: str
    blind_relative_path: str
    pointer_relative_path: str


WINDOW_SPECS: tuple[WindowSpec, ...] = (
    WindowSpec(
        slot="01_X01_guimi",
        title="诡秘之主·第3章",
        blind_relative_path=(
            "01_X01_guimi/03_unzipped_normalized/02_blind_candidate.json"
        ),
        pointer_relative_path="X01_ch0003_structure_gold_current.json",
    ),
    WindowSpec(
        slot="02_B01_zhifou",
        title="知否·U0033",
        blind_relative_path=(
            "02_B01_zhifou/03_unzipped_normalized/02_blind_candidate.json"
        ),
        pointer_relative_path="Z74B_B01_U0033_structure_gold_current.json",
    ),
    WindowSpec(
        slot="03_B02_dawang",
        title="大王饶命·U0039",
        blind_relative_path=(
            "03_B02_dawang/03_unzipped_normalized/02_blind_candidate.json"
        ),
        pointer_relative_path="Z74B_B02_U0039_structure_gold_current.json",
    ),
    WindowSpec(
        slot="04_B03_shenmi",
        title="神秘复苏·U0041",
        blind_relative_path=(
            "04_B03_shenmi/03_unzipped_normalized/02_blind_candidate.json"
        ),
        pointer_relative_path="Z74B_B03_U0041_structure_gold_current.json",
    ),
    WindowSpec(
        slot="05_B04_wuxian",
        title="无限恐怖·U0003",
        blind_relative_path=(
            "05_B04_wuxian/03_unzipped_normalized/02_blind_candidate.json"
        ),
        pointer_relative_path="Z74B_B04_U0003_structure_gold_current.json",
    ),
    WindowSpec(
        slot="06_B05_fanren",
        title="凡人修仙传·第30章／U0030",
        blind_relative_path=(
            "06_B05_fanren/03_unzipped_normalized/02_blind_candidate.json"
        ),
        pointer_relative_path="Z74B_B05_U0030_structure_gold_current.json",
    ),
)


@dataclass(frozen=True)
class BuildResult:
    artifacts: dict[str, bytes]
    summary: dict[str, Any]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_jsonl_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    ).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Z99MiningError(f"缺少输入文件：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Z99MiningError(f"输入不是有效 UTF-8 JSON：{path}") from exc
    if not isinstance(value, dict):
        raise Z99MiningError(f"输入顶层必须是对象：{path}")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Z99MiningError(f"{field} 必须是非空字符串")
    return value


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise Z99MiningError(f"路径不在仓库内：{path}") from exc


def _resolve_repo_path(repo_root: Path, relative_path: str, field: str) -> Path:
    candidate = repo_root / _require_string(relative_path, field)
    _repo_relative(candidate, repo_root)
    return candidate


def normalize_claim(value: str) -> str:
    """固定 claim 归一化：NFKC、casefold，只保留 Unicode 字母和数字。"""

    if not isinstance(value, str):
        raise Z99MiningError("claim 必须是字符串")
    folded = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in folded
        if unicodedata.category(character)[:1] in {"L", "N"}
    )


def character_ngram_set(value: str, width: int) -> frozenset[str]:
    if width <= 0:
        raise Z99MiningError("字符 n-gram 宽度必须大于 0")
    if not value:
        return frozenset()
    if len(value) < width:
        return frozenset({value})
    return frozenset(
        value[index : index + width] for index in range(len(value) - width + 1)
    )


def dice_coefficient(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return 2.0 * len(left & right) / (len(left) + len(right))


def similarity_evidence(blind_claim: str, formal_claim: str) -> dict[str, Any]:
    blind_normalized = normalize_claim(blind_claim)
    formal_normalized = normalize_claim(formal_claim)
    if not blind_normalized:
        raise Z99MiningError("盲产 claim 归一化后为空")
    if not formal_normalized:
        raise Z99MiningError("正式 claim 归一化后为空")

    matcher = difflib.SequenceMatcher(
        None,
        blind_normalized,
        formal_normalized,
        autojunk=False,
    )
    sequence_ratio_raw = matcher.ratio()
    blind_bigrams = character_ngram_set(blind_normalized, 2)
    formal_bigrams = character_ngram_set(formal_normalized, 2)
    blind_trigrams = character_ngram_set(blind_normalized, 3)
    formal_trigrams = character_ngram_set(formal_normalized, 3)
    bigram_dice_raw = dice_coefficient(blind_bigrams, formal_bigrams)
    trigram_dice_raw = dice_coefficient(blind_trigrams, formal_trigrams)
    composite_raw = (
        SEQUENCE_WEIGHT * sequence_ratio_raw
        + BIGRAM_DICE_WEIGHT * bigram_dice_raw
        + TRIGRAM_DICE_WEIGHT * trigram_dice_raw
    )
    matching_blocks = []
    for block in matcher.get_matching_blocks():
        if block.size < 2:
            continue
        matching_blocks.append(
            {
                "blind_start": block.a,
                "formal_start": block.b,
                "length": block.size,
                "normalized_fragment": blind_normalized[block.a : block.a + block.size],
            }
        )
    return {
        "algorithm_version": SIMILARITY_ALGORITHM_VERSION,
        "normalization_version": "unicode-nfkc-casefold-letters-numbers-only-v1",
        "blind_normalized_claim": blind_normalized,
        "formal_normalized_claim": formal_normalized,
        "blind_normalized_char_count": len(blind_normalized),
        "formal_normalized_char_count": len(formal_normalized),
        "sequence_ratio": round(sequence_ratio_raw, SCORE_DECIMAL_PLACES),
        "bigram_dice": round(bigram_dice_raw, SCORE_DECIMAL_PLACES),
        "trigram_dice": round(trigram_dice_raw, SCORE_DECIMAL_PLACES),
        "composite_score": round(composite_raw, SCORE_DECIMAL_PLACES),
        "threshold": SIMILARITY_THRESHOLD,
        "threshold_rule": "candidate_if_rounded_composite_score_strictly_below_threshold",
        "bigram_counts": {
            "blind_unique": len(blind_bigrams),
            "formal_unique": len(formal_bigrams),
            "shared_unique": len(blind_bigrams & formal_bigrams),
        },
        "trigram_counts": {
            "blind_unique": len(blind_trigrams),
            "formal_unique": len(formal_trigrams),
            "shared_unique": len(blind_trigrams & formal_trigrams),
        },
        "blind_is_exact_normalized_substring_of_formal": (
            blind_normalized in formal_normalized
        ),
        "formal_is_exact_normalized_substring_of_blind": (
            formal_normalized in blind_normalized
        ),
        "sequence_matching_blocks_min_length_2": matching_blocks,
    }


def is_surface_candidate(evidence: Mapping[str, Any]) -> bool:
    score = evidence.get("composite_score")
    if not isinstance(score, (int, float)):
        raise Z99MiningError("相似度证据缺少 composite_score")
    return float(score) < SIMILARITY_THRESHOLD


def _extract_part_rows(
    document: Mapping[str, Any],
    *,
    side: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    layered_items = document.get("layered_items")
    if not isinstance(layered_items, list) or not layered_items:
        raise Z99MiningError(f"{side}.layered_items 必须是非空数组")

    rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    seen_group_ids: set[str] = set()
    seen_part_ids: set[str] = set()
    for group_ordinal, item in enumerate(layered_items, start=1):
        if not isinstance(item, dict):
            raise Z99MiningError(f"{side}.layered_items[{group_ordinal}] 不是对象")
        group_id = _require_string(
            item.get("item_id"),
            f"{side}.layered_items[{group_ordinal}].item_id",
        )
        if group_id in seen_group_ids:
            raise Z99MiningError(f"{side} 分组 ID 重复：{group_id}")
        seen_group_ids.add(group_id)
        parts = item.get("parts")
        if not isinstance(parts, list) or not parts:
            raise Z99MiningError(f"{side} 分组 {group_id} 的 parts 必须是非空数组")
        groups.append(
            {
                "group_ordinal": group_ordinal,
                "group_id": group_id,
                "part_count": len(parts),
            }
        )
        for part_ordinal, part in enumerate(parts, start=1):
            if not isinstance(part, dict):
                raise Z99MiningError(
                    f"{side} 分组 {group_id} 第 {part_ordinal} 条不是对象"
                )
            part_id = _require_string(
                part.get("part_id"),
                f"{side}.{group_id}.parts[{part_ordinal}].part_id",
            )
            claim = _require_string(
                part.get("claim"),
                f"{side}.{group_id}.{part_id}.claim",
            )
            if part_id in seen_part_ids:
                raise Z99MiningError(f"{side} 条目 ID 重复：{part_id}")
            seen_part_ids.add(part_id)
            if not normalize_claim(claim):
                raise Z99MiningError(f"{side} 条目 {part_id} 的 claim 归一化后为空")
            rows.append(
                {
                    "group_ordinal": group_ordinal,
                    "group_id": group_id,
                    "part_ordinal": part_ordinal,
                    "part_id": part_id,
                    "claim": claim,
                    "row": copy.deepcopy(part),
                }
            )
    return rows, groups


def _distribution(part_counts: Sequence[int]) -> dict[str, Any]:
    if not part_counts:
        raise Z99MiningError("分组颗粒度统计不能为空")
    return {
        "part_counts_in_group_order": list(part_counts),
        "minimum": min(part_counts),
        "maximum": max(part_counts),
        "mean": round(statistics.fmean(part_counts), SCORE_DECIMAL_PLACES),
        "median": round(float(statistics.median(part_counts)), SCORE_DECIMAL_PLACES),
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise Z99MiningError("颗粒度比值的分母必须大于 0")
    return round(numerator / denominator, SCORE_DECIMAL_PLACES)


def _nearest_formal(
    blind_row: Mapping[str, Any],
    formal_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not formal_rows:
        raise Z99MiningError("正式金标没有可比较条目")
    scored: list[tuple[float, str, str, dict[str, Any], dict[str, Any]]] = []
    for formal_row in formal_rows:
        evidence = similarity_evidence(
            _require_string(blind_row.get("claim"), "blind.claim"),
            _require_string(formal_row.get("claim"), "formal.claim"),
        )
        scored.append(
            (
                float(evidence["composite_score"]),
                _require_string(formal_row.get("part_id"), "formal.part_id"),
                _require_string(formal_row.get("group_id"), "formal.group_id"),
                dict(formal_row),
                evidence,
            )
        )
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    return scored[0][3], scored[0][4]


def _validate_declared_sha(path: Path, declared: Any, field: str) -> str:
    expected = _require_string(declared, field)
    actual = sha256_file(path)
    if actual != expected:
        raise Z99MiningError(
            f"SHA 不一致：{field} 声明 {expected}，实际 {actual}，文件 {path}"
        )
    return actual


def _registry_entry_map(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise Z99MiningError("formal_gold_registry.entries 必须是数组")
    result: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise Z99MiningError(f"formal_gold_registry.entries[{index}] 不是对象")
        pointer_path = _require_string(
            entry.get("pointer_path"),
            f"formal_gold_registry.entries[{index}].pointer_path",
        )
        if pointer_path in result:
            raise Z99MiningError(f"正式登记重复 pointer_path：{pointer_path}")
        result[pointer_path] = entry
    return result


def _blind_manifest_entry_map(
    manifest: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    books = manifest.get("books")
    if not isinstance(books, list):
        raise Z99MiningError("盲产回包 manifest.books 必须是数组")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(books, start=1):
        if not isinstance(row, dict):
            raise Z99MiningError(f"盲产回包 manifest.books[{index}] 不是对象")
        slot = _require_string(row.get("slot"), f"manifest.books[{index}].slot")
        if slot in result:
            raise Z99MiningError(f"盲产回包 manifest 的 slot 重复：{slot}")
        result[slot] = row
    return result


def _declared_blind_candidate_sha(entry: Mapping[str, Any], slot: str) -> str:
    extracted = entry.get("extracted")
    if not isinstance(extracted, list):
        raise Z99MiningError(f"{slot}.extracted 必须是数组")
    candidates = [
        row
        for row in extracted
        if isinstance(row, dict) and row.get("normalized") == "02_blind_candidate.json"
    ]
    if len(candidates) != 1:
        raise Z99MiningError(
            f"{slot} 必须恰好声明一份 normalized=02_blind_candidate.json"
        )
    return _require_string(candidates[0].get("sha256"), f"{slot}.candidate.sha256")


def comparison_contract() -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_VERSION,
        "task": "Z99_EXTERNAL_FINALIZATION_SUPPLY_ITEM_1",
        "mode": {
            "api_calls": 0,
            "network_attempts": 0,
            "model_calls": 0,
            "novel_body_reads": 0,
            "input_mode": "existing_json_only",
        },
        "selection": {
            "blind_source": (
                "TEMP/gold_blind_produce_returns_20260724 六个固定 slot 的"
                " 03_unzipped_normalized/02_blind_candidate.json"
            ),
            "formal_source": (
                "config/gold 六个固定 *_current.json 的 active_gold.path"
            ),
            "formal_registry_role": (
                "只做六指针与 SHA 交叉验收，不替代 current 指针选材"
            ),
            "blind_rows": "layered_items[].parts[] 的全部对象",
            "formal_rows": (
                "active gold layered_items[].parts[] 的全部对象，包含当章计分条"
                "与回看条；不按层过滤"
            ),
            "comparison_field": "claim only",
            "group_alignment": "none",
        },
        "normalization": {
            "version": "unicode-nfkc-casefold-letters-numbers-only-v1",
            "ordered_steps": [
                "Unicode NFKC",
                "Unicode casefold",
                "只保留 Unicode 类别首字母为 L 或 N 的字符",
            ],
            "removed": "空白、标点、符号及其他非字母数字字符",
            "traditional_simplified_conversion": False,
            "synonym_rewrite": False,
            "word_segmentation": False,
            "semantic_embedding": False,
        },
        "similarity": {
            "algorithm_version": SIMILARITY_ALGORITHM_VERSION,
            "sequence_ratio": {
                "implementation": "difflib.SequenceMatcher",
                "autojunk": False,
                "weight": SEQUENCE_WEIGHT,
            },
            "character_bigram_dice": {
                "collection": "unique set, not multiset",
                "weight": BIGRAM_DICE_WEIGHT,
            },
            "character_trigram_dice": {
                "collection": "unique set, not multiset",
                "weight": TRIGRAM_DICE_WEIGHT,
            },
            "formula": ("0.45*sequence_ratio + 0.35*bigram_dice + 0.20*trigram_dice"),
            "score_decimal_places": SCORE_DECIMAL_PLACES,
            "rounding": "Python round applied once to composite score",
            "nearest_tie_break": (
                "composite_score descending, then formal part_id ascending, "
                "then formal group_id ascending"
            ),
        },
        "candidate_gate": {
            "threshold": SIMILARITY_THRESHOLD,
            "operator": "rounded_composite_score < threshold",
            "status": CANDIDATE_STATUS,
            "meaning": (
                "固定 claim 词面算法下未找到达到阈值的现役正式条，"
                "只进入人工语义复核候选池"
            ),
            "not_allowed_inference": [
                "不得称为语义漏项",
                "不得称为正式金标错误",
                "不得自动升金或修改 current",
                "不得把阈值解释为经过人工语义校准的精度界线",
            ],
            "threshold_calibration_status": (
                "screening_constant_not_semantically_calibrated"
            ),
        },
        "evidence_retention": {
            "blind_row": "逐条原样保留",
            "nearest_formal_row": "逐条原样保留",
            "similarity": [
                "两边归一化 claim",
                "三个分项分数与加权总分",
                "二元和三元字符集合计数",
                "长度至少为 2 的 SequenceMatcher 匹配块",
                "双向精确归一化子串标记",
            ],
        },
        "determinism": {
            "runtime_timestamp_in_outputs": False,
            "input_order": "WINDOW_SPECS order, then JSON group and part order",
            "json_object_keys": "sorted",
            "json_encoding": "UTF-8, ensure_ascii=false, LF",
            "output_manifest_self_hash": (
                "output_manifest.json lists every generated artifact except itself"
            ),
        },
    }


def _collect_inputs(
    repo_root: Path,
    blind_root: Path,
    gold_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repo_root = repo_root.resolve()
    blind_root = blind_root.resolve()
    gold_root = gold_root.resolve()
    _repo_relative(blind_root, repo_root)
    _repo_relative(gold_root, repo_root)

    blind_manifest_path = blind_root / "manifest.json"
    blind_manifest = _read_json(blind_manifest_path)
    blind_manifest_entries = _blind_manifest_entry_map(blind_manifest)
    if set(blind_manifest_entries) != {spec.slot for spec in WINDOW_SPECS}:
        raise Z99MiningError("盲产回包 manifest 的六个 slot 与固定合同不一致")

    registry_path = gold_root / "formal_gold_registry.json"
    registry = _read_json(registry_path)
    registry_entries = _registry_entry_map(registry)
    expected_registry_paths = {
        f"config/gold/{spec.pointer_relative_path}" for spec in WINDOW_SPECS
    }
    if set(registry_entries) != expected_registry_paths:
        raise Z99MiningError("正式金标登记的六个 pointer_path 与固定合同不一致")

    discovered_current = {
        path.name for path in gold_root.glob("*_current.json") if path.is_file()
    }
    expected_current = {spec.pointer_relative_path for spec in WINDOW_SPECS}
    if discovered_current != expected_current:
        raise Z99MiningError(
            "config/gold 的 current 文件集合与固定六窗合同不一致："
            f"expected={sorted(expected_current)} actual={sorted(discovered_current)}"
        )

    windows: list[dict[str, Any]] = []
    for spec in WINDOW_SPECS:
        blind_path = blind_root / spec.blind_relative_path
        blind_document = _read_json(blind_path)
        blind_entry = blind_manifest_entries[spec.slot]
        if blind_entry.get("not_active_gold") is not True:
            raise Z99MiningError(f"{spec.slot} 没有明确 not_active_gold=true")
        if blind_document.get("status") != "blind_produce_candidate_not_active":
            raise Z99MiningError(f"{spec.slot} 的盲产候选状态不是未启用")
        blind_sha = _validate_declared_sha(
            blind_path,
            _declared_blind_candidate_sha(blind_entry, spec.slot),
            f"{spec.slot}.manifest candidate sha256",
        )

        pointer_path = gold_root / spec.pointer_relative_path
        pointer = _read_json(pointer_path)
        active_gold = pointer.get("active_gold")
        if not isinstance(active_gold, dict):
            raise Z99MiningError(f"{spec.pointer_relative_path}.active_gold 不是对象")
        artifact_path = _resolve_repo_path(
            repo_root,
            _require_string(
                active_gold.get("path"),
                f"{spec.pointer_relative_path}.active_gold.path",
            ),
            f"{spec.pointer_relative_path}.active_gold.path",
        )
        artifact = _read_json(artifact_path)
        artifact_sha = _validate_declared_sha(
            artifact_path,
            active_gold.get("sha256"),
            f"{spec.pointer_relative_path}.active_gold.sha256",
        )
        if artifact.get("status") != "active_gold":
            raise Z99MiningError(f"{artifact_path} 不是 active_gold")

        pointer_repo_path = _repo_relative(pointer_path, repo_root)
        registry_entry = registry_entries[pointer_repo_path]
        pointer_sha = _validate_declared_sha(
            pointer_path,
            registry_entry.get("pointer_sha256"),
            f"{pointer_repo_path}.registry pointer_sha256",
        )
        if registry_entry.get("artifact_path") != _repo_relative(
            artifact_path, repo_root
        ):
            raise Z99MiningError(
                f"{pointer_repo_path} 与 registry artifact_path 不一致"
            )
        if registry_entry.get("artifact_sha256") != artifact_sha:
            raise Z99MiningError(
                f"{pointer_repo_path} 与 registry artifact_sha256 不一致"
            )
        if registry_entry.get("gold_id") != artifact.get("gold_id"):
            raise Z99MiningError(f"{pointer_repo_path} 与 registry gold_id 不一致")

        blind_rows, blind_groups = _extract_part_rows(
            blind_document,
            side=f"{spec.slot}.blind",
        )
        formal_rows, formal_groups = _extract_part_rows(
            artifact,
            side=f"{spec.slot}.formal",
        )
        windows.append(
            {
                "spec": spec,
                "blind_path": blind_path,
                "blind_sha256": blind_sha,
                "blind_document": blind_document,
                "blind_rows": blind_rows,
                "blind_groups": blind_groups,
                "pointer_path": pointer_path,
                "pointer_sha256": pointer_sha,
                "pointer": pointer,
                "artifact_path": artifact_path,
                "artifact_sha256": artifact_sha,
                "artifact": artifact,
                "formal_rows": formal_rows,
                "formal_groups": formal_groups,
            }
        )

    provenance = {
        "blind_manifest": {
            "path": _repo_relative(blind_manifest_path, repo_root),
            "sha256": sha256_file(blind_manifest_path),
            "declared_model_api_calls": blind_manifest.get("model_api_calls"),
        },
        "formal_gold_registry": {
            "path": _repo_relative(registry_path, repo_root),
            "sha256": sha256_file(registry_path),
            "entry_total": len(registry_entries),
        },
    }
    return windows, provenance


def _build_candidate_rows(
    windows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    window_summaries: list[dict[str, Any]] = []
    for window in windows:
        spec = window["spec"]
        if not isinstance(spec, WindowSpec):
            raise Z99MiningError("内部窗口 spec 类型错误")
        blind_rows = window["blind_rows"]
        formal_rows = window["formal_rows"]
        if not isinstance(blind_rows, list) or not isinstance(formal_rows, list):
            raise Z99MiningError("内部窗口 rows 类型错误")
        window_candidate_total = 0
        comparison_total = 0
        closest_scores: list[float] = []
        for blind_row in blind_rows:
            nearest, evidence = _nearest_formal(blind_row, formal_rows)
            comparison_total += len(formal_rows)
            closest_scores.append(float(evidence["composite_score"]))
            if not is_surface_candidate(evidence):
                continue
            window_candidate_total += 1
            candidates.append(
                {
                    "schema_version": ROW_SCHEMA_VERSION,
                    "candidate_id": f"{spec.slot}::{blind_row['part_id']}",
                    "status": CANDIDATE_STATUS,
                    "semantic_review_status": "pending_not_performed",
                    "semantic_verdict": None,
                    "window": {
                        "slot": spec.slot,
                        "title": spec.title,
                        "blind_gold_id": window["blind_document"].get("gold_id"),
                        "active_formal_gold_id": window["artifact"].get("gold_id"),
                    },
                    "candidate_reason": (
                        "nearest_formal_surface_similarity_strictly_below_threshold"
                    ),
                    "blind_location": {
                        "group_ordinal": blind_row["group_ordinal"],
                        "group_id": blind_row["group_id"],
                        "part_ordinal": blind_row["part_ordinal"],
                        "part_id": blind_row["part_id"],
                    },
                    "blind_row": copy.deepcopy(blind_row["row"]),
                    "nearest_formal_location": {
                        "group_ordinal": nearest["group_ordinal"],
                        "group_id": nearest["group_id"],
                        "part_ordinal": nearest["part_ordinal"],
                        "part_id": nearest["part_id"],
                    },
                    "nearest_formal_row": copy.deepcopy(nearest["row"]),
                    "similarity_evidence": evidence,
                    "boundary": {
                        "mechanical_surface_difference_only": True,
                        "semantic_missing_item_claimed": False,
                        "formal_gold_change_allowed": False,
                        "current_pointer_change_allowed": False,
                    },
                }
            )
        window_summaries.append(
            {
                "slot": spec.slot,
                "title": spec.title,
                "blind_part_total": len(blind_rows),
                "formal_part_total_all_layers": len(formal_rows),
                "pairwise_comparison_total": comparison_total,
                "candidate_total": window_candidate_total,
                "not_in_candidate_pool_total": len(blind_rows) - window_candidate_total,
                "candidate_rate_of_blind_parts": round(
                    window_candidate_total / len(blind_rows),
                    SCORE_DECIMAL_PLACES,
                ),
                "nearest_score_minimum": min(closest_scores),
                "nearest_score_maximum": max(closest_scores),
                "nearest_score_mean": round(
                    statistics.fmean(closest_scores),
                    SCORE_DECIMAL_PLACES,
                ),
                "nearest_score_median": round(
                    float(statistics.median(closest_scores)),
                    SCORE_DECIMAL_PLACES,
                ),
            }
        )
    return candidates, window_summaries


def _granularity_rows(
    windows: Sequence[Mapping[str, Any]],
    candidate_summaries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_slot = {row["slot"]: row for row in candidate_summaries}
    rows: list[dict[str, Any]] = []
    for window in windows:
        spec = window["spec"]
        if not isinstance(spec, WindowSpec):
            raise Z99MiningError("内部窗口 spec 类型错误")
        blind_groups = window["blind_groups"]
        formal_groups = window["formal_groups"]
        blind_rows = window["blind_rows"]
        formal_rows = window["formal_rows"]
        blind_part_counts = [int(row["part_count"]) for row in blind_groups]
        formal_part_counts = [int(row["part_count"]) for row in formal_groups]
        formal_scoreable_total = sum(
            row["row"].get("score_in_single_chapter") is True for row in formal_rows
        )
        rows.append(
            {
                "slot": spec.slot,
                "title": spec.title,
                "grouping": {
                    "blind_container": "layered_items[].parts[]",
                    "formal_container": "layered_items[].parts[]",
                    "group_alignment_performed": False,
                    "interpretation": (
                        "只按两边各自已有 item_id 统计，不推断两边分组语义等价"
                    ),
                },
                "blind": {
                    "group_total": len(blind_groups),
                    "part_total": len(blind_rows),
                    "parts_per_group": _distribution(blind_part_counts),
                },
                "formal": {
                    "group_total": len(formal_groups),
                    "part_total_all_layers": len(formal_rows),
                    "part_total_scoreable_single_chapter": formal_scoreable_total,
                    "part_total_other_layers": len(formal_rows)
                    - formal_scoreable_total,
                    "parts_per_group_all_layers": _distribution(formal_part_counts),
                },
                "mechanical_ratios": {
                    "blind_parts_per_formal_part_all_layers": _ratio(
                        len(blind_rows), len(formal_rows)
                    ),
                    "blind_parts_per_formal_scoreable_part": _ratio(
                        len(blind_rows), formal_scoreable_total
                    ),
                    "blind_groups_per_formal_group": _ratio(
                        len(blind_groups), len(formal_groups)
                    ),
                },
                "surface_candidate_total": candidate_by_slot[spec.slot][
                    "candidate_total"
                ],
                "boundary": (
                    "条数和分组大小只标定机械颗粒度，不代表覆盖率、召回率或语义优劣"
                ),
            }
        )
    return rows


def _granularity_markdown(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Z99 件1｜六窗条数与分组颗粒度标定",
        "",
        "> 这张表只数 JSON 里的分组和条目，不判断哪边更完整，也不把机械差异叫作语义漏项。",
        "",
        "| 窗口 | 盲产组 | 盲产条 | 正式组 | 正式全部条 | 正式当章计分条 | 盲产／正式全部条 | 表面候选条 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {title} | {blind_groups} | {blind_parts} | {formal_groups} | "
            "{formal_all} | {formal_scoreable} | {ratio:.6f} | {candidate_total} |".format(
                title=row["title"],
                blind_groups=row["blind"]["group_total"],
                blind_parts=row["blind"]["part_total"],
                formal_groups=row["formal"]["group_total"],
                formal_all=row["formal"]["part_total_all_layers"],
                formal_scoreable=row["formal"]["part_total_scoreable_single_chapter"],
                ratio=row["mechanical_ratios"][
                    "blind_parts_per_formal_part_all_layers"
                ],
                candidate_total=row["surface_candidate_total"],
            )
        )
    lines.extend(
        [
            "",
            "分组口径：两边都按 `layered_items[].parts[]` 读取；每个 "
            "`layered_items` 对象算一组。两边的 `item_id` 没有做强行对齐。",
            "",
            "更细的每组条数、均值、中位数和比值在 `granularity_calibration.json`。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def _totals(
    windows: Sequence[Mapping[str, Any]],
    candidate_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "window_total": len(windows),
        "blind_group_total": sum(len(window["blind_groups"]) for window in windows),
        "blind_part_total": sum(len(window["blind_rows"]) for window in windows),
        "formal_group_total": sum(len(window["formal_groups"]) for window in windows),
        "formal_part_total_all_layers": sum(
            len(window["formal_rows"]) for window in windows
        ),
        "formal_part_total_scoreable_single_chapter": sum(
            row["row"].get("score_in_single_chapter") is True
            for window in windows
            for row in window["formal_rows"]
        ),
        "pairwise_comparison_total": sum(
            int(row["pairwise_comparison_total"]) for row in candidate_summaries
        ),
        "candidate_total": sum(
            int(row["candidate_total"]) for row in candidate_summaries
        ),
        "not_in_candidate_pool_total": sum(
            int(row["not_in_candidate_pool_total"]) for row in candidate_summaries
        ),
    }


def _input_manifest(
    repo_root: Path,
    windows: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    rows = []
    for window in windows:
        spec = window["spec"]
        if not isinstance(spec, WindowSpec):
            raise Z99MiningError("内部窗口 spec 类型错误")
        rows.append(
            {
                "slot": spec.slot,
                "title": spec.title,
                "blind_candidate": {
                    "path": _repo_relative(window["blind_path"], repo_root),
                    "sha256": window["blind_sha256"],
                    "blind_gold_id": window["blind_document"].get("gold_id"),
                    "status": window["blind_document"].get("status"),
                },
                "formal_current_pointer": {
                    "path": _repo_relative(window["pointer_path"], repo_root),
                    "sha256": window["pointer_sha256"],
                    "pointer_id": window["pointer"].get("pointer_id"),
                },
                "formal_active_artifact": {
                    "path": _repo_relative(window["artifact_path"], repo_root),
                    "sha256": window["artifact_sha256"],
                    "declared_pointer_sha256": window["pointer"]["active_gold"].get(
                        "sha256"
                    ),
                    "gold_id": window["artifact"].get("gold_id"),
                    "status": window["artifact"].get("status"),
                },
            }
        )
    return {
        "schema_version": "z99-blind-gold-input-manifest-v1",
        "selection_source": "six_fixed_current_pointers",
        "window_total": len(rows),
        "cross_checks": copy.deepcopy(provenance),
        "windows": rows,
    }


def _artifact_entries(artifacts: Mapping[str, bytes]) -> list[dict[str, Any]]:
    return [
        {
            "path": name,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
        }
        for name, raw in sorted(artifacts.items())
    ]


def _artifact_set_sha(entries: Sequence[Mapping[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(list(entries)))


def _readme(
    totals: Mapping[str, Any],
    window_summaries: Sequence[Mapping[str, Any]],
    key_shas: Mapping[str, str],
) -> str:
    lines = [
        "# Z99 件1｜六本盲产与现役金标的离线表面差异池",
        "",
        "✅ 结论：六窗一共读到 {blind_parts} 条盲产条、{formal_parts} 条现役"
        "正式条；固定词面算法筛出 {candidate_total} 条待人工语义复核候选。".format(
            blind_parts=totals["blind_part_total"],
            formal_parts=totals["formal_part_total_all_layers"],
            candidate_total=totals["candidate_total"],
        ),
        "",
        "🔥 这些候选不是“金标漏项”。它只说明：拿盲产条的 `claim` 与同窗"
        "全部现役正式条的 `claim` 做固定字符相似度比较时，最高分仍低于 "
        f"`{SIMILARITY_THRESHOLD:.6f}`。有没有语义重复、普通动作噪声、错事实"
        "或真正值得补充的结构点，仍要人工逐条审。",
        "",
        "## 六窗计数",
        "",
        "| 窗口 | 盲产条 | 正式全部条 | 表面候选条 | 未进候选池 |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in window_summaries:
        lines.append(
            "| {title} | {blind_part_total} | {formal_part_total_all_layers} | "
            "{candidate_total} | {not_in_candidate_pool_total} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 文件怎么读",
            "",
            "- `candidate_surface_uncovered_pending_semantic_review.jsonl`：逐条"
            "候选池。每行保留盲产原条、同窗最近正式原条、归一化文本、三个"
            "分项分数、总分和匹配块。",
            "- `granularity_calibration.md`：人看的六窗条数与分组颗粒度表。",
            "- `granularity_calibration.json`：机器可读的分组条数、均值、中位数"
            "和机械比值。",
            "- `comparison_contract.json`：归一化、公式、阈值、并列处理和禁止推论。",
            "- `input_manifest.json`：六份盲产输入、六个 current 指针、current "
            "所指正式件的 SHA。",
            "- `mechanical_acceptance.json`：零调用、数量、状态和证据保留检查。",
            "- `output_manifest.json`：除它自己外的全部生成文件 SHA；避免自哈希递归。",
            "",
            "## 这次固定的比较规则",
            "",
            "只比较 `claim`。文本先做 Unicode NFKC、忽略大小写，再去掉空白、"
            "标点和符号，只留下字母与数字。总分＝顺序相似度 45%＋二元字符 "
            "Dice 35%＋三元字符 Dice 20%，保留 6 位小数后，严格小于 "
            f"`{SIMILARITY_THRESHOLD:.6f}` 才进池。",
            "",
            "这个阈值只是离线筛查常量，没有经过人工语义精度标定。正式条会"
            "把当章计分条和回看条都纳入最近邻比较，不做跨窗比较，也不强行"
            "对齐两边分组。",
            "",
            "## 关键 SHA",
            "",
            f"- 候选池：`{key_shas['candidate_pool']}`",
            f"- 输入清单：`{key_shas['input_manifest']}`",
            f"- 比较合同：`{key_shas['contract']}`",
            f"- 颗粒度 JSON：`{key_shas['granularity_json']}`",
            "",
            "全程 0 API、0 网络、0 模型调用、0 正文读取；没有改正式金标、"
            "current、治理、决策、运行或回包目录。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build_artifacts(
    *,
    repo_root: Path = ROOT,
    blind_root: Path | None = None,
    gold_root: Path | None = None,
) -> BuildResult:
    repo_root = repo_root.resolve()
    blind_root = (
        blind_root or repo_root / DEFAULT_BLIND_ROOT.relative_to(ROOT)
    ).resolve()
    gold_root = (gold_root or repo_root / DEFAULT_GOLD_ROOT.relative_to(ROOT)).resolve()
    windows, provenance = _collect_inputs(repo_root, blind_root, gold_root)
    candidates, window_summaries = _build_candidate_rows(windows)
    granularity_rows = _granularity_rows(windows, window_summaries)
    totals = _totals(windows, window_summaries)
    if len(candidates) != totals["candidate_total"]:
        raise Z99MiningError("候选池条数与汇总不一致")
    if totals["blind_part_total"] != (
        totals["candidate_total"] + totals["not_in_candidate_pool_total"]
    ):
        raise Z99MiningError("盲产总条数没有被候选与非候选完整分割")

    artifacts: dict[str, bytes] = {}
    artifacts["comparison_contract.json"] = canonical_json_bytes(comparison_contract())
    artifacts["candidate_surface_uncovered_pending_semantic_review.jsonl"] = (
        canonical_jsonl_bytes(candidates)
    )
    artifacts["input_manifest.json"] = canonical_json_bytes(
        _input_manifest(repo_root, windows, provenance)
    )
    artifacts["granularity_calibration.json"] = canonical_json_bytes(
        {
            "schema_version": "z99-blind-gold-granularity-calibration-v1",
            "boundary": (
                "机械条数与分组颗粒度，不是覆盖率、召回率、语义优劣或漏项判定"
            ),
            "group_counting_rule": (
                "layered_items 中每个对象算一组；该对象 parts 中每个对象算一条"
            ),
            "rows": granularity_rows,
            "totals": totals,
        }
    )
    artifacts["granularity_calibration.md"] = _granularity_markdown(
        granularity_rows
    ).encode("utf-8")
    candidate_pool_sha = sha256_bytes(
        artifacts["candidate_surface_uncovered_pending_semantic_review.jsonl"]
    )
    artifacts["candidate_pool_summary.json"] = canonical_json_bytes(
        {
            "schema_version": "z99-blind-gold-candidate-pool-summary-v1",
            "status": CANDIDATE_STATUS,
            "boundary": (
                "surface screening only; semantic review not performed; "
                "not a formal-gold omission verdict"
            ),
            "contract_version": CONTRACT_VERSION,
            "algorithm_version": SIMILARITY_ALGORITHM_VERSION,
            "threshold": SIMILARITY_THRESHOLD,
            "candidate_rows_path": (
                "candidate_surface_uncovered_pending_semantic_review.jsonl"
            ),
            "candidate_rows_sha256": candidate_pool_sha,
            "windows": window_summaries,
            "totals": totals,
        }
    )
    key_shas = {
        "candidate_pool": candidate_pool_sha,
        "input_manifest": sha256_bytes(artifacts["input_manifest.json"]),
        "contract": sha256_bytes(artifacts["comparison_contract.json"]),
        "granularity_json": sha256_bytes(artifacts["granularity_calibration.json"]),
    }
    artifacts["README.md"] = _readme(
        totals,
        window_summaries,
        key_shas,
    ).encode("utf-8")

    core_entries = _artifact_entries(artifacts)
    acceptance = {
        "schema_version": "z99-blind-gold-mechanical-acceptance-v1",
        "status": "PASS",
        "scope": "offline_surface_difference_mining_only",
        "checks": {
            "fixed_window_total_is_6": totals["window_total"] == 6,
            "all_blind_rows_compared": totals["blind_part_total"] > 0,
            "all_current_artifact_shas_match": True,
            "blind_manifest_candidate_shas_match": True,
            "formal_registry_pointer_shas_match": True,
            "candidate_rows_all_keep_nearest_formal_row": all(
                row.get("nearest_formal_row")
                and row.get("nearest_formal_location")
                and row.get("similarity_evidence")
                for row in candidates
            ),
            "candidate_rows_all_use_exact_pending_status": all(
                row.get("status") == CANDIDATE_STATUS for row in candidates
            ),
            "candidate_rows_all_strictly_below_threshold": all(
                is_surface_candidate(row["similarity_evidence"]) for row in candidates
            ),
            "candidate_plus_non_candidate_equals_blind_total": (
                totals["candidate_total"] + totals["not_in_candidate_pool_total"]
                == totals["blind_part_total"]
            ),
            "semantic_review_performed": False,
            "formal_gold_changed": False,
            "current_pointer_changed": False,
        },
        "usage": {
            "model_api_logical_samples": 0,
            "model_api_network_attempts": 0,
            "model_api_usage_tokens": 0,
            "network_requests": 0,
            "novel_body_read_count": 0,
        },
        "determinism_controls": {
            "runtime_timestamp_in_outputs": False,
            "sorted_json_keys": True,
            "fixed_window_order": True,
            "fixed_tie_break": True,
            "cli_builds_twice_in_memory_before_write": True,
        },
        "totals": totals,
        "core_artifact_entries": core_entries,
        "core_artifact_set_sha256": _artifact_set_sha(core_entries),
        "boundary": (
            "PASS 只证明输入身份、机械计数、阈值执行、证据保留和零调用；"
            "不证明候选为真、不证明正式金标漏项、不准升金。"
        ),
    }
    positive_check_names = (
        "fixed_window_total_is_6",
        "all_blind_rows_compared",
        "all_current_artifact_shas_match",
        "blind_manifest_candidate_shas_match",
        "formal_registry_pointer_shas_match",
        "candidate_rows_all_keep_nearest_formal_row",
        "candidate_rows_all_use_exact_pending_status",
        "candidate_rows_all_strictly_below_threshold",
        "candidate_plus_non_candidate_equals_blind_total",
    )
    if not all(acceptance["checks"][name] for name in positive_check_names):
        raise Z99MiningError("机械验收布尔检查没有全部通过")
    if any(
        acceptance["checks"][name]
        for name in (
            "semantic_review_performed",
            "formal_gold_changed",
            "current_pointer_changed",
        )
    ):
        raise Z99MiningError("保护项出现越权变更")
    artifacts["mechanical_acceptance.json"] = canonical_json_bytes(acceptance)

    output_entries = _artifact_entries(artifacts)
    artifacts["output_manifest.json"] = canonical_json_bytes(
        {
            "schema_version": "z99-blind-gold-output-manifest-v1",
            "self_hash_policy": (
                "本文件列出其他全部生成文件，不列自身，避免递归自哈希"
            ),
            "generated_artifact_total_excluding_self": len(output_entries),
            "entries": output_entries,
            "artifact_set_sha256": _artifact_set_sha(output_entries),
        }
    )
    summary = {
        **totals,
        "candidate_status": CANDIDATE_STATUS,
        "threshold": SIMILARITY_THRESHOLD,
        "output_artifact_total": len(artifacts),
        "output_manifest_sha256": sha256_bytes(artifacts["output_manifest.json"]),
        "deterministic_in_memory_double_build_required": True,
    }
    return BuildResult(artifacts=artifacts, summary=summary)


def _write_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, raw in sorted(artifacts.items()):
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def _check_artifacts(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    mismatches: list[str] = []
    for relative_path, expected in sorted(artifacts.items()):
        path = output_dir / relative_path
        if not path.is_file():
            mismatches.append(f"missing:{relative_path}")
            continue
        actual = path.read_bytes()
        if actual != expected:
            mismatches.append(
                f"mismatch:{relative_path}:expected={sha256_bytes(expected)}:"
                f"actual={sha256_bytes(actual)}"
            )
    if mismatches:
        raise Z99MiningError("输出回读不一致：" + "；".join(mismatches))


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="零调用比较六份盲产候选与 current 指向的六份正式金标"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="仓库根目录；默认取脚本上一级",
    )
    parser.add_argument(
        "--blind-root",
        type=Path,
        default=None,
        help="盲产回包根目录；默认取仓库 TEMP 固定目录",
    )
    parser.add_argument(
        "--gold-root",
        type=Path,
        default=None,
        help="正式金标指针目录；默认取仓库 config/gold",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录；默认取 Z99 实验的 blind_mining",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="只回读核对现有产物，不写文件",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="只在内存双构建，不写文件",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    blind_root = args.blind_root.resolve() if args.blind_root else None
    gold_root = args.gold_root.resolve() if args.gold_root else None
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else repo_root
        / "experiments/Z99_external_finalization_supply_20260724/blind_mining"
    )
    first = build_artifacts(
        repo_root=repo_root,
        blind_root=blind_root,
        gold_root=gold_root,
    )
    second = build_artifacts(
        repo_root=repo_root,
        blind_root=blind_root,
        gold_root=gold_root,
    )
    if first.artifacts != second.artifacts or first.summary != second.summary:
        raise Z99MiningError("同输入的两次内存构建不一致")
    if args.check:
        _check_artifacts(output_dir, first.artifacts)
    elif not args.dry_run:
        _write_artifacts(output_dir, first.artifacts)
        _check_artifacts(output_dir, first.artifacts)
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": (
                    "check"
                    if args.check
                    else "dry_run"
                    if args.dry_run
                    else "write_and_readback"
                ),
                "output_dir": str(output_dir),
                **first.summary,
                "model_api_calls": 0,
                "network_attempts": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
