from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "v02-c11-source-coverage.v1"
RANDOM_FLOOR_TRIALS = 100
RANDOM_FLOOR_SEED = "V02-C11.3-20260725"
RANDOM_FLOOR_ALGORITHM = "sha256_rank_without_replacement.v1"
ARM_ORDER = ("treatment", "control")
STATE_ORDER = (
    "SCORE",
    "CONTEXT_ONLY",
    "STYLE_ONLY",
    "REVIEW",
    "EXCLUDE",
)
SENTENCE_END = frozenset("。！？!?…")
CLOSERS = frozenset("”’」』）》】")
SEPARATOR_ONLY = re.compile(r"^[*＊※—\\-_=~·•…]+$")


class SourceCoverageError(RuntimeError):
    """C11.3 输入漂移或机械合同不成立。"""


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / "experiments").is_dir():
            return candidate
    raise SourceCoverageError("找不到小说架构仓库根目录")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
EXPERIMENT_ROOT = (
    REPO_ROOT / "experiments" / "extraction_redesign_v02_overnight_20260725"
)
C4_ROOT = EXPERIMENT_ROOT / "V02_C4_transport_probe"
SOURCE_MANIFEST = C4_ROOT / "source_manifest.json"
CATALOG_DIR = C4_ROOT / "catalogs"
TREATMENT_RUN = REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C4_r03_20260725"
CONTROL_RUN = REPO_ROOT / "runs" / "V02_实验A锚先行倒装_C6对照臂_r05_20260725"
TASK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = TASK_ROOT / "artifacts"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceCoverageError(f"JSON 读取失败：{path}") from exc


def _nonspace_overlap(
    body: str,
    first: tuple[int, int],
    second: tuple[int, int],
) -> int:
    start = max(first[0], second[0])
    end = min(first[1], second[1])
    if end <= start:
        return 0
    return sum(not body[index].isspace() for index in range(start, end))


def _trim_span(body: str, start: int, end: int) -> tuple[int, int]:
    while start < end and body[start].isspace():
        start += 1
    while end > start and body[end - 1].isspace():
        end -= 1
    return start, end


def segment_source_body(case_id: str, body: str) -> list[dict[str, Any]]:
    """按物理行，再按句末标点切分；输出不携带原文。"""

    units: list[dict[str, Any]] = []
    absolute = 0
    for line_number, raw_line in enumerate(
        body.splitlines(keepends=True),
        start=1,
    ):
        content = raw_line.rstrip("\r\n")
        line_start = absolute
        absolute += len(raw_line)
        content_start, content_end = _trim_span(
            body,
            line_start,
            line_start + len(content),
        )
        if content_start == content_end:
            continue

        segment_start = content_start
        cursor = content_start
        while cursor < content_end:
            character = body[cursor]
            is_ascii_period = character == "." and (
                cursor + 1 == content_end
                or body[cursor + 1].isspace()
                or body[cursor + 1] in CLOSERS
            )
            if character not in SENTENCE_END and not is_ascii_period:
                cursor += 1
                continue

            segment_end = cursor + 1
            while segment_end < content_end and (
                body[segment_end] in SENTENCE_END or body[segment_end] == "."
            ):
                segment_end += 1
            while segment_end < content_end and body[segment_end] in CLOSERS:
                segment_end += 1
            start, end = _trim_span(body, segment_start, segment_end)
            if start < end:
                units.append(
                    _unit_record(
                        case_id=case_id,
                        line_number=line_number,
                        start=start,
                        end=end,
                        text=body[start:end],
                    )
                )
            segment_start = segment_end
            cursor = segment_end

        start, end = _trim_span(body, segment_start, content_end)
        if start < end:
            units.append(
                _unit_record(
                    case_id=case_id,
                    line_number=line_number,
                    start=start,
                    end=end,
                    text=body[start:end],
                )
            )

    for ordinal, unit in enumerate(units, start=1):
        unit["unit_id"] = f"{case_id}-SU-{ordinal:04d}"
        unit["ordinal"] = ordinal
    return units


def _unit_record(
    *,
    case_id: str,
    line_number: int,
    start: int,
    end: int,
    text: str,
) -> dict[str, Any]:
    normalized = re.sub(r"\s+", "", text)
    return {
        "case_id": case_id,
        "line_number": line_number,
        "start_char": start,
        "end_char_exclusive": end,
        "text_sha256": sha256_bytes(text.encode("utf-8")),
        "nonspace_char_count": len(normalized),
        "mechanical_kind": (
            "SEPARATOR_ONLY"
            if normalized and SEPARATOR_ONLY.fullmatch(normalized)
            else "CONTENT_CANDIDATE"
        ),
    }


def load_frozen_sources(
    source_manifest_path: Path = SOURCE_MANIFEST,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = read_json(source_manifest_path)
    if manifest.get("schema_version") != "v02-anchor-first-source-manifest.v1":
        raise SourceCoverageError("C4 source_manifest 版本漂移")
    chapters = manifest.get("chapters")
    if not isinstance(chapters, list) or len(chapters) != 3:
        raise SourceCoverageError("C4 source_manifest 章节数不是 3")

    loaded: dict[str, dict[str, Any]] = {}
    for row in chapters:
        if not isinstance(row, Mapping):
            raise SourceCoverageError("C4 source_manifest 含非对象章节")
        case_id = str(row.get("case_id") or "")
        cache = row.get("chapter_cache")
        heading = row.get("complete_heading")
        if not case_id or not isinstance(cache, Mapping) or not heading:
            raise SourceCoverageError("C4 source_manifest 章节身份不完整")
        if case_id in loaded:
            raise SourceCoverageError(f"C4 source_manifest 重复 case：{case_id}")
        cache_path = Path(str(cache.get("path")))
        if not cache_path.is_file():
            raise SourceCoverageError(f"{case_id} 冻结正文缺失")
        if sha256_file(cache_path) != cache.get("file_sha256"):
            raise SourceCoverageError(f"{case_id} 冻结正文文件 SHA 漂移")
        text = cache_path.read_text(encoding="utf-8")
        actual_heading, separator, raw_body = text.partition("\n")
        if not separator or actual_heading.rstrip("\r") != heading:
            raise SourceCoverageError(f"{case_id} 章头漂移")
        body = raw_body.lstrip("\r\n").strip("\r\n")
        if len(body) != cache.get("body_char_count"):
            raise SourceCoverageError(f"{case_id} 正文字符数漂移")
        if sha256_bytes(body.encode("utf-8")) != cache.get("body_sha256"):
            raise SourceCoverageError(f"{case_id} 正文 SHA 漂移")
        loaded[case_id] = {
            "body": body,
            "body_sha256": cache["body_sha256"],
            "cache_file_sha256": cache["file_sha256"],
            "units": segment_source_body(case_id, body),
        }
    return manifest, loaded


def load_catalog(
    case_id: str,
    *,
    catalog_dir: Path = CATALOG_DIR,
    expected_body_sha256: str,
    body: str | None = None,
) -> dict[str, dict[str, Any]]:
    path = catalog_dir / f"{case_id}.json"
    document = read_json(path)
    if not isinstance(document, Mapping):
        raise SourceCoverageError(f"{case_id} 冻结锚目录顶层不是对象")
    if document.get("case_id") != case_id:
        raise SourceCoverageError(f"{case_id} 冻结锚目录 case 身份漂移")
    if document.get("source_body_sha256") != expected_body_sha256:
        raise SourceCoverageError(f"{case_id} 冻结锚目录正文 SHA 漂移")
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SourceCoverageError(f"{case_id} 冻结锚目录为空")
    if document.get("entry_count") != len(entries):
        raise SourceCoverageError(f"{case_id} 冻结锚目录条数漂移")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise SourceCoverageError(f"{case_id} 锚目录含非对象条目")
        anchor_id = str(entry.get("anchor_id") or "")
        if not anchor_id or anchor_id in result:
            raise SourceCoverageError(f"{case_id} 锚 ID 缺失或重复")
        start = entry.get("body_start_char")
        end = entry.get("body_end_char_exclusive")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or (body is not None and end > len(body))
        ):
            raise SourceCoverageError(f"{case_id}/{anchor_id} 锚偏移非法")
        if body is not None:
            quote = entry.get("quote")
            if not isinstance(quote, str) or body[start:end] != quote:
                raise SourceCoverageError(
                    f"{case_id}/{anchor_id} 锚短引与正文偏移不一致"
                )
        result[anchor_id] = dict(entry)
    return result


def _candidate_path(run_root: Path, case_id: str) -> Path:
    return run_root / "samples" / "main" / case_id / "candidate" / "model_json.json"


def _mechanical_path(run_root: Path, case_id: str) -> Path:
    return run_root / "samples" / "main" / case_id / "mechanical.json"


def _checkpoint_path(run_root: Path, case_id: str, filename: str) -> Path:
    return run_root / "samples" / "main" / case_id / "checkpoint" / filename


def _assistant_content(response: Mapping[str, Any], *, identity: str) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise SourceCoverageError(f"{identity} 响应 choices 结构非法")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, Mapping) else None
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str) or not content.strip():
        raise SourceCoverageError(f"{identity} 响应正文为空")
    return content


def _audit_checkpoint(
    *,
    arm: str,
    case_id: str,
    run_root: Path,
    frozen_request_path: Path,
    expected_body_sha256: str,
    expected_catalog_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    identity = f"{arm}/{case_id}"
    candidate_path = _candidate_path(run_root, case_id)
    mechanical_path = _mechanical_path(run_root, case_id)
    request_path = _checkpoint_path(run_root, case_id, "01_request.json")
    response_path = _checkpoint_path(run_root, case_id, "02_response.json")
    seal_path = _checkpoint_path(run_root, case_id, "05_seal.json")
    required = (
        candidate_path,
        mechanical_path,
        request_path,
        response_path,
        seal_path,
        frozen_request_path,
    )
    if not all(path.is_file() for path in required):
        raise SourceCoverageError(f"{identity} 冻结输入或检查点缺失")

    seal = read_json(seal_path)
    if not isinstance(seal, Mapping):
        raise SourceCoverageError(f"{identity} 检查点封签不是对象")
    refs = seal.get("artifacts")
    if not isinstance(refs, Mapping) or seal.get("sealed") is not True:
        raise SourceCoverageError(f"{identity} 检查点封签字段非法")
    if arm == "treatment":
        expected_schema = "v02-anchor-first-checkpoint-seal.v1"
        expected_contract = "v02-anchor-first-c2-live.v1"
        expected_ref_names = {
            "01_request.json",
            "02_response.json",
            "03_usage.json",
            "04_attempts.json",
        }
    else:
        expected_schema = "v02-c6-control-checkpoint-seal.v1"
        expected_contract = "v02-c6-control-runner.v1"
        expected_ref_names = {
            "01_request.json",
            "02_response.json",
            "03_mechanical.json",
            "04_usage_attempts.json",
        }
    if (
        seal.get("schema_version") != expected_schema
        or seal.get("contract_version") != expected_contract
        or set(refs) != expected_ref_names
    ):
        raise SourceCoverageError(f"{identity} 检查点封签布局漂移")
    checkpoint_dir = seal_path.parent
    for filename, expected_sha in refs.items():
        artifact_path = checkpoint_dir / filename
        if (
            not isinstance(expected_sha, str)
            or not artifact_path.is_file()
            or sha256_file(artifact_path) != expected_sha
        ):
            raise SourceCoverageError(f"{identity} 检查点 {filename} SHA 漂移")
    preimage = {key: value for key, value in seal.items() if key != "checkpoint_id"}
    if seal.get("checkpoint_id") != canonical_sha(preimage):
        raise SourceCoverageError(f"{identity} 检查点封签 ID 不能重建")

    mechanical = read_json(mechanical_path)
    checkpoint_mechanical_sha: str | None = None
    if arm == "treatment":
        if seal.get("mechanical_path") != "../mechanical.json" or seal.get(
            "mechanical_sha256"
        ) != sha256_file(mechanical_path):
            raise SourceCoverageError(f"{identity} 封签外机械票 SHA 漂移")
    else:
        checkpoint_mechanical_path = checkpoint_dir / "03_mechanical.json"
        checkpoint_mechanical_sha = sha256_file(checkpoint_mechanical_path)
        if read_json(checkpoint_mechanical_path) != mechanical:
            raise SourceCoverageError(f"{identity} 封签内外机械票不一致")

    request = read_json(request_path)
    frozen_request = read_json(frozen_request_path)
    prepared_request_path = (
        run_root / "prepared" / "main" / case_id / "request_artifact.json"
    )
    prepared_body_path = run_root / "prepared" / "main" / case_id / "request_body.json"
    prepared_catalog_path = run_root / "prepared" / "catalogs" / f"{case_id}.json"
    frozen_catalog_path = CATALOG_DIR / f"{case_id}.json"
    if (
        not isinstance(request, Mapping)
        or request != frozen_request
        or request_path.read_bytes() != frozen_request_path.read_bytes()
        or not prepared_request_path.is_file()
        or prepared_request_path.read_bytes() != request_path.read_bytes()
        or not prepared_body_path.is_file()
        or read_json(prepared_body_path) != request.get("body")
        or not prepared_catalog_path.is_file()
        or not frozen_catalog_path.is_file()
        or prepared_catalog_path.read_bytes() != frozen_catalog_path.read_bytes()
        or request.get("case_id") != case_id
        or request.get("source_body_sha256") != expected_body_sha256
        or request.get("catalog_sha256") != expected_catalog_sha256
    ):
        raise SourceCoverageError(f"{identity} 请求未绑定 C4 冻结真源")

    response = read_json(response_path)
    candidate = read_json(candidate_path)
    if not isinstance(response, Mapping) or not isinstance(candidate, Mapping):
        raise SourceCoverageError(f"{identity} 响应或候选不是对象")
    content = _assistant_content(response, identity=identity)
    raw_response_path = (
        run_root
        / "samples"
        / "main"
        / case_id
        / "transport"
        / "raw_responses"
        / "attempt01.json"
    )
    if (
        not raw_response_path.is_file()
        or read_json(raw_response_path) != response
        or sha256_file(raw_response_path) != mechanical.get("raw_response_sha256")
    ):
        raise SourceCoverageError(f"{identity} 原始响应未绑定机械票与封签响应")
    try:
        rebuilt_candidate = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SourceCoverageError(f"{identity} 响应正文不是 JSON") from exc
    if rebuilt_candidate != candidate:
        raise SourceCoverageError(f"{identity} 候选不能从封签响应重建")
    if not isinstance(mechanical, Mapping):
        raise SourceCoverageError(f"{identity} 机械票不是对象")
    status = str(mechanical.get("status") or "").lower()
    if (
        status != "pass"
        or mechanical.get("case_id") != case_id
        or sha256_bytes(content.encode("utf-8")) != mechanical.get("content_sha256")
    ):
        raise SourceCoverageError(f"{identity} 候选内容未绑定机械 PASS")

    return dict(candidate), {
        "request_sha256": sha256_file(request_path),
        "request_body_sha256": sha256_file(prepared_body_path),
        "response_sha256": sha256_file(response_path),
        "raw_response_sha256": sha256_file(raw_response_path),
        "seal_sha256": sha256_file(seal_path),
        "candidate_sha256": sha256_file(candidate_path),
        "mechanical_sha256": sha256_file(mechanical_path),
        "checkpoint_mechanical_sha256": checkpoint_mechanical_sha,
        "checkpoint_id": str(seal["checkpoint_id"]),
        "seal_schema_version": str(seal["schema_version"]),
    }


def load_arm_events(
    arm: str,
    case_id: str,
    *,
    treatment_run: Path = TREATMENT_RUN,
    control_run: Path = CONTROL_RUN,
    expected_body_sha256: str,
    expected_catalog_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if arm not in ARM_ORDER:
        raise SourceCoverageError(f"未知臂：{arm}")
    run_root = treatment_run if arm == "treatment" else control_run
    frozen_arm = "anchor_first" if arm == "treatment" else "control"
    candidate, input_shas = _audit_checkpoint(
        arm=arm,
        case_id=case_id,
        run_root=run_root,
        frozen_request_path=(C4_ROOT / "requests" / frozen_arm / f"{case_id}.json"),
        expected_body_sha256=expected_body_sha256,
        expected_catalog_sha256=expected_catalog_sha256,
    )
    events = candidate.get("events")
    if not isinstance(events, list):
        raise SourceCoverageError(f"{arm}/{case_id} 缺 events")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in seen:
            raise SourceCoverageError(f"{arm}/{case_id} 事件 ID 缺失或重复")
        seen.add(event_id)
        if arm == "treatment":
            raw_anchor_ids = event.get("minimal_anchor_ids")
        else:
            anchors = event.get("anchors")
            if not isinstance(anchors, list):
                raise SourceCoverageError(f"{arm}/{case_id}/{event_id} 缺 anchors")
            raw_anchor_ids = [
                row.get("anchor_id") if isinstance(row, Mapping) else None
                for row in anchors
            ]
        if (
            not isinstance(raw_anchor_ids, list)
            or not raw_anchor_ids
            or any(not isinstance(value, str) for value in raw_anchor_ids)
        ):
            raise SourceCoverageError(f"{arm}/{case_id}/{event_id} 锚列表非法")
        normalized.append(
            {
                "event_id": event_id,
                "anchor_ids": list(dict.fromkeys(raw_anchor_ids)),
            }
        )
    return normalized, input_shas


def resolve_anchor_to_unit(
    *,
    body: str,
    anchor: Mapping[str, Any],
    units: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    start = anchor.get("body_start_char")
    end = anchor.get("body_end_char_exclusive")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or end > len(body)
    ):
        raise SourceCoverageError("锚偏移非法，不能执行来源单元匹配")
    anchor_span = (
        start,
        end,
    )
    overlaps = [
        (
            str(unit["unit_id"]),
            _nonspace_overlap(
                body,
                anchor_span,
                (
                    int(unit["start_char"]),
                    int(unit["end_char_exclusive"]),
                ),
            ),
        )
        for unit in units
        if unit["mechanical_kind"] != "SEPARATOR_ONLY"
    ]
    maximum = max((value for _, value in overlaps), default=0)
    winners = sorted(unit_id for unit_id, value in overlaps if value == maximum)
    if maximum == 0:
        return {
            "status": "ZERO_OVERLAP_REVIEW",
            "max_nonspace_overlap": 0,
            "candidate_unit_ids": [],
        }
    if len(winners) != 1:
        return {
            "status": "TIED_MAX_REVIEW",
            "max_nonspace_overlap": maximum,
            "candidate_unit_ids": winners,
        }
    return {
        "status": "UNIQUE_MAX",
        "max_nonspace_overlap": maximum,
        "candidate_unit_ids": winners,
    }


def build_arm_ledger(
    *,
    arm: str,
    case_id: str,
    body: str,
    units: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unit_by_id = {str(unit["unit_id"]): unit for unit in units}
    covered_by: dict[str, set[str]] = {unit_id: set() for unit_id in unit_by_id}
    covered_anchors: dict[str, set[str]] = {unit_id: set() for unit_id in unit_by_id}
    review_units: set[str] = set()
    resolution_rows: list[dict[str, Any]] = []

    for event in events:
        event_id = str(event["event_id"])
        event_resolutions: list[dict[str, Any]] = []
        for anchor_id in event["anchor_ids"]:
            anchor = catalog.get(anchor_id)
            if anchor is None:
                raise SourceCoverageError(
                    f"{arm}/{case_id}/{event_id} 引用了目录外锚 {anchor_id}"
                )
            resolved = resolve_anchor_to_unit(
                body=body,
                anchor=anchor,
                units=units,
            )
            row = {
                "event_id": event_id,
                "anchor_id": anchor_id,
                **resolved,
            }
            event_resolutions.append(row)
            resolution_rows.append(row)

        for row in event_resolutions:
            if row["status"] == "UNIQUE_MAX":
                unit_id = row["candidate_unit_ids"][0]
                covered_by[unit_id].add(event_id)
                covered_anchors[unit_id].add(row["anchor_id"])
            elif row["status"] == "TIED_MAX_REVIEW":
                review_units.update(row["candidate_unit_ids"])

    ledger_units: list[dict[str, Any]] = []
    for unit in units:
        unit_id = str(unit["unit_id"])
        if unit["mechanical_kind"] == "SEPARATOR_ONLY":
            state = "EXCLUDE"
            reason = "MECHANICAL_SEPARATOR_ONLY"
        elif unit_id in review_units:
            state = "REVIEW"
            reason = "ANCHOR_TIE_OR_ZERO_OVERLAP"
        elif covered_by[unit_id]:
            state = "SCORE"
            reason = "UNIQUE_MAX_ANCHOR_OVERLAP"
        else:
            state = "REVIEW"
            reason = "NO_MECHANICALLY_DECIDABLE_COVERAGE"
        ledger_units.append(
            {
                **unit,
                "state": state,
                "state_reason": reason,
                "covered_by": sorted(covered_by[unit_id]),
                "covering_anchor_ids": sorted(covered_anchors[unit_id]),
            }
        )

    return {
        "arm": arm,
        "case_id": case_id,
        "units": ledger_units,
        "anchor_resolution": resolution_rows,
        "event_total": len(events),
        "anchor_reference_total": sum(len(event["anchor_ids"]) for event in events),
    }


def summarize_units(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(unit["state"]) for unit in units)
    for state in STATE_ORDER:
        counts.setdefault(state, 0)
    main_denominator = counts["SCORE"] + counts["REVIEW"]
    source_coverage_rate = (
        None if main_denominator == 0 else counts["SCORE"] / main_denominator
    )
    total = sum(counts.values())
    return {
        "unit_total": total,
        "state_counts": {state: counts[state] for state in STATE_ORDER},
        "main_denominator_score_plus_review": main_denominator,
        "source_coverage_rate": source_coverage_rate,
        "score_share_of_all_units": (None if total == 0 else counts["SCORE"] / total),
        "review_share_of_all_units": (None if total == 0 else counts["REVIEW"] / total),
        "review_share_of_main_denominator": (
            None if main_denominator == 0 else counts["REVIEW"] / main_denominator
        ),
        "context_style_exclude_not_in_main_denominator": True,
    }


def _nearest_rank(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise SourceCoverageError("空分布不能取分位数")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _stable_anchor_selection(
    *,
    anchor_ids: Sequence[str],
    arm: str,
    case_id: str,
    trial_index: int,
    size: int,
) -> list[str]:
    """用 SHA 排序取前 N 项，避免 random.sample 的版本实现差异。"""

    ranked = sorted(
        anchor_ids,
        key=lambda anchor_id: (
            sha256_bytes(
                (
                    f"{RANDOM_FLOOR_SEED}|{RANDOM_FLOOR_ALGORITHM}|"
                    f"{arm}|{case_id}|{trial_index}|{anchor_id}"
                ).encode("utf-8")
            ),
            anchor_id,
        ),
    )
    return ranked[:size]


def random_anchor_floor(
    *,
    body: str,
    units: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    sample_size: int,
    arm: str,
    case_id: str,
    trials: int = RANDOM_FLOOR_TRIALS,
) -> dict[str, Any]:
    if isinstance(trials, bool) or not isinstance(trials, int) or trials <= 0:
        raise SourceCoverageError("随机地板 trials 必须是正整数")
    if (
        isinstance(sample_size, bool)
        or not isinstance(sample_size, int)
        or sample_size < 0
    ):
        raise SourceCoverageError("随机地板 sample_size 必须是非负整数")
    eligible_units = [
        unit for unit in units if unit["mechanical_kind"] != "SEPARATOR_ONLY"
    ]
    anchor_ids = sorted(catalog)
    size = min(sample_size, len(anchor_ids))
    covered_counts: list[int] = []
    for trial_index in range(trials):
        selected = _stable_anchor_selection(
            anchor_ids=anchor_ids,
            arm=arm,
            case_id=case_id,
            trial_index=trial_index,
            size=size,
        )
        covered: set[str] = set()
        for anchor_id in selected:
            resolved = resolve_anchor_to_unit(
                body=body,
                anchor=catalog[anchor_id],
                units=units,
            )
            if resolved["status"] == "UNIQUE_MAX":
                covered.add(resolved["candidate_unit_ids"][0])
        covered_counts.append(len(covered))
    denominator = len(eligible_units)
    rates = [
        0.0 if denominator == 0 else count / denominator for count in covered_counts
    ]
    return {
        "trial_count": trials,
        "selection_algorithm": RANDOM_FLOOR_ALGORITHM,
        "sampled_distinct_anchor_total": size,
        "catalog_anchor_total": len(anchor_ids),
        "mean": (
            0.0 if denominator == 0 else sum(covered_counts) / (denominator * trials)
        ),
        "p05": _nearest_rank(rates, 0.05),
        "p50": _nearest_rank(rates, 0.50),
        "p95": _nearest_rank(rates, 0.95),
        "min": min(rates),
        "max": max(rates),
    }


def _aggregate_arm(
    arm_cases: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    units = [unit for case in arm_cases.values() for unit in case["units"]]
    return summarize_units(units)


def build_documents(
    *,
    source_manifest_path: Path = SOURCE_MANIFEST,
    catalog_dir: Path = CATALOG_DIR,
    treatment_run: Path = TREATMENT_RUN,
    control_run: Path = CONTROL_RUN,
) -> dict[str, Any]:
    manifest, sources = load_frozen_sources(source_manifest_path)
    case_order = [str(row["case_id"]) for row in manifest["chapters"]]

    arm_ledgers: dict[str, dict[str, Any]] = {arm: {} for arm in ARM_ORDER}
    source_inputs: dict[str, Any] = {}
    floor_cases: dict[str, dict[str, Any]] = {arm: {} for arm in ARM_ORDER}
    for case_id in case_order:
        source = sources[case_id]
        catalog = load_catalog(
            case_id,
            catalog_dir=catalog_dir,
            expected_body_sha256=source["body_sha256"],
            body=source["body"],
        )
        catalog_document = read_json(catalog_dir / f"{case_id}.json")
        catalog_identity_sha256 = canonical_sha(catalog_document)
        source_inputs[case_id] = {
            "body_sha256": source["body_sha256"],
            "cache_file_sha256": source["cache_file_sha256"],
            "catalog_sha256": sha256_file(catalog_dir / f"{case_id}.json"),
            "source_unit_total": len(source["units"]),
            "segmentation_sha256": sha256_bytes(canonical_json_bytes(source["units"])),
        }
        for arm in ARM_ORDER:
            events, input_shas = load_arm_events(
                arm,
                case_id,
                treatment_run=treatment_run,
                control_run=control_run,
                expected_body_sha256=source["body_sha256"],
                expected_catalog_sha256=catalog_identity_sha256,
            )
            ledger = build_arm_ledger(
                arm=arm,
                case_id=case_id,
                body=source["body"],
                units=source["units"],
                catalog=catalog,
                events=events,
            )
            ledger["summary"] = summarize_units(ledger["units"])
            ledger["input_shas"] = input_shas
            arm_ledgers[arm][case_id] = ledger
            distinct_anchor_total = len(
                {anchor_id for event in events for anchor_id in event["anchor_ids"]}
            )
            floor_cases[arm][case_id] = random_anchor_floor(
                body=source["body"],
                units=source["units"],
                catalog=catalog,
                sample_size=distinct_anchor_total,
                arm=arm,
                case_id=case_id,
            )

    source_unit_ledger = {
        "schema_version": SCHEMA_VERSION,
        "status": "CANDIDATE_DIAGNOSTIC_ONLY",
        "segmentation_contract": {
            "order": "physical_line_then_sentence_end_punctuation",
            "sentence_end_characters": sorted(SENTENCE_END | {"."}),
            "closing_characters_attached_to_previous_unit": sorted(CLOSERS),
            "offset_basis": "C4_frozen_body_unicode_codepoint",
            "text_not_emitted": True,
        },
        "state_contract": {
            "states": list(STATE_ORDER),
            "automatic_states_used": ["SCORE", "REVIEW", "EXCLUDE"],
            "context_only_and_style_only_require_future_nonmechanical_review": True,
            "unknown_defaults_to_review": True,
            "score_rule": (
                "each_anchor_independently_scores_only_its_unique_max_positive_"
                "nonspace_overlap_unit"
            ),
            "review_rule": (
                "the_same_anchor_tie_candidates_or_zero_overlap_or_"
                "no_mechanically_decidable_coverage"
            ),
            "event_level_tie_or_zero_does_not_spread_to_other_unique_anchors": (True),
        },
        "sources": source_inputs,
        "arms": arm_ledgers,
        "formal_gold_read": False,
        "model_api_calls": 0,
        "network_requests": 0,
    }

    coverage_report = {
        "schema_version": SCHEMA_VERSION,
        "status": "CANDIDATE_DIAGNOSTIC_ONLY",
        "main_denominator": "SCORE_PLUS_REVIEW",
        "arms": {
            arm: {
                "overall": _aggregate_arm(arm_ledgers[arm]),
                "by_case": {
                    case_id: arm_ledgers[arm][case_id]["summary"]
                    for case_id in case_order
                },
            }
            for arm in ARM_ORDER
        },
        "same_source_units_verified": all(
            [unit["unit_id"] for unit in arm_ledgers["treatment"][case_id]["units"]]
            == [unit["unit_id"] for unit in arm_ledgers["control"][case_id]["units"]]
            for case_id in case_order
        ),
        "interpretation_boundary": (
            "原文覆盖账只说明合法锚在同一机械来源单元上的可定位覆盖；"
            "不替代事实召回、语义承托、UCR、SOP 或发布闸。"
        ),
        "formal_gold_read": False,
        "quality_result_registered": False,
    }

    floor_report = {
        "schema_version": SCHEMA_VERSION,
        "status": "N11_DIAGNOSTIC_FLOORS_READY",
        "seed_text": RANDOM_FLOOR_SEED,
        "selection_algorithm": RANDOM_FLOOR_ALGORITHM,
        "trial_count": RANDOM_FLOOR_TRIALS,
        "empty_extraction_floor": {
            "source_coverage_rate": 0.0,
            "meaning": "没有任何锚引用时的机械地板",
        },
        "random_anchor_floor": {
            "sampling_contract": (
                "每臂每章保留实际使用的不同锚数量，从同章冻结目录无放回随机抽取；"
                "每次用 SHA 派生唯一排序后取前 N 项，不依赖 Python random 实现；"
                "逐锚只计算唯一最大正非空白重叠覆盖，100 次固定种子。"
            ),
            "arms": floor_cases,
        },
        "diagnostic_only": True,
        "does_not_replace_n11_atom_alignment_floor": True,
        "formal_gold_read": False,
    }

    source_receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS_ZERO_API_SOURCE_COVERAGE_LEDGER",
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "chapter_total": len(case_order),
        "source_unit_total": sum(len(source["units"]) for source in sources.values()),
        "arm_event_totals": {
            arm: sum(arm_ledgers[arm][case_id]["event_total"] for case_id in case_order)
            for arm in ARM_ORDER
        },
        "same_source_units_verified": coverage_report["same_source_units_verified"],
        "interpreter_independent_floor_algorithm": RANDOM_FLOOR_ALGORITHM,
        "arm_source_bindings": {
            arm: {
                case_id: arm_ledgers[arm][case_id]["input_shas"]
                for case_id in case_order
            }
            for arm in ARM_ORDER
        },
        "formal_gold_read": False,
        "model_api_calls": 0,
        "network_requests": 0,
        "candidate_only": True,
    }
    return {
        "source_unit_ledger.json": source_unit_ledger,
        "source_coverage_report.json": coverage_report,
        "n11_source_coverage_floors.json": floor_report,
        "source_receipt.json": source_receipt,
    }


def build_artifacts(**kwargs: Any) -> dict[str, bytes]:
    documents = build_documents(**kwargs)
    artifacts = {
        name: canonical_json_bytes(document) for name, document in documents.items()
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS_DETERMINISTIC_ARTIFACT_SET",
        "deterministic_floor_algorithm": RANDOM_FLOOR_ALGORITHM,
        "files": [
            {
                "path": name,
                "sha256": sha256_bytes(raw),
                "byte_count": len(raw),
            }
            for name, raw in sorted(artifacts.items())
        ],
        "artifact_set_sha256": sha256_bytes(
            canonical_json_bytes(
                {name: sha256_bytes(raw) for name, raw in sorted(artifacts.items())}
            )
        ),
    }
    artifacts["artifact_manifest.json"] = canonical_json_bytes(manifest)
    return artifacts


def verify_output_dir(
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    expected_artifacts: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    artifacts = dict(expected_artifacts or build_artifacts())
    if not output_dir.is_dir():
        raise SourceCoverageError(f"C11.3 输出目录缺失：{output_dir}")
    actual_names = {path.name for path in output_dir.iterdir()}
    expected_names = set(artifacts)
    if actual_names != expected_names:
        raise SourceCoverageError(
            "C11.3 输出目录文件集合漂移："
            f"缺失={sorted(expected_names - actual_names)}，"
            f"未登记={sorted(actual_names - expected_names)}"
        )
    for name, expected_raw in artifacts.items():
        path = output_dir / name
        if not path.is_file() or path.read_bytes() != expected_raw:
            raise SourceCoverageError(f"C11.3 磁盘工件不能从真源重建：{name}")
    return json.loads(artifacts["artifact_manifest.json"].decode("utf-8"))


def write_or_verify(
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    allow_rebuild: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    artifacts = build_artifacts(**kwargs)
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_names = set(artifacts)
    unexpected = {path.name for path in output_dir.iterdir()} - expected_names
    if unexpected:
        raise SourceCoverageError(f"C11.3 输出目录存在未登记文件：{sorted(unexpected)}")
    for name, raw in artifacts.items():
        path = output_dir / name
        if path.exists() and path.read_bytes() != raw and not allow_rebuild:
            raise SourceCoverageError(f"C11.3 既有工件发生字节漂移：{name}")
        path.write_bytes(raw)
    return verify_output_dir(output_dir, expected_artifacts=artifacts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C11.3 原文覆盖账")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="按当前已审输入重建候选工件；仍执行完整磁盘回读校验",
    )
    args = parser.parse_args(argv)
    expected = build_artifacts()
    if args.check:
        verify_output_dir(args.output_dir, expected_artifacts=expected)
    else:
        write_or_verify(args.output_dir, allow_rebuild=args.rebuild)
    receipt = json.loads(expected["source_receipt.json"].decode("utf-8"))
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "source_unit_total": receipt["source_unit_total"],
                "arm_event_totals": receipt["arm_event_totals"],
                "disk_full_set_rebuild_verified": True,
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
