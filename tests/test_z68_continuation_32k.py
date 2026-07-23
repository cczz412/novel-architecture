from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z68_continuation_32k as z68c  # noqa: E402


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-Request-Id": "z68c-unit"}

    def __init__(self, payload: dict) -> None:
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.raw


def response_payload(chapter: int, *, finish_reason: str = "stop") -> dict:
    content = json.dumps(
        {"schema_version": "z-event-v1", "chapter": chapter, "events": []},
        ensure_ascii=False,
    )
    return {
        "model": "deepseek-v4-flash",
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "completion_tokens_details": {"reasoning_tokens": 19},
        },
    }


class Z68Continuation32KTests(unittest.TestCase):
    def patched_transport(self, opener):
        original = z68c.api_transport.ApiTransport.from_bundle

        def factory(bundle, *, run_dir, max_calls):
            return original(
                bundle,
                run_dir=run_dir,
                max_calls=max_calls,
                opener=opener,
                sleeper=lambda _: None,
            )

        return mock.patch.object(
            z68c.api_transport.ApiTransport,
            "from_bundle",
            side_effect=factory,
        )

    def test_scope_and_single_variable_are_pinned(self) -> None:
        self.assertEqual(z68c.REUSED_CHAPTERS, (3, 4))
        self.assertEqual(z68c.CALLED_CHAPTERS, (5, 13, 19))
        self.assertEqual(z68c.NEW_MAX_TOKENS, 32000)
        self.assertEqual(z68c.MAX_NETWORK_ATTEMPTS, 5)

    def test_prior_hard_stop_and_tool_are_pinned(self) -> None:
        receipt = z68c.assert_prior_run()
        self.assertEqual(receipt["hard_stop_sha256"], z68c.PRIOR_HARD_STOP_SHA256)
        self.assertEqual(receipt["tool_sha256"], z68c.PRIOR_TOOL_SHA256)

    def test_called_chapters_change_only_max_tokens(self) -> None:
        for chapter in z68c.CALLED_CHAPTERS:
            with self.subTest(chapter=chapter):
                old = z68c.prior_prepared_body(chapter)
                new, diff = z68c.continued_body(chapter)
                self.assertEqual(z68c.deep_diff_paths(old, new), ["$.max_tokens"])
                self.assertEqual(old["max_tokens"], 16000)
                self.assertEqual(new["max_tokens"], 32000)
                self.assertEqual(old["messages"], new["messages"])
                self.assertTrue(diff["messages_equal"])

    def test_reused_chapters_cannot_be_called(self) -> None:
        for chapter in z68c.REUSED_CHAPTERS:
            with self.subTest(chapter=chapter):
                with self.assertRaisesRegex(Exception, "不调用"):
                    z68c.continued_body(chapter)

    def test_prohibited_material_is_absent(self) -> None:
        for chapter in z68c.CALLED_CHAPTERS:
            body = z68c.continued_body(chapter)[0]
            self.assertEqual(z68c.z68.request_has_prohibited_input(body), [])

    def test_run_local_contract_projects_exact_32k_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            z68c.build_run_local_contract(run_dir / z68c.RUN_LOCAL_CONTRACT)
            for chapter in z68c.CALLED_CHAPTERS:
                z68c.assert_body_matches_32k_contract(z68c.continued_body(chapter)[0], run_dir)

    def test_prepare_is_zero_call_and_refuses_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z68c-test"
            result = z68c.prepare(run_dir)
            self.assertEqual(result["model_api_calls"], 0)
            self.assertEqual(result["network_attempts"], 0)
            self.assertFalse((run_dir / "call_attempts.jsonl").exists())
            self.assertFalse((run_dir / "usage.jsonl").exists())
            self.assertEqual(len(list((run_dir / "prepared_requests").glob("*.json"))), 3)
            self.assertEqual(z68c.verify_prepared(run_dir, require_zero_call=True)["status"], "pass")
            with self.assertRaisesRegex(Exception, "运行目录已存在"):
                z68c.prepare(run_dir)

    def test_reused_artifacts_equal_prior_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z68c-test"
            z68c.prepare(run_dir)
            for chapter in z68c.REUSED_CHAPTERS:
                current = z68c.core_artifact_receipt(run_dir, chapter)
                prior = z68c.core_artifact_receipt(z68c.PRIOR_RUN, chapter)
                self.assertEqual(current["model_json_sha256"], prior["model_json_sha256"])
                self.assertEqual(current["events_sha256"], prior["events_sha256"])
                self.assertEqual(current["program_audit_sha256"], prior["program_audit_sha256"])

    def test_known_response_usage_keeps_unknown_attempt_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            response = {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "completion_tokens_details": {"reasoning_tokens": 19},
                },
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "", "reasoning_content": "abc"},
                    }
                ],
            }
            z68c.z68.write_json(run_dir / "responses/neutral_extract/ch0005_raw.json", response)
            (run_dir / "call_attempts.jsonl").write_text("{}\n{}\n", encoding="utf-8")
            receipt = z68c.known_response_usage(run_dir)
            self.assertEqual(receipt["totals"]["total_tokens"], 30)
            self.assertEqual(receipt["attempts_without_persisted_usage"], 1)

    def test_chapter5_failure_hard_stops_before_13_and_19(self) -> None:
        calls: list[int] = []

        def opener(request, timeout):
            calls.append(5)
            return FakeResponse(response_payload(5, finish_reason="length"))

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z68c-hard-stop"
            z68c.prepare(run_dir)
            with self.patched_transport(opener), mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                with self.assertRaisesRegex(Exception, "finish_reason=length"):
                    z68c.run(run_dir)
            self.assertEqual(calls, [5])
            attempts = z68c.z68.read_jsonl(run_dir / "call_attempts.jsonl")
            self.assertEqual([row["case_id"] for row in attempts], ["ch0005"])
            self.assertFalse((run_dir / "requests/neutral_extract/ch0013_request.json").exists())
            self.assertFalse((run_dir / "requests/neutral_extract/ch0019_request.json").exists())
            manifest = z68c.z68.read_json(run_dir / "run_manifest.json")
            self.assertEqual(manifest["status"], "hard_stop")
            self.assertEqual(manifest["transport"]["logical_case_order"], ["ch0005"])

    def test_successful_fake_run_is_strictly_5_13_19(self) -> None:
        chapters = iter(z68c.CALLED_CHAPTERS)
        observed: list[int] = []

        def opener(request, timeout):
            chapter = next(chapters)
            observed.append(chapter)
            return FakeResponse(response_payload(chapter))

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z68c-success"
            z68c.prepare(run_dir)
            with self.patched_transport(opener), mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                result = z68c.run(run_dir)
            self.assertEqual(observed, [5, 13, 19])
            self.assertEqual(result["new_chapters_completed"], [5, 13, 19])
            receipt = z68c.transport_receipt(run_dir)
            self.assertEqual(receipt["logical_case_order"], ["ch0005", "ch0013", "ch0019"])
            self.assertEqual(receipt["actual_network_attempts"], 3)
            self.assertEqual(receipt["logical_samples_started"], {
                "ch0005": 1,
                "ch0013": 1,
                "ch0019": 1,
            })
            manifest = z68c.z68.read_json(run_dir / "run_manifest.json")
            self.assertEqual(manifest["transport"], receipt)
            z68c.analyze(run_dir)
            verification = z68c.verify(run_dir)
            self.assertEqual(verification["status"], "pass")
            self.assertEqual(verification["transport"], receipt)

    def test_transport_budget_rejects_sixth_attempt(self) -> None:
        opened: list[int] = []

        def opener(request, timeout):
            opened.append(1)
            return FakeResponse(
                {
                    "model": "deepseek-v4-flash",
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z68c-budget"
            z68c.prepare(run_dir)
            bundle = z68c.load_bundle(run_dir)
            transport = z68c.api_transport.ApiTransport.from_bundle(
                bundle,
                run_dir=run_dir,
                max_calls=z68c.MAX_NETWORK_ATTEMPTS,
                opener=opener,
            )
            messages = z68c.continued_body(5)[0]["messages"]
            with mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                for index in range(1, 6):
                    transport.call(
                        stage="neutral_extract",
                        case_id=f"budget{index}",
                        messages=messages,
                    )
                with self.assertRaisesRegex(Exception, "调用闸已满：5/5"):
                    transport.call(
                        stage="neutral_extract",
                        case_id="budget6",
                        messages=messages,
                    )
            self.assertEqual(len(opened), 5)
            self.assertEqual(z68c.attempt_count(run_dir), 5)
            self.assertFalse(
                (run_dir / "requests/neutral_extract/budget6_request.json").exists()
            )

    def test_formal_record_summary_covers_abc(self) -> None:
        self.assertEqual(z68c.formal_record_summary({"type": "A", "delta": "变化"}), "变化")
        self.assertEqual(
            z68c.formal_record_summary(
                {"type": "B", "trigger_condition": "条件", "trigger_action": "动作"}
            ),
            "条件：动作",
        )
        self.assertEqual(
            z68c.formal_record_summary(
                {"type": "C", "reader_expectation": "期待", "payoff_test": "兑现"}
            ),
            "期待；兑现",
        )


if __name__ == "__main__":
    unittest.main()
