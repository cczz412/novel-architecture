"""M8 模糊意图路由的严格 JSON 文件外壳。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import NoReturn


if __package__:
    from . import intent_router
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import intent_router


REQUEST_KEYS = {"intent", "known_entities"}
HOME_LABELS = {
    "chapter_plan": "下一章或具体场景的章节计划",
    "volume_outline": "本卷卷纲",
    "character_arc": "人物长期走向",
    "relationship_arc": "人物关系走向",
    "open_hook": "尚未落位的灵感",
}
COMMITMENT_LABELS = {
    "committed": "作者表达了明确承诺",
    "provisional": "暂定方向",
    "idea": "还只是灵感",
}
TIME_HORIZON_LABELS = {
    "next_chapter_or_scene": "下一章或具体场景",
    "current_volume": "本卷内",
    "future_unscheduled": "未来，但时间未定",
    "long_term_unscheduled": "长期走向，时间未定",
    "unanchored": "还没有时间锚点",
}
SCOPE_KIND_LABELS = {
    "chapter": "章节",
    "volume": "卷",
    "character": "人物",
    "relationship": "人物关系",
    "open": "未落位",
}


class IntentRouterToolError(ValueError):
    """文件运输外壳拒绝了不闭合或可能误拆的人物输入。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise IntentRouterToolError(code, detail)


def execute(request: dict) -> dict:
    """严格校验运输对象后，原样调用现有 route_author_intent。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    intent = request.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        _fail("EMPTY_AUTHOR_INTENT")
    known_entities = request.get("known_entities")
    if not isinstance(known_entities, list):
        _fail("KNOWN_ENTITIES_MUST_BE_ARRAY")
    for index, entity in enumerate(known_entities):
        if not isinstance(entity, str) or not entity.strip():
            _fail("KNOWN_ENTITY_INVALID", str(index))

    result = intent_router.route_author_intent(
        intent,
        known_entities=known_entities,
    )
    if result.get("advice_only") is not True or result.get("writes") != []:
        _fail("ADVICE_ONLY_BOUNDARY_DRIFT")
    return result


def _label(mapping: dict[str, str], value: object, field: str) -> str:
    if not isinstance(value, str) or value not in mapping:
        _fail("RENDER_ENUM_UNKNOWN", field)
    return f"{mapping[value]}（{value}）"


def _home_list(values: object, field: str) -> str:
    if not isinstance(values, list):
        _fail("RENDER_RESULT_INVALID", field)
    if not values:
        return "无"
    return "、".join(_label(HOME_LABELS, value, field) for value in values)


def _blockquote(value: str) -> str:
    return "\n".join(
        f"> {line}" if line else ">"
        for line in (value.splitlines() or [""])
    )


def render_advice(request: dict) -> str:
    """从原 request 调用 execute，再生成不带写权的作者可读建议。"""
    result = execute(request)
    scope = result.get("entity_scope")
    if (
        not isinstance(scope, dict)
        or set(scope) != {"kind", "entities"}
        or not isinstance(scope.get("entities"), list)
        or any(not isinstance(item, str) or not item for item in scope["entities"])
    ):
        _fail("RENDER_RESULT_INVALID", "entity_scope")
    confidence = result.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        _fail("RENDER_RESULT_INVALID", "confidence")
    clarification = result.get("clarification_question")
    if clarification is not None and (
        not isinstance(clarification, str)
        or not clarification
        or clarification.count("？") > 1
    ):
        _fail("RENDER_RESULT_INVALID", "clarification_question")

    lines = [
        "# 作者未来意图放置建议",
        "",
        "## 作者原话",
        "",
        _blockquote(request["intent"]),
        "",
        "## 路由建议",
        "",
        (
            "- 首选落位："
            f"{_label(HOME_LABELS, result.get('primary_home'), 'primary_home')}"
            "（系统建议，不是作者确认）"
        ),
        (
            "- 可选落位（机器 candidate_homes，含首选）："
            f"{_home_list(result.get('candidate_homes'), 'candidate_homes')}"
        ),
        (
            "- 关联位置（机器 link_targets，只放引用）："
            f"{_home_list(result.get('link_targets'), 'link_targets')}"
        ),
        (
            "- 承诺强度："
            f"{_label(COMMITMENT_LABELS, result.get('commitment'), 'commitment')}"
        ),
        (
            "- 时间范围："
            f"{_label(TIME_HORIZON_LABELS, result.get('time_horizon'), 'time_horizon')}"
        ),
        (
            "- 识别范围："
            f"{_label(SCOPE_KIND_LABELS, scope.get('kind'), 'entity_scope.kind')}"
        ),
        f"- 识别人物：{'、'.join(scope['entities']) or '未识别到明确人物'}",
        f"- 置信度（沿用机器值）：{confidence}",
    ]
    if clarification is None:
        lines.append("- 澄清问题：无")
    else:
        lines.extend(
            [
                f"- 澄清问题：{clarification}",
                "- 为什么还要问：当前信息不足以唯一落位，工具没有硬猜。",
            ]
        )
    lines.extend(
        [
            "",
            "## 写入边界",
            "",
            (
                "⚠️ 这里只是放置建议，当前没有写入任何计划/人物卡/"
                "关系卡/灵感账。"
            ),
            "机器边界：advice_only=true，writes=[]（写入数=0）。",
        ]
    )
    return "\n".join(lines) + "\n"


# LOCAL_FILESYSTEM_ONLY: 只把本地 JSON 文件适配到纯对象 execute。
def _load_request(input_path: str | None) -> dict:
    if input_path in {None, "-"}:
        raw = sys.stdin.buffer.read()
    else:
        path = Path(input_path)
        if not path.is_file():
            _fail("INPUT_PATH_NOT_FILE", str(path))
        raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntentRouterToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("REQUEST_OBJECT_REQUIRED")
    return value


def _output_bytes(value: dict) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_atomic(path: Path, value: dict) -> None:
    _write_bytes_atomic(path, _output_bytes(value))


def _write_text_atomic(path: Path, value: str) -> None:
    _write_bytes_atomic(path, value.encode("utf-8"))


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    if not path.parent.is_dir():
        _fail("OUTPUT_PARENT_NOT_DIRECTORY", str(path.parent))
    if path.exists() and not path.is_file():
        _fail("OUTPUT_PATH_NOT_FILE", str(path))
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_paths(input_path: str | None, output_path: str | None) -> None:
    if input_path in {None, "-"} or output_path in {None, "-"}:
        return
    if Path(input_path).resolve() == Path(output_path).resolve():
        _fail("INPUT_OUTPUT_PATH_MUST_DIFFER")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="路由作者的一句未来意图")
    parser.add_argument("--input", help="输入 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON；省略或 - 表示 stdout")
    parser.add_argument(
        "--render",
        action="store_true",
        help="把原请求路由后输出作者可读建议，不接受单独结果对象",
    )
    args = parser.parse_args(argv)
    try:
        _validate_paths(args.input, args.output)
        request = _load_request(args.input)
        if args.render:
            rendered = render_advice(request)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(rendered.encode("utf-8"))
                sys.stdout.buffer.flush()
            else:
                _write_text_atomic(Path(args.output), rendered)
        else:
            result = execute(request)
            if args.output in {None, "-"}:
                sys.stdout.buffer.write(_output_bytes(result))
                sys.stdout.buffer.flush()
            else:
                _write_atomic(Path(args.output), result)
    except (OSError, IntentRouterToolError, intent_router.IntentRoutingError) as exc:
        print(f"INTENT_ROUTER_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
