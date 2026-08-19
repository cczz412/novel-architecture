"""M9 PROTOTYPE 的 LOCAL_FILESYSTEM_ONLY 命令行适配层。"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, TextIO

if __package__:
    from . import overview
else:  # 允许直接执行当前脚本。
    import overview


TRANSPORT_SCOPE = "LOCAL_FILESYSTEM_ONLY"
MODEL_PROVIDER_SWAP_POINT = overview.MODEL_PROVIDER_SWAP_POINT
BATCH_TRANSPORT = "M9_STANDALONE_MULTICHAPTER_BATCH"
BATCH_TRANSPORT_VERSION = "v1"
BATCH_REQUEST_KEYS = frozenset({"items"})


def execute(request: dict, overview_provider: overview.OverviewProvider) -> dict:
    """保留独立工具对象入口；文件操作只在 ``main`` 中发生。"""
    return overview.execute(request, overview_provider)


def render(card: object) -> str:
    """把一张既有 M9 prototype JSON 渲染为稳定人读文本。"""
    return overview.render_card(card)


def _validated_batch_items(request: object) -> list[dict[str, Any]]:
    if not isinstance(request, dict):
        raise overview.OverviewError("BATCH_REQUEST_NOT_OBJECT")
    missing = sorted(BATCH_REQUEST_KEYS - request.keys())
    extra = sorted(request.keys() - BATCH_REQUEST_KEYS)
    if missing:
        raise overview.OverviewError(
            f"BATCH_REQUEST_MISSING_FIELDS:{','.join(missing)}"
        )
    if extra:
        raise overview.OverviewError(f"BATCH_REQUEST_EXTRA_FIELDS:{','.join(extra)}")

    raw_items = request["items"]
    if not isinstance(raw_items, list) or not raw_items:
        raise overview.OverviewError("BATCH_ITEMS_MUST_BE_NONEMPTY_LIST")

    items: list[dict[str, Any]] = []
    chapter_ids: list[str] = []
    revision_refs: list[tuple[str, int, str]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise overview.OverviewError(f"BATCH_ITEM_NOT_OBJECT:{index}")
        try:
            overview.provider_key_for_request(raw_item)
        except overview.OverviewError as exc:
            raise overview.OverviewError(f"BATCH_ITEM_INVALID:{index}:{exc}") from exc
        current_ref = raw_item["current_revision_ref"]
        chapter_ids.append(current_ref["chapter_id"])
        revision_refs.append(
            (
                current_ref["chapter_id"],
                current_ref["revision_no"],
                current_ref["revision_text_sha256"],
            )
        )
        items.append(raw_item)

    duplicate_chapters = sorted(
        chapter_id for chapter_id in set(chapter_ids) if chapter_ids.count(chapter_id) > 1
    )
    duplicate_refs = sorted(
        revision_ref
        for revision_ref in set(revision_refs)
        if revision_refs.count(revision_ref) > 1
    )
    if duplicate_chapters or duplicate_refs:
        reasons: list[str] = []
        if duplicate_chapters:
            reasons.append(f"CHAPTER_ID={','.join(duplicate_chapters)}")
        if duplicate_refs:
            rendered_refs = ",".join(
                f"{chapter_id}:r{revision_no}:{revision_sha}"
                for chapter_id, revision_no, revision_sha in duplicate_refs
            )
            reasons.append(f"REVISION_REF={rendered_refs}")
        raise overview.OverviewError(f"BATCH_DUPLICATE_IDENTITY:{';'.join(reasons)}")
    return copy.deepcopy(items)


def execute_batch(
    request: dict,
    overview_provider: overview.OverviewProvider,
) -> dict[str, Any]:
    """按输入顺序运输多章请求；不增加任何跨章概览语义。"""
    items = _validated_batch_items(request)
    cards = [execute(item, overview_provider) for item in items]
    return {
        "transport": BATCH_TRANSPORT,
        "version": BATCH_TRANSPORT_VERSION,
        "cards": cards,
    }


def offline_overview_provider(responses: object) -> overview.OverviewProvider:
    """用冻结 JSON 映射替代模型；缺少精确键时失败关闭。"""
    if not isinstance(responses, dict):
        raise overview.OverviewError("RESPONSES_MAPPING_NOT_OBJECT")
    frozen = copy.deepcopy(responses)

    def provide(provider_request: dict[str, Any]) -> dict[str, Any]:
        key = provider_request["provider_key"]
        if key not in frozen:
            raise overview.OverviewError(f"OFFLINE_RESPONSE_MISSING:{key}")
        value = copy.deepcopy(frozen[key])
        if not isinstance(value, dict):
            raise overview.OverviewError(f"OFFLINE_RESPONSE_NOT_OBJECT:{key}")
        return value

    return provide


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise overview.OverviewError(f"FILE_NOT_UTF8:{path}") from exc
    except json.JSONDecodeError as exc:
        raise overview.OverviewError(f"FILE_NOT_JSON:{path}:{exc}") from exc


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    if not path.parent.is_dir():
        raise overview.OverviewError(f"OUTPUT_PARENT_NOT_FOUND:{path.parent}")
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


def _write_text_atomic(path: Path, value: str) -> None:
    if not path.parent.is_dir():
        raise overview.OverviewError(f"OUTPUT_PARENT_NOT_FOUND:{path.parent}")
    payload = value.encode("utf-8")
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


def _local_path(raw: str, *, label: str) -> Path:
    if raw == "-":
        raise overview.OverviewError(f"{label}_MUST_BE_LOCAL_FILE")
    return Path(raw)


def main(
    argv: list[str] | None = None,
    *,
    stderr: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="M9 本地 C4 v1 快照 -> PROTOTYPE 章概览卡（零 API）"
    )
    parser.add_argument(
        "--mode",
        choices=("single", "batch", "render"),
        default="single",
        help="single 保持原单章行为；batch 读取有序 items；render 渲染既有卡",
    )
    parser.add_argument("--input", required=True, help="本地单章请求或有序批次 JSON")
    parser.add_argument("--responses", help="JSON 生成模式所需的本地 responses 映射")
    parser.add_argument("--output", help="本地输出文件；render 省略时写 stdout")
    args = parser.parse_args(argv)
    stderr = stderr or sys.stderr
    stdout = stdout or sys.stdout

    try:
        input_path = _local_path(args.input, label="INPUT")
        input_value = _read_json(input_path)
        if args.mode == "render":
            if args.responses is not None:
                raise overview.OverviewError("RENDER_RESPONSES_NOT_ALLOWED")
            rendered = render(input_value)
            if args.output is None:
                stdout.write(rendered)
                stdout.flush()
            else:
                output_path = _local_path(args.output, label="OUTPUT")
                _write_text_atomic(output_path, rendered)
        else:
            if args.responses is None:
                raise overview.OverviewError("RESPONSES_REQUIRED_FOR_JSON_MODE")
            if args.output is None:
                raise overview.OverviewError("OUTPUT_REQUIRED_FOR_JSON_MODE")
            if not isinstance(input_value, dict):
                raise overview.OverviewError("REQUEST_NOT_OBJECT")
            responses_path = _local_path(args.responses, label="RESPONSES")
            output_path = _local_path(args.output, label="OUTPUT")
            responses = _read_json(responses_path)
            provider = offline_overview_provider(responses)
            if args.mode == "batch":
                result = execute_batch(input_value, provider)
            else:
                result = execute(input_value, provider)
            _write_json_atomic(output_path, result)
    except (overview.OverviewError, OSError) as exc:
        stderr.write(f"M9_OVERVIEW_TOOL_REJECTED:{exc}\n")
        stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
