from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z71_semantic_fill_pilot as z71  # noqa: E402


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-Request-Id": "z71-unit"}

    def __init__(self, payload: dict) -> None:
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self.raw


def model_output_from_body(body: dict, mutate=None) -> dict:
    payload = json.loads(body["messages"][1]["content"])
    events = [
        {
            "event_id": row["event_id"],
            "event": row["event"],
            "provenance_anchor_ids": [],
        }
        for row in payload["items"]
    ]
    output = {
        "schema_version": "z-semantic-fill-v1",
        "chapter": payload["chapter"],
        "batch_id": payload["batch_id"],
        "events": events,
    }
    if mutate is not None:
        mutate(output, payload)
    return output


def response_for_body(body: dict, mutate=None) -> dict:
    content = json.dumps(model_output_from_body(body, mutate), ensure_ascii=False)
    return {
        "model": z71.MODEL,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "completion_tokens_details": {"reasoning_tokens": 5},
        },
    }


class Z71SemanticFillPilotTests(unittest.TestCase):
    def patched_transport(self, opener):
        original = z71.api_transport.ApiTransport.from_bundle

        def factory(bundle, *, run_dir, max_calls):
            return original(
                bundle,
                run_dir=run_dir,
                max_calls=max_calls,
                opener=opener,
                sleeper=lambda _: None,
            )

        return mock.patch.object(
            z71.api_transport.ApiTransport,
            "from_bundle",
            side_effect=factory,
        )

    def test_prepare_is_zero_call_and_builds_72_events_in_25_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-prepare"
            result = z71.prepare(run_dir)
            self.assertEqual(result["model_api_calls"], 0)
            self.assertEqual(result["network_attempts"], 0)
            self.assertEqual(result["logical_batches"], 25)
            self.assertEqual(result["total_events"], 72)
            batch_sizes = [row["event_count"] for row in result["rows"]]
            self.assertEqual(batch_sizes.count(3), 23)
            self.assertEqual(batch_sizes.count(2), 1)
            self.assertEqual(batch_sizes.count(1), 1)
            self.assertEqual(sum(batch_sizes), 72)
            self.assertEqual(
                len(list((run_dir / "prepared_requests").glob("*.json"))), 25
            )
            self.assertFalse((run_dir / "call_attempts.jsonl").exists())
            self.assertFalse((run_dir / "usage.jsonl").exists())
            self.assertEqual(
                z71.copied_input_fingerprint(run_dir), z71.SOURCE_MATERIAL_FINGERPRINT
            )
            self.assertEqual(
                z71.verify_prepared(run_dir, require_zero_call=True)["status"], "pass"
            )
            with self.assertRaisesRegex(Exception, "运行目录已存在"):
                z71.prepare(run_dir)

    def test_source_windows_are_located_substrings_and_nearby_eight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-windows"
            z71.prepare(run_dir)
            for path in sorted((run_dir / "prepared_requests").glob("*.json")):
                body = z71.read_json(path)
                payload = json.loads(body["messages"][1]["content"])
                chapter = int(payload["chapter"])
                chapter_text = z71._run_chapter_file(run_dir, chapter).read_text(
                    encoding="utf-8"
                )
                catalog = z71._catalog(run_dir, chapter)
                positions = {
                    row["anchor_id"]: index for index, row in enumerate(catalog)
                }
                for item in payload["items"]:
                    nearby_ids = [row["anchor_id"] for row in item["nearby_anchors"]]
                    for anchor in item["anchors"]:
                        center = positions[anchor["anchor_id"]]
                        expected = {
                            catalog[index]["anchor_id"]
                            for index in range(
                                max(0, center - 8),
                                min(len(catalog) - 1, center + 8) + 1,
                            )
                        }
                        self.assertTrue(expected.issubset(set(nearby_ids)))
                    seen_ranges = set()
                    for window in item["source_windows"]:
                        self.assertIn(window["text"], chapter_text)
                        self.assertNotEqual(window["text"], chapter_text)
                        key = (window["start_anchor_id"], window["end_anchor_id"])
                        self.assertNotIn(key, seen_ranges)
                        seen_ranges.add(key)

    def test_prompt_and_requests_exclude_answer_examples_and_eval_materials(
        self,
    ) -> None:
        for marker in z71.SYSTEM_PROHIBITED_MARKERS:
            self.assertNotIn(marker, z71.SYSTEM_PROMPT)
        self.assertIn("当前主体、当前动作属于同一事件", z71.SYSTEM_PROMPT)
        self.assertIn("疑义时保持原句", z71.SYSTEM_PROMPT)
        self.assertTrue(str(z71.SOURCE_RUN.name).startswith("Z68C_"))
        self.assertNotIn("Z70", str(z71.SOURCE_RUN))
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-prohibited"
            z71.prepare(run_dir)
            for path in (run_dir / "prepared_requests").glob("*.json"):
                body = z71.read_json(path)
                self.assertEqual(z71.request_prohibited_hits(body), [])
                self.assertEqual(body["model"], z71.MODEL)
                self.assertEqual(body["temperature"], 0.0)
                self.assertEqual(body["max_tokens"], 8000)
                self.assertEqual(body["n"], 1)
                self.assertEqual(body["reasoning_effort"], "medium")
                self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_success_uses_25_single_samples_and_429_retries_same_body(self) -> None:
        captured: list[dict] = []

        def opener(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            captured.append(body)
            if len(captured) == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {},
                    io.BytesIO(b"unit-rate-limit"),
                )
            return FakeResponse(response_for_body(body))

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-success"
            z71.prepare(run_dir)
            with (
                self.patched_transport(opener),
                mock.patch.dict(
                    os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
                ),
            ):
                result = z71.run(run_dir)
            self.assertEqual(result["logical_batches_completed"], 25)
            self.assertEqual(result["event_count"], 72)
            self.assertEqual(result["changed_events"], 0)
            self.assertEqual(len(captured), 26)
            self.assertEqual(captured[0], captured[1])
            receipt = z71.transport_receipt(run_dir)
            self.assertEqual(receipt["actual_network_attempts"], 26)
            self.assertEqual(len(receipt["logical_case_order"]), 25)
            self.assertTrue(receipt["same_request_on_network_retries"])

            before = {
                path.relative_to(run_dir).as_posix(): z71.z68.sha256_file(path)
                for path in run_dir.rglob("*")
                if path.is_file()
            }
            verification = z71.verify(run_dir)
            after = {
                path.relative_to(run_dir).as_posix(): z71.z68.sha256_file(path)
                for path in run_dir.rglob("*")
                if path.is_file()
            }
            self.assertEqual(verification["status"], "pass")
            self.assertEqual(before, after, "verify(run_dir) 必须纯只读")

            for chapter in z71.TARGET_CHAPTERS:
                source = z71.read_json(run_dir / f"inputs/events/ch{chapter:04d}.json")
                final = z71.read_json(run_dir / f"outputs/events/ch{chapter:04d}.json")
                z71.assert_final_compatible(source, final, chapter=chapter)
                self.assertEqual(source, final)
                diff = z71.read_json(
                    run_dir / f"sidecars/event_diffs/ch{chapter:04d}.json"
                )
                self.assertEqual(
                    set(diff),
                    {
                        "schema_version",
                        "chapter",
                        "source_event_count",
                        "changed_count",
                        "unchanged_count",
                        "events",
                    },
                )

    def _assert_first_batch_contract_failure(self, mutate, error_pattern: str) -> None:
        def opener(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            return FakeResponse(response_for_body(body, mutate))

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-invalid"
            z71.prepare(run_dir)
            with (
                self.patched_transport(opener),
                mock.patch.dict(
                    os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
                ),
            ):
                with self.assertRaisesRegex(Exception, error_pattern):
                    z71.run(run_dir)
            manifest = z71.read_json(run_dir / "run_manifest.json")
            hard_stop = z71.read_json(run_dir / "hard_stop.json")
            self.assertEqual(manifest["status"], "hard_stop")
            self.assertEqual(hard_stop["completed_batches"], [])
            self.assertEqual(hard_stop["next_batch"], "ch0003_b001")
            self.assertEqual(z71.verify(run_dir)["status"], "pass")

    def test_illegal_provenance_hard_stops(self) -> None:
        def mutate(output, payload):
            output["events"][0]["event"] += "并补入细节。"
            output["events"][0]["provenance_anchor_ids"] = ["E9999"]

        self._assert_first_batch_contract_failure(mutate, "provenance越出")

    def test_changed_event_id_hard_stops(self) -> None:
        def mutate(output, payload):
            output["events"][0]["event_id"] = "EV-C0003-99"

        self._assert_first_batch_contract_failure(mutate, "修改了event_id")

    def test_over_100_nonspace_characters_hard_stops(self) -> None:
        def mutate(output, payload):
            output["events"][0]["event"] = "人" * 101
            output["events"][0]["provenance_anchor_ids"] = [
                payload["items"][0]["nearby_anchors"][0]["anchor_id"]
            ]

        self._assert_first_batch_contract_failure(mutate, "越过6～100")

    def test_classification_label_is_rejected(self) -> None:
        def mutate(output, payload):
            output["events"][0]["event"] += "[A]"
            output["events"][0]["provenance_anchor_ids"] = [
                payload["items"][0]["nearby_anchors"][0]["anchor_id"]
            ]

        self._assert_first_batch_contract_failure(mutate, "分类标签")

    def test_keyboard_interrupt_is_persisted_as_hard_stop(self) -> None:
        def opener(request, timeout):
            raise KeyboardInterrupt("unit-interrupt")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-interrupt"
            z71.prepare(run_dir)
            with (
                self.patched_transport(opener),
                mock.patch.dict(
                    os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    z71.run(run_dir)
            self.assertEqual(
                z71.read_json(run_dir / "run_manifest.json")["status"], "hard_stop"
            )
            self.assertEqual(
                z71.read_json(run_dir / "hard_stop.json")["error_type"],
                "KeyboardInterrupt",
            )
            self.assertEqual(z71.verify(run_dir)["status"], "pass")
            with self.assertRaisesRegex(
                Exception, "运行权已被占用|正式运行痕迹|不是可首次开跑"
            ):
                z71.run(run_dir)

    def test_run_claim_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "z71-claim"
            z71.prepare(run_dir)
            z71.acquire_run_claim(run_dir)
            with self.assertRaisesRegex(Exception, "拒绝重复采样"):
                z71.acquire_run_claim(run_dir)


if __name__ == "__main__":
    unittest.main()
