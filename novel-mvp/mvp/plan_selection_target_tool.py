"""把作者对当前 C7 局部卡的选择绑定成只读运输原型。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn


if __package__:
    from . import plan_tool
else:  # 允许直接运行 python novel-mvp/mvp/plan_selection_target_tool.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvp import plan_tool


REQUEST_KEYS = {
    "c7",
    "expected_c7_snapshot_sha256",
    "card_local_id",
    "choice",
}
CHOICES = {"A", "B", "C", "discard"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class PlanSelectionTargetToolError(ValueError):
    """C7 局部选择目标或本地 JSON 适配不合法。"""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _fail(code: str, detail: str = "") -> NoReturn:
    raise PlanSelectionTargetToolError(code, detail)


def execute(request: object) -> dict[str, Any]:
    """只解析作者点名的 C7 卡和局部选项，不生成正式写入动作。"""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        _fail("REQUEST_FIELDS_INVALID")
    try:
        snapshot = plan_tool.validate_c7_v1(request.get("c7"))
        actual_sha256 = plan_tool.c7_snapshot_sha256(snapshot)
    except plan_tool.PlanToolError as exc:
        raise PlanSelectionTargetToolError("C7_SNAPSHOT_INVALID", str(exc)) from exc

    expected_sha256 = request.get("expected_c7_snapshot_sha256")
    if (
        not isinstance(expected_sha256, str)
        or SHA256_RE.fullmatch(expected_sha256) is None
    ):
        _fail("EXPECTED_C7_SNAPSHOT_SHA256_INVALID")
    if expected_sha256 != actual_sha256:
        _fail("STALE_C7_SNAPSHOT")

    card_local_id = request.get("card_local_id")
    if not isinstance(card_local_id, str) or not card_local_id:
        _fail("CARD_LOCAL_ID_INVALID")
    matching_cards = [
        card for card in snapshot["cards"] if card["id"] == card_local_id
    ]
    if len(matching_cards) != 1:
        _fail("CARD_LOCAL_ID_NOT_FOUND", card_local_id)
    card = matching_cards[0]

    choice = request.get("choice")
    if choice not in CHOICES:
        _fail("CHOICE_INVALID", str(choice))
    selected_option: dict[str, Any] | None = None
    if choice != "discard":
        selected_options = [
            option for option in card["options"] if option["id"] == choice
        ]
        if len(selected_options) != 1:
            _fail("CHOICE_OPTION_NOT_FOUND", choice)
        selected_option = selected_options[0]

    return {
        "kind": "C7_LOCAL_SELECTION_TARGET_PROTOTYPE",
        "version": "v1",
        "identity": "transport_only_no_plan_write",
        "source_c7_snapshot_sha256": actual_sha256,
        "project": snapshot["project"],
        "card_local_id": card_local_id,
        "choice": choice,
        "card": copy.deepcopy(card),
        "selected_option": copy.deepcopy(selected_option),
        "planning_card_ref": card["planning_card_ref"],
        "planning_card_rev": card["planning_card_rev"],
        "recommended_option_ref": card["recommended_option_ref"],
        "is_recommended_choice": (
            None
            if selected_option is None
            else selected_option["id"] == card["recommended_option_ref"]
        ),
        "selection_target_summary": {
            "card_title": card["title"],
            "option_label": (
                None if selected_option is None else selected_option["label"]
            ),
            "reveal_intent": (
                None
                if selected_option is None
                else selected_option["reveal_intent"]
            ),
        },
    }


# LOCAL_FILESYSTEM_ONLY: 仅把本地 JSON 请求适配到纯对象 execute。
def _load_request(input_path: str | None) -> dict[str, Any]:
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
        raise PlanSelectionTargetToolError("INPUT_JSON_INVALID") from exc
    if not isinstance(value, dict):
        _fail("REQUEST_OBJECT_REQUIRED")
    return value


def _output_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
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
            handle.write(_output_bytes(value))
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
    parser = argparse.ArgumentParser(description="解析 C7 局部作者选择目标")
    parser.add_argument("--input", help="输入 JSON；省略或 - 表示 stdin")
    parser.add_argument("--output", help="输出 JSON；省略或 - 表示 stdout")
    args = parser.parse_args(argv)
    try:
        _validate_paths(args.input, args.output)
        result = execute(_load_request(args.input))
        if args.output in {None, "-"}:
            sys.stdout.buffer.write(_output_bytes(result))
            sys.stdout.buffer.flush()
        else:
            _write_json_atomic(Path(args.output), result)
    except (OSError, PlanSelectionTargetToolError) as exc:
        print(f"PLAN_SELECTION_TARGET_TOOL_ERROR:{exc}", file=sys.stderr)
        return 2
    return 0


__all__ = ["PlanSelectionTargetToolError", "execute"]


if __name__ == "__main__":
    raise SystemExit(main())
