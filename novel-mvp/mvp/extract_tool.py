"""M3 独立零 API 工具：C2 v1 批次 → C3 v1 批次。

``execute`` 只处理对象。文件、stdin/stdout 和原子落盘只存在于 CLI
适配层。本模块不调模型；``response_provider`` 是唯一的模型供应器替换缝。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

try:
    from . import text_mapping as mapping_runtime
except ImportError:  # direct local-file CLI
    import text_mapping as mapping_runtime
from typing import Any, TextIO

if __package__:
    from . import extract
else:  # 允许 `python novel-mvp/mvp/extract_tool.py ...` 直接运行。
    import extract


MODEL_PROVIDER_SWAP_POINT = "MODEL_PROVIDER_SWAP_POINT"
REQUEST_KEYS = frozenset({"items", "current_chapter_revision_refs"})
C3_V1_KEYS = frozenset(
    {"contract", "version", "chapter_revision_ref", "text", "quote", "seg"}
)
CALL_RESULT_KEYS = frozenset({"data", "usage", "model"})


class ExtractToolError(RuntimeError):
    """独立工具在产生完整 C3 v1 批次前失败关闭。"""


ResponseProvider = Callable[[dict[str, Any]], dict[str, Any]]


def item_key(item: dict[str, Any]) -> str:
    """给离线 responses 映射生成稳定的责任段键。"""
    ref = item.get("chapter_revision_ref")
    if not isinstance(ref, dict):
        raise ExtractToolError("C2_ITEM_REVISION_REF_MISSING")
    return f"{ref.get('chapter_id')}:r{ref.get('revision_no')}:s{item.get('seg')}"


def _validate_request(request: object) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(request, dict):
        raise ExtractToolError("REQUEST_NOT_OBJECT")
    missing = sorted(REQUEST_KEYS - request.keys())
    extra = sorted(request.keys() - REQUEST_KEYS)
    if missing:
        raise ExtractToolError(f"REQUEST_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        raise ExtractToolError(f"REQUEST_EXTRA_FIELDS:{','.join(extra)}")

    items = request["items"]
    refs = request["current_chapter_revision_refs"]
    if not isinstance(items, list) or not items:
        raise ExtractToolError("REQUEST_ITEMS_MUST_BE_NONEMPTY_LIST")
    if not isinstance(refs, list) or not refs:
        raise ExtractToolError("CURRENT_REFS_MUST_BE_NONEMPTY_LIST")
    if any(not isinstance(item, dict) for item in items):
        raise ExtractToolError("C2_ITEM_NOT_OBJECT")

    current_by_chapter: dict[str, dict[str, Any]] = {}
    for ref in refs:
        if not isinstance(ref, dict):
            raise ExtractToolError("CURRENT_REVISION_REF_NOT_OBJECT")
        chapter_id = ref.get("chapter_id")
        if not isinstance(chapter_id, str):
            raise ExtractToolError("CURRENT_REVISION_REF_CHAPTER_ID_INVALID")
        if chapter_id in current_by_chapter:
            raise ExtractToolError(f"DUPLICATE_CURRENT_REVISION_REF:{chapter_id}")
        current_by_chapter[chapter_id] = ref

    seen_keys: set[str] = set()
    item_chapters: set[str] = set()
    for item in items:
        ref = item.get("chapter_revision_ref")
        chapter_id = ref.get("chapter_id") if isinstance(ref, dict) else None
        if not isinstance(chapter_id, str) or chapter_id not in current_by_chapter:
            raise ExtractToolError(f"CURRENT_REVISION_REF_MISSING:{chapter_id}")
        extract.validate_c2_v1_segment(
            item,
            current_chapter_revision_ref=current_by_chapter[chapter_id],
        )
        key = item_key(item)
        if key in seen_keys:
            raise ExtractToolError(f"DUPLICATE_C2_ITEM:{key}")
        seen_keys.add(key)
        item_chapters.add(chapter_id)

    unused = sorted(current_by_chapter.keys() - item_chapters)
    if unused:
        raise ExtractToolError(f"UNUSED_CURRENT_REVISION_REFS:{','.join(unused)}")
    return items, current_by_chapter


def _validate_provider_result(value: object, *, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExtractToolError(f"PROVIDER_RESULT_NOT_OBJECT:{key}")
    missing = sorted(CALL_RESULT_KEYS - value.keys())
    extra = sorted(value.keys() - CALL_RESULT_KEYS)
    if missing:
        raise ExtractToolError(f"PROVIDER_RESULT_MISSING_FIELDS:{key}:{','.join(missing)}")
    if extra:
        raise ExtractToolError(f"PROVIDER_RESULT_EXTRA_FIELDS:{key}:{','.join(extra)}")
    if not isinstance(value["usage"], dict) or not isinstance(value["model"], str):
        raise ExtractToolError(f"PROVIDER_METADATA_INVALID:{key}")

    data = value["data"]
    if not isinstance(data, dict) or set(data) != {"facts"}:
        raise ExtractToolError(f"PROVIDER_DATA_SHAPE_INVALID:{key}")
    facts = data["facts"]
    if not isinstance(facts, list):
        raise ExtractToolError(f"PROVIDER_FACTS_NOT_LIST:{key}")
    for index, fact in enumerate(facts, start=1):
        if not isinstance(fact, dict) or set(fact) != {"text", "quote"}:
            raise ExtractToolError(f"PROVIDER_FACT_SHAPE_INVALID:{key}:{index}")
        text = fact["text"]
        quote = fact["quote"]
        if not isinstance(text, str) or not text or text != text.strip():
            raise ExtractToolError(f"PROVIDER_FACT_TEXT_INVALID:{key}:{index}")
        if not isinstance(quote, str) or quote != quote.strip():
            raise ExtractToolError(f"PROVIDER_FACT_QUOTE_INVALID:{key}:{index}")
    return value


def _validate_c3_candidate(candidate: object, *, source_item: dict[str, Any], key: str) -> None:
    expected_keys = C3_V1_KEYS | ({"text_map_evidence"} if "text_map" in source_item else set())
    if not isinstance(candidate, dict) or set(candidate) != expected_keys:
        raise ExtractToolError(f"C3_V1_SHAPE_INVALID:{key}")
    if candidate["contract"] != "C3_FACT_CANDIDATE" or candidate["version"] != "v1":
        raise ExtractToolError(f"C3_V1_IDENTITY_INVALID:{key}")
    if candidate["chapter_revision_ref"] != source_item["chapter_revision_ref"]:
        raise ExtractToolError(f"C3_REVISION_REF_NOT_INHERITED:{key}")
    if candidate["seg"] != source_item["seg"]:
        raise ExtractToolError(f"C3_SEG_NOT_INHERITED:{key}")
    quote = candidate["quote"]
    if "text_map" in source_item:
        try:
            mapping_runtime.validate_candidate(candidate, source_item)
        except (ValueError, KeyError, TypeError) as exc:
            raise ExtractToolError(f"C3_TEXT_MAP_INVALID:{key}:{exc}") from exc
        return
    if quote and quote not in source_item["text"]:
        raise ExtractToolError(f"C3_QUOTE_NOT_IN_RESPONSIBILITY_SEGMENT:{key}")


def execute(request: dict, response_provider: ResponseProvider) -> dict:
    """Run one all-or-nothing C2 v1 batch through the existing M3 boundary."""
    if not callable(response_provider):
        raise ExtractToolError("RESPONSE_PROVIDER_NOT_CALLABLE")
    items, current_by_chapter = _validate_request(request)

    output_items: list[dict[str, Any]] = []
    for item in items:
        key = item_key(item)

        def provider_adapter(
            instructions: str,
            user_content: str,
            cfg: dict,
            *,
            _item: dict[str, Any] = item,
            _key: str = key,
        ) -> dict[str, Any]:
            provider_request = {
                "item_key": _key,
                "instructions": instructions,
                "user_content": user_content,
                "c2_item": copy.deepcopy(_item),
            }
            result = response_provider(provider_request)
            return _validate_provider_result(result, key=_key)

        chapter_id = item["chapter_revision_ref"]["chapter_id"]
        candidates = extract.extract_segment(
            item,
            {"model_id": MODEL_PROVIDER_SWAP_POINT},
            current_chapter_revision_ref=current_by_chapter[chapter_id],
            response_provider=provider_adapter,
        )
        for candidate in candidates:
            _validate_c3_candidate(candidate, source_item=item, key=key)
        output_items.extend(candidates)

    return {"items": output_items}


def offline_response_provider(responses: object) -> ResponseProvider:
    """用已冻结 JSON 映射替代模型；缺项直接失败，不生成默认响应。"""
    if not isinstance(responses, dict):
        raise ExtractToolError("RESPONSES_MAPPING_NOT_OBJECT")
    frozen = copy.deepcopy(responses)

    def provide(provider_request: dict[str, Any]) -> dict[str, Any]:
        key = provider_request["item_key"]
        if key not in frozen:
            raise ExtractToolError(f"OFFLINE_RESPONSE_MISSING:{key}")
        return copy.deepcopy(frozen[key])

    return provide


def _file_identity(
    path: Path,
    *,
    label: str,
) -> tuple[Path, os.stat_result | None]:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ExtractToolError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    try:
        stat_result = path.stat()
    except FileNotFoundError:
        stat_result = None
    except OSError as exc:
        raise ExtractToolError(f"FILE_IDENTITY_UNAVAILABLE:{label}") from exc
    return resolved, stat_result


def _same_file_identity(left: Path, right: Path) -> bool:
    left_resolved, left_stat = _file_identity(left, label="SOURCE")
    right_resolved, right_stat = _file_identity(right, label="OUTPUT")
    return left_resolved == right_resolved or (
        left_stat is not None
        and right_stat is not None
        and os.path.samestat(left_stat, right_stat)
    )


def _validate_adapter_paths(
    input_path: str | None,
    responses_path: str,
    output_path: str | None,
) -> None:
    if output_path in {None, "-"}:
        return
    output = Path(output_path)
    if input_path not in {None, "-"} and _same_file_identity(
        Path(input_path), output
    ):
        raise ExtractToolError("OUTPUT_PATH_MUST_DIFFER_FROM_INPUT")
    if _same_file_identity(Path(responses_path), output):
        raise ExtractToolError("OUTPUT_PATH_MUST_DIFFER_FROM_RESPONSES")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ExtractToolError(f"FILE_NOT_UTF8:{path}") from exc
    except json.JSONDecodeError as exc:
        raise ExtractToolError(f"FILE_NOT_JSON:{path}:{exc}") from exc


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
        _fsync_directory(path.parent)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="M3 本地 C2 v1 → C3 v1 离线工具")
    parser.add_argument("--input", help="C2 v1 批次 JSON；不给时从 stdin 读")
    parser.add_argument("--responses", required=True, help="已冻结的离线 responses JSON 映射")
    parser.add_argument("--output", help="C3 v1 批次 JSON；不给时写 stdout")
    args = parser.parse_args(argv)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    try:
        _validate_adapter_paths(args.input, args.responses, args.output)
        if args.input not in {None, "-"}:
            request = _read_json(Path(args.input))
        else:
            try:
                request = json.load(stdin)
            except json.JSONDecodeError as exc:
                raise ExtractToolError(f"STDIN_NOT_JSON:{exc}") from exc
        responses = _read_json(Path(args.responses))
        result = execute(request, offline_response_provider(responses))
        if args.output not in {None, "-"}:
            _write_json_atomic(Path(args.output), result)
        else:
            json.dump(result, stdout, ensure_ascii=False, indent=2)
            stdout.write("\n")
            stdout.flush()
    except (ExtractToolError, extract.C2V1ContractError, OSError) as exc:
        stderr.write(f"M3_EXTRACT_TOOL_REJECTED:{exc}\n")
        stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
