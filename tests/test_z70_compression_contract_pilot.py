from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z70_compression_contract_pilot as z70  # noqa: E402


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-Request-Id": "z70-unit"}

    def __init__(self, payload: dict) -> None:
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.raw


def response_payload(chapter: int, *, finish_reason: str = "stop", empty: bool = False) -> dict:
    catalog = z70.read_json(
        z70.SOURCE_INPUTS / f"evidence_catalogs/ch{chapter:04d}.json"
    )["entries"]
    events = []
    if not empty:
        events = [
            {
                "event_id": f"EV-C{chapter:04d}-01",
                "event": "克莱恩完成了一次明确行动。",
                "anchors": [{"anchor_id": catalog[0]["anchor_id"]}],
            }
        ]
    content = json.dumps(
        {"schema_version": "z-event-v1", "chapter": chapter, "events": events},
        ensure_ascii=False,
    )
    return {
        "model": "deepseek-v4-flash",
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "completion_tokens_details": {"reasoning_tokens": 5},
        },
    }


class Z70CompressionContractPilotTests(unittest.TestCase):
    def patched_transport(self, opener):
        original = z70.api_transport.ApiTransport.from_bundle

        def factory(bundle, *, run_dir, max_calls):
            return original(
                bundle,
                run_dir=run_dir,
                max_calls=max_calls,
                opener=opener,
                sleeper=lambda _: None,
            )

        return mock.patch.object(
            z70.api_transport.ApiTransport,
            "from_bundle",
            side_effect=factory,
        )

    def test_unique_clause_diff_and_32k_baseline_for_all_five_chapters(self) -> None:
        self.assertEqual(z70.TARGET_CHAPTERS, (3, 4, 5, 13, 19))
        self.assertEqual(z70.MAX_TOKENS, 32000)
        for chapter in z70.TARGET_CHAPTERS:
            with self.subTest(chapter=chapter):
                z68_body = z70.z68.build_instantiated_body(chapter)[0]
                baseline, baseline_diff = z70.build_baseline_body(chapter)
                prepared, diff = z70.build_candidate_body(chapter)
                self.assertEqual(z70.deep_diff_paths(z68_body, baseline), ["$.max_tokens"])
                self.assertEqual(baseline["max_tokens"], 32000)
                self.assertEqual(prepared["max_tokens"], 32000)
                self.assertEqual(
                    z70.deep_diff_paths(baseline, prepared), ["$.messages[0].content"]
                )
                system = prepared["messages"][0]["content"]
                self.assertEqual(system.count(z70.COMPRESSION_CONTRACT_CLAUSE), 1)
                self.assertEqual(
                    z70.remove_candidate_clause(system), baseline["messages"][0]["content"]
                )
                self.assertEqual(prepared["messages"][1], baseline["messages"][1])
                self.assertEqual(
                    baseline_diff["builder"],
                    "z68_revised_request_pilot.build_instantiated_body",
                )
                self.assertTrue(diff["system_byte_equal_after_line_deletion"])
                self.assertEqual(z70.request_has_prohibited_input(prepared), [])

    def test_prepare_is_zero_call_copies_frozen_inputs_and_refuses_existing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z70-prepare"
            result = z70.prepare(run_dir)
            self.assertEqual(result["model_api_calls"], 0)
            self.assertEqual(result["network_attempts"], 0)
            self.assertFalse((run_dir / "call_attempts.jsonl").exists())
            self.assertFalse((run_dir / "usage.jsonl").exists())
            self.assertFalse((run_dir / "requests").exists())
            self.assertEqual(
                z70.z68.tree_fingerprint(run_dir / "inputs"),
                z70.SOURCE_INPUTS_FINGERPRINT,
            )
            self.assertEqual(len(list((run_dir / "baseline_requests").glob("*.json"))), 5)
            self.assertEqual(len(list((run_dir / "prepared_requests").glob("*.json"))), 5)
            self.assertEqual(len(list((run_dir / "request_diffs").glob("*.json"))), 5)
            self.assertTrue((run_dir / "provenance/z70_compression_contract_pilot.py").is_file())
            self.assertEqual(
                z70.verify_prepared(run_dir, require_zero_call=True)["status"], "pass"
            )
            with self.assertRaisesRegex(Exception, "运行目录已存在"):
                z70.prepare(run_dir)

    def test_concurrent_run_claim_has_one_owner_and_blocks_prepared_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z70-concurrent-claim"
            z70.prepare(run_dir)
            barrier = threading.Barrier(2)
            winners: list[dict] = []
            errors: list[BaseException] = []

            def compete() -> None:
                barrier.wait()
                try:
                    winners.append(z70.acquire_run_claim(run_dir))
                except BaseException as exc:  # 只收集并发结果供断言
                    errors.append(exc)

            threads = [threading.Thread(target=compete) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(len(winners), 1)
            self.assertEqual(len(errors), 1)
            self.assertIn("拒绝重复采样", str(errors[0]))
            with self.assertRaisesRegex(Exception, "正式运行工件"):
                z70.verify_prepared(run_dir, require_zero_call=True)
            with self.assertRaisesRegex(Exception, "机械验收失败"):
                z70.verify(run_dir)

    def test_success_order_and_429_retry_reuse_the_exact_same_body(self) -> None:
        network_chapters = [3, 3, 4, 5, 13, 19]
        captured_bodies: list[dict] = []

        def opener(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            captured_bodies.append(body)
            chapter = network_chapters[len(captured_bodies) - 1]
            if len(captured_bodies) == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {},
                    io.BytesIO(b"unit-rate-limit"),
                )
            return FakeResponse(response_payload(chapter))

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z70-success"
            z70.prepare(run_dir)
            with self.patched_transport(opener), mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                result = z70.run(run_dir)

            self.assertEqual(result["chapters_completed"], [3, 4, 5, 13, 19])
            self.assertEqual(len(captured_bodies), 6)
            self.assertEqual(captured_bodies[0], captured_bodies[1])
            self.assertEqual(
                captured_bodies[0], z70.read_json(run_dir / "prepared_requests/ch0003.json")
            )
            self.assertTrue(all(body["max_tokens"] == 32000 for body in captured_bodies))
            receipt = z70.transport_receipt(run_dir)
            self.assertEqual(
                receipt["logical_case_order"],
                ["ch0003", "ch0004", "ch0005", "ch0013", "ch0019"],
            )
            self.assertEqual(receipt["actual_network_attempts"], 6)
            self.assertEqual(receipt["attempts_by_case"]["ch0003"], 2)
            self.assertTrue(receipt["same_request_on_network_retries"])
            verification = z70.verify(run_dir)
            self.assertEqual(verification["status"], "pass")
            self.assertEqual(verification["run_status"], "completed_candidate_only")

    def test_any_failure_hard_stops_and_later_chapters_do_not_run(self) -> None:
        observed: list[int] = []

        def opener(request, timeout):
            chapter = (3, 4)[len(observed)]
            observed.append(chapter)
            return FakeResponse(
                response_payload(chapter, finish_reason="length" if chapter == 4 else "stop")
            )

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z70-hard-stop"
            z70.prepare(run_dir)
            with self.patched_transport(opener), mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                with self.assertRaisesRegex(Exception, "finish_reason=length"):
                    z70.run(run_dir)
            self.assertEqual(observed, [3, 4])
            self.assertFalse(
                (run_dir / "requests/neutral_extract/ch0005_request.json").exists()
            )
            self.assertFalse(
                (run_dir / "requests/neutral_extract/ch0013_request.json").exists()
            )
            self.assertFalse(
                (run_dir / "requests/neutral_extract/ch0019_request.json").exists()
            )
            hard_stop = z70.read_json(run_dir / "hard_stop.json")
            self.assertEqual(hard_stop["completed_chapters"], [3])
            self.assertEqual(hard_stop["next_chapter"], 4)
            self.assertEqual(
                z70.read_json(run_dir / "run_manifest.json")["status"], "hard_stop"
            )
            self.assertEqual(z70.verify(run_dir)["status"], "pass")
            hard_stop["completed_chapters"] = [3, 5]
            z70.write_json(run_dir / "hard_stop.json", hard_stop)
            with self.assertRaisesRegex(Exception, "机械验收失败"):
                z70.verify(run_dir)

    def test_keyboard_interrupt_is_persisted_as_hard_stop_not_prepared(self) -> None:
        def opener(request, timeout):
            raise KeyboardInterrupt("unit-interrupt")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z70-interrupted"
            z70.prepare(run_dir)
            with self.patched_transport(opener), mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                with self.assertRaises(KeyboardInterrupt):
                    z70.run(run_dir)
            manifest = z70.read_json(run_dir / "run_manifest.json")
            self.assertEqual(manifest["status"], "hard_stop")
            self.assertEqual(manifest["usable_model_outputs"], 0)
            self.assertEqual(z70.verify(run_dir)["status"], "pass")

    def test_empty_events_is_a_contract_failure_and_hard_stop(self) -> None:
        def opener(request, timeout):
            return FakeResponse(response_payload(3, empty=True))

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z70-empty"
            z70.prepare(run_dir)
            with self.patched_transport(opener), mock.patch.dict(
                os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
            ):
                with self.assertRaisesRegex(Exception, "events为空"):
                    z70.run(run_dir)
            self.assertFalse(
                (run_dir / "requests/neutral_extract/ch0004_request.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
