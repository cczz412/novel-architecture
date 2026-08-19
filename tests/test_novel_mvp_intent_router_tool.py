from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
TOOL_PATH = PRODUCT_ROOT / "mvp/intent_router_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import intent_router, intent_router_tool
finally:
    sys.path.pop(0)


ENTITIES = ["林照", "许岚", "周伯"]


def _request(intent: str = "下一章让林照和许岚在渡口相遇。") -> dict:
    return {"intent": intent, "known_entities": list(ENTITIES)}


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), *args],
        input=stdin,
        capture_output=True,
        check=False,
    )


def test_clear_next_chapter_meeting_uses_existing_router_advice_only() -> None:
    request = _request()

    result = intent_router_tool.execute(request)

    assert result == intent_router.route_author_intent(
        request["intent"], known_entities=request["known_entities"]
    )
    assert result["primary_home"] == "chapter_plan"
    assert result["link_targets"] == ["relationship_arc"]
    assert result["advice_only"] is True
    assert result["writes"] == []


def test_vague_long_term_fate_keeps_existing_clarification_behavior() -> None:
    result = intent_router_tool.execute(
        _request("有人最后一定会死，但具体时间未定。")
    )

    assert result["primary_home"] == "character_arc"
    assert result["candidate_homes"] == ["character_arc", "open_hook"]
    assert result["clarification_question"] == "这条长期命运属于哪个人物？"
    assert result["advice_only"] is True
    assert result["writes"] == []


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (
            {"intent": "下一章让林照出发。", "known_entities": "林照"},
            "KNOWN_ENTITIES_MUST_BE_ARRAY",
        ),
        (
            {"intent": "下一章让林照出发。", "known_entities": [""]},
            "KNOWN_ENTITY_INVALID",
        ),
        (
            {"intent": "下一章让林照出发。", "known_entities": ["林照", 3]},
            "KNOWN_ENTITY_INVALID",
        ),
        (
            {"intent": "下一章让林照出发。"},
            "REQUEST_FIELDS_INVALID",
        ),
        (
            {
                "intent": "下一章让林照出发。",
                "known_entities": ["林照"],
                "project": "forbidden",
            },
            "REQUEST_FIELDS_INVALID",
        ),
        (
            {"intent": "  ", "known_entities": ["林照"]},
            "EMPTY_AUTHOR_INTENT",
        ),
    ],
)
def test_bad_request_shape_is_rejected_before_routing(
    payload: dict, error_code: str
) -> None:
    with pytest.raises(intent_router_tool.IntentRouterToolError) as exc_info:
        intent_router_tool.execute(payload)

    assert exc_info.value.code == error_code


def test_file_output_bytes_equal_object_core_and_stdin_stdout(tmp_path: Path) -> None:
    request = _request()
    input_path = tmp_path / "intent.json"
    output_path = tmp_path / "advice.json"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))
    streamed = _run_cli(
        stdin=json.dumps(request, ensure_ascii=False).encode("utf-8")
    )

    expected = intent_router_tool.execute(request)
    assert completed.returncode == streamed.returncode == 0
    assert output_path.read_bytes() == intent_router_tool._output_bytes(expected)
    assert json.loads(output_path.read_bytes()) == expected
    assert json.loads(streamed.stdout) == expected


def test_bad_json_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "existing.json"
    input_path.write_bytes(b"{not-json")
    before = b'{"keep":"old"}\n'
    output_path.write_bytes(before)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"INPUT_JSON_INVALID" in completed.stderr
    assert output_path.read_bytes() == before


def test_bad_shape_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    input_path = tmp_path / "bad-shape.json"
    output_path = tmp_path / "existing.json"
    input_path.write_text(
        json.dumps(
            {"intent": "下一章让林照出发。", "known_entities": "林照"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    before = b'{"keep":"old"}\n'
    output_path.write_bytes(before)

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 2
    assert b"KNOWN_ENTITIES_MUST_BE_ARRAY" in completed.stderr
    assert output_path.read_bytes() == before


def test_replace_failure_keeps_existing_output_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "existing.json"
    before = b'{"keep":"old"}\n'
    output_path.write_bytes(before)

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(intent_router_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        intent_router_tool._write_atomic(
            output_path,
            intent_router_tool.execute(_request()),
        )

    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []


@pytest.mark.parametrize(
    ("intent", "expected_home", "expected_text"),
    [
        (
            "下一章让林照和许岚在渡口相遇。",
            "chapter_plan",
            "人物关系走向（relationship_arc）",
        ),
        (
            "有人最后一定会死，但具体时间未定。",
            "character_arc",
            "这条长期命运属于哪个人物？",
        ),
        (
            "本卷内要让林照找到旧城入口。",
            "volume_outline",
            "本卷内（current_volume）",
        ),
        (
            "先记个灵感，也许城门会自己说话。",
            "open_hook",
            "还只是灵感（idea）",
        ),
        (
            "林照未来会改变。",
            "character_arc",
            "这是人物长期走向，还是先作为未承诺灵感保存？",
        ),
    ],
)
def test_render_advice_covers_real_routes_without_changing_router_values(
    intent: str,
    expected_home: str,
    expected_text: str,
) -> None:
    request = _request(intent)
    before = copy.deepcopy(request)
    machine = intent_router_tool.execute(request)

    rendered = intent_router_tool.render_advice(request)

    assert request == before
    assert machine["primary_home"] == expected_home
    assert request["intent"] in rendered
    assert f"（{expected_home}）" in rendered
    assert expected_text in rendered
    assert f"置信度（沿用机器值）：{machine['confidence']}" in rendered
    for entity in machine["entity_scope"]["entities"]:
        assert entity in rendered
    assert "系统建议，不是作者确认" in rendered
    assert "当前没有写入任何计划/人物卡/关系卡/灵感账" in rendered
    assert "advice_only=true，writes=[]（写入数=0）" in rendered


def test_render_path_calls_execute_instead_of_accepting_forged_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request("下一章让林照出发。")
    real_execute = intent_router_tool.execute
    calls = 0

    def recording_execute(value: dict) -> dict:
        nonlocal calls
        calls += 1
        return real_execute(value)

    monkeypatch.setattr(intent_router_tool, "execute", recording_execute)

    rendered = intent_router_tool.render_advice(request)

    assert calls == 1
    assert request["intent"] in rendered


def test_render_cli_file_stdout_and_repeated_processes_are_byte_stable(
    tmp_path: Path,
) -> None:
    request = _request("下一章让林照和许岚在渡口相遇。")
    input_path = tmp_path / "intent.json"
    first_path = tmp_path / "advice-first.md"
    second_path = tmp_path / "advice-second.md"
    input_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    args = ("--render", "--input", str(input_path))

    first = _run_cli(*args, "--output", str(first_path))
    second = _run_cli(*args, "--output", str(second_path))
    stdout = _run_cli(*args)

    assert first.returncode == second.returncode == stdout.returncode == 0
    expected = intent_router_tool.render_advice(request).encode("utf-8")
    assert first_path.read_bytes() == second_path.read_bytes() == stdout.stdout
    assert stdout.stdout == expected


def test_render_bad_request_same_path_and_replace_failure_preserve_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    same_path = tmp_path / "same.json"
    request = _request()
    same_bytes = json.dumps(request, ensure_ascii=False).encode("utf-8")
    same_path.write_bytes(same_bytes)

    same_run = _run_cli(
        "--render",
        "--input",
        str(same_path),
        "--output",
        str(same_path),
    )
    assert same_run.returncode == 2
    assert b"INPUT_OUTPUT_PATH_MUST_DIFFER" in same_run.stderr
    assert same_path.read_bytes() == same_bytes

    output_path = tmp_path / "existing.md"
    original = b"keep-existing-render\n"
    output_path.write_bytes(original)
    bad_input = tmp_path / "bad.json"
    bad_input.write_text(
        json.dumps({"intent": "下一章出发", "known_entities": "林照"}),
        encoding="utf-8",
    )
    bad_run = _run_cli(
        "--render",
        "--input",
        str(bad_input),
        "--output",
        str(output_path),
    )
    assert bad_run.returncode == 2
    assert output_path.read_bytes() == original

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(intent_router_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        intent_router_tool._write_text_atomic(
            output_path,
            intent_router_tool.render_advice(request),
        )
    assert output_path.read_bytes() == original
    assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []
