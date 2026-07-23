from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MODULE_PATH = ROOT / "tools/z75_triplet_prompt_pilot.py"
SPEC = importlib.util.spec_from_file_location("z75_triplet_prompt_pilot", MODULE_PATH)
assert SPEC and SPEC.loader
z75 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z75)


class FakeTransport:
    def __init__(
        self,
        run_dir: Path,
        *,
        fail_chapter: int | None = None,
        retry_first: bool = False,
    ) -> None:
        self.run_dir = run_dir
        self.fail_chapter = fail_chapter
        self.retry_first = retry_first
        self.call_number = 0

    def _append_jsonl(self, path: Path, row: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def call(self, *, stage: str, case_id: str, messages: list[dict[str, str]]) -> SimpleNamespace:
        chapter = int(case_id.rsplit("ch", 1)[1])
        body = z75.read_json(self.run_dir / f"prepared_requests/ch{chapter:04d}.json")
        self.assert_messages_equal(messages, body["messages"])
        request_sha = z75.z68.canonical_sha(body)
        attempt_total = 2 if self.retry_first and chapter == 3 else 1
        for attempt in range(1, attempt_total + 1):
            self.call_number += 1
            self._append_jsonl(
                self.run_dir / "call_attempts.jsonl",
                {
                    "call_number": self.call_number,
                    "max_calls": z75.MAX_NETWORK_ATTEMPTS,
                    "stage": stage,
                    "case_id": case_id,
                    "attempt": attempt,
                    "request_sha256": request_sha,
                    "status": "retryable_http_error"
                    if attempt < attempt_total
                    else "success",
                },
            )
        request_record = {"stage": stage, "case_id": case_id, "body": body}
        z75.write_json(
            self.run_dir / f"requests/{stage}/{case_id}_request.json", request_record
        )
        anchor = "NOT-IN-CATALOG" if chapter == self.fail_chapter else "E0001"
        payload = {
            "schema_version": "z-event-v1",
            "chapter": chapter,
            "events": [
                {
                    "event_id": f"EV-C{chapter:04d}-01",
                    "event": "测试主体完成测试动作。",
                    "anchors": [{"anchor_id": anchor}],
                }
            ],
        }
        content = json.dumps(payload, ensure_ascii=False)
        z75.write_json(
            self.run_dir / f"responses/{stage}/{case_id}_raw.json",
            {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]},
        )
        z75.write_json(
            self.run_dir / f"responses/{stage}/{case_id}_meta.json",
            {"finish_reason": "stop", "elapsed_ms": 1},
        )
        self._append_jsonl(
            self.run_dir / "usage.jsonl",
            {
                "stage": stage,
                "case_id": case_id,
                "finish_reason": "stop",
                "stage_max_tokens": 32000,
                "elapsed_ms": 1,
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "completion_tokens_details": {"reasoning_tokens": 2},
                },
            },
        )
        return SimpleNamespace(
            request_record=request_record,
            finish_reason="stop",
            content=content,
        )

    def assert_messages_equal(
        self, observed: list[dict[str, str]], expected: list[dict[str, str]]
    ) -> None:
        if observed != expected:
            raise AssertionError("fake transport 收到的 messages 不等于 prepared")


class Z75TripletPromptPilotTest(unittest.TestCase):
    def test_source_is_pinned_and_only_exact_file_is_loaded(self) -> None:
        doc = z75.load_example_source()
        self.assertEqual(z75.SOURCE_EXAMPLES_SHA256, z75.z68.sha256_file(z75.SOURCE_EXAMPLES))
        self.assertEqual(16, len(doc["groups"]))
        self.assertEqual(28, sum(len(row["just_right"]["records"]) for row in doc["groups"]))

    def test_direction_shapes_are_two_by_two(self) -> None:
        expected = {
            "jr08": (8, 15, "just_right_only"),
            "jr28": (16, 28, "just_right_only"),
            "triad08": (8, 15, "full_triad"),
            "triad16": (16, 28, "full_triad"),
        }
        for direction, (groups, records, mode) in expected.items():
            block, meta = z75.render_example_block(direction)
            self.assertEqual(groups, meta["group_count"])
            self.assertEqual(records, meta["just_right_record_count"])
            self.assertEqual(mode, meta["mode"])
            self.assertNotIn(z75.FORBIDDEN_SOURCE_NAME, block)
            self.assertFalse(
                z75.z68.request_has_prohibited_input(
                    {"messages": [{"role": "system", "content": block}]}
                )
            )
            if mode == "full_triad":
                self.assertIn("太大版（错误，不要照抄）", block)
                self.assertIn("太小版（错误，不要照抄）", block)
            else:
                self.assertNotIn("太大版（错误，不要照抄）", block)
                self.assertNotIn("太小版（错误，不要照抄）", block)

    def test_candidate_is_only_a_middle_system_message(self) -> None:
        for direction in z75.DIRECTIONS:
            block, _ = z75.render_example_block(direction)
            for chapter in z75.TARGET_CHAPTERS:
                baseline, _ = z75.z70.build_baseline_body(chapter)
                candidate, diff = z75.build_candidate_body(direction, chapter)
                restored = copy.deepcopy(candidate)
                middle = restored["messages"].pop(1)
                self.assertEqual(baseline, restored)
                self.assertEqual({"role": "system", "content": block}, middle)
                self.assertEqual(32000, candidate["max_tokens"])
                self.assertTrue(diff["removed_message_restores_baseline_exactly"])
                self.assertTrue(diff["unchanged_original_system"])
                self.assertTrue(diff["unchanged_original_user"])
                self.assertTrue(all(diff["unchanged_top_level_except_messages"].values()))

    def test_prepare_and_verify_are_zero_call_for_all_directions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for direction in z75.DIRECTIONS:
                run_dir = root / direction
                preflight = z75.prepare(direction, run_dir)
                self.assertEqual("pass_zero_call_prepared", preflight["status"])
                self.assertEqual(0, preflight["model_api_calls"])
                receipt = z75.verify(direction, run_dir)
                self.assertEqual("pass", receipt["status"])
                self.assertEqual("prepared", receipt["run_status"])
                self.assertFalse(z75.call_artifacts_present(run_dir))

    def test_protected_v12_pointer_and_gold_are_pinned(self) -> None:
        protected = z75.assert_protected()
        self.assertEqual(
            z75.CURRENT_GOLD_POINTER_SHA256,
            protected[z75.CURRENT_GOLD_POINTER.relative_to(ROOT).as_posix()],
        )
        self.assertEqual(
            z75.CURRENT_GOLD_V1_2_SHA256,
            protected[z75.CURRENT_GOLD_V1_2.relative_to(ROOT).as_posix()],
        )

    def test_fake_transport_runs_five_chapters_once_and_actual_body_equals_prepared(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_dir = Path(raw) / "jr08"
            z75.prepare("jr08", run_dir)
            fake = FakeTransport(run_dir, retry_first=True)
            with mock.patch.object(
                z75.api_transport.ApiTransport,
                "from_bundle",
                return_value=fake,
            ):
                metrics = z75.run("jr08", run_dir)
            self.assertEqual(list(z75.TARGET_CHAPTERS), metrics["chapters_completed"])
            receipt = z75.verify("jr08", run_dir)
            self.assertEqual("completed_candidate_silver_only", receipt["run_status"])
            self.assertEqual(5, len(z75.z68.read_jsonl(run_dir / "usage.jsonl")))
            transport = z75.transport_receipt("jr08", run_dir)
            self.assertEqual(6, transport["actual_network_attempts"])
            self.assertEqual(2, transport["attempts_by_case"]["jr08_ch0003"])
            self.assertTrue(transport["same_request_on_network_retries"])
            with self.assertRaisesRegex(
                Exception, "拒绝重复采样|不是首次运行状态|不是可首次运行"
            ):
                z75.run("jr08", run_dir)

    def test_fake_transport_invalid_anchor_hard_stops_and_refuses_resume(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_dir = Path(raw) / "triad08"
            z75.prepare("triad08", run_dir)
            fake = FakeTransport(run_dir, fail_chapter=4)
            with mock.patch.object(
                z75.api_transport.ApiTransport,
                "from_bundle",
                return_value=fake,
            ):
                with self.assertRaisesRegex(Exception, "回包无效|证据锚合同失败"):
                    z75.run("triad08", run_dir)
            hard_stop = z75.read_json(run_dir / "hard_stop.json")
            self.assertEqual([3], hard_stop["completed_chapters"])
            self.assertEqual(4, hard_stop["next_chapter"])
            self.assertEqual("hard_stop", z75.read_json(run_dir / "run_manifest.json")["status"])
            receipt = z75.verify("triad08", run_dir)
            self.assertEqual("hard_stop", receipt["run_status"])
            with self.assertRaisesRegex(
                Exception, "拒绝重复采样|不是首次运行状态|不是可首次运行"
            ):
                z75.run("triad08", run_dir)


if __name__ == "__main__":
    unittest.main()
