from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tools.zbatch_modules import z83_retry_transport as transport


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def ok_outcome() -> transport.AttemptOutcome:
    return transport.AttemptOutcome(
        http_status=200,
        request_sha256=SHA_A,
        raw_response_sha256=SHA_B,
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        payload={"event": "x"},
        wire_body_sha256=SHA_C,
        request_artifact_sha256=SHA_A,
    )


def error_outcome(status: int, *, headers: dict[str, str] | None = None) -> transport.AttemptOutcome:
    return transport.AttemptOutcome(
        http_status=status,
        request_sha256=SHA_A,
        headers=headers or {},
        wire_body_sha256=SHA_C,
        request_artifact_sha256=SHA_A,
    )


class RetryTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temp.name) / "attempt_results.jsonl"
        self.clock = FakeClock()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_request(
        self,
        outcomes,
        *,
        state=None,
        chapter=3,
        jitter=lambda: 0.0,
        logical_request_id=None,
    ):
        queue = list(outcomes)

        def send_once(_attempt: int):
            return queue.pop(0)

        return transport.run_logical_request(
            logical_request_id=logical_request_id or f"ch{chapter}-case",
            chapter=chapter,
            send_once=send_once,
            attempt_ledger_path=self.ledger,
            contract_version="single-object-v1",
            state=state or transport.RetryRunState(),
            sleeper=self.clock.sleep,
            monotonic=self.clock.monotonic,
            jitter=jitter,
        )

    def read_rows(self):
        return [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]

    def test_success_writes_completed_attempt_and_five_part_checkpoint(self) -> None:
        result = self.run_request([ok_outcome()])
        rows = self.read_rows()
        self.assertEqual(1, len(rows))
        self.assertEqual("success", rows[0]["outcome"])
        self.assertEqual(12, rows[0]["usage"]["total_tokens"])
        self.assertEqual("pending", result.checkpoint["mechanical_verdict"])
        self.assertEqual("single-object-v1", result.checkpoint["contract_version"])
        transport.validate_checkpoint(result.checkpoint)

    def test_two_429_retries_then_success_use_5_and_10_second_backoff_plus_jitter(self) -> None:
        result = self.run_request(
            [error_outcome(429), error_outcome(429), ok_outcome()],
            jitter=lambda: 0.5,
        )
        self.assertEqual([6.0, 11.0], self.clock.sleeps)
        self.assertEqual(3, len(result.attempt_rows))
        rows = self.read_rows()
        self.assertEqual("unknown", rows[0]["usage"])
        self.assertEqual("unknown", rows[1]["usage"])
        self.assertIsNone(rows[0]["retry_wait_actual_seconds"])
        waits = transport.read_retry_wait_rows(self.ledger)
        self.assertEqual(["completed", "completed"], [row["status"] for row in waits])
        self.assertEqual([6.0, 11.0], [row["actual_seconds"] for row in waits])
        transport.validate_retry_wait_sequence(
            self.ledger, rows, require_all_429_completed=True
        )

    def test_429_is_fsynced_before_wait_and_interruption_gets_append_only_ticket(self) -> None:
        observed: list[list[dict[str, object]]] = []

        def interrupted_sleep(_seconds: float) -> None:
            observed.append(self.read_rows())
            raise RuntimeError("simulated interruption")

        with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
            transport.run_logical_request(
                logical_request_id="ch3-interrupted",
                chapter=3,
                send_once=lambda _attempt: error_outcome(429),
                attempt_ledger_path=self.ledger,
                contract_version="single-object-v1",
                state=transport.RetryRunState(),
                sleeper=interrupted_sleep,
                monotonic=self.clock.monotonic,
                jitter=lambda: 0.0,
            )
        self.assertEqual(1, len(observed))
        self.assertEqual(429, observed[0][0]["http_status"])
        self.assertIsNone(observed[0][0]["retry_wait_actual_seconds"])
        waits = transport.read_retry_wait_rows(self.ledger)
        self.assertEqual(1, len(waits))
        self.assertEqual("interrupted", waits[0]["status"])
        self.assertEqual("RuntimeError", waits[0]["interruption_type"])

    def test_third_429_is_hard_stop_and_all_three_results_remain_appended(self) -> None:
        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            self.run_request([error_outcome(429), error_outcome(429), error_outcome(429)])
        self.assertEqual("request_third_429", caught.exception.reason_code)
        self.assertEqual(3, len(self.read_rows()))

    def test_run_fifth_429_is_hard_stop(self) -> None:
        state = transport.RetryRunState(total_429=4)
        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            self.run_request([error_outcome(429)], state=state)
        self.assertEqual("run_fifth_429", caught.exception.reason_code)
        self.assertEqual(5, state.total_429)

    def test_retry_after_seconds_and_http_date(self) -> None:
        def now() -> datetime:
            return datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc)

        self.assertEqual(12.0, transport.parse_retry_after_seconds("12", now=now))
        self.assertEqual(
            30.0,
            transport.parse_retry_after_seconds("Wed, 22 Jul 2026 00:00:30 GMT", now=now),
        )

    def test_retry_after_over_300_hard_stops_without_sleep(self) -> None:
        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            self.run_request([error_outcome(429, headers={"Retry-After": "301"})])
        self.assertEqual("retry_after_over_300", caught.exception.reason_code)
        self.assertEqual([], self.clock.sleeps)

    def test_retry_after_can_extend_local_backoff(self) -> None:
        self.run_request([error_outcome(429, headers={"retry-after": "8"}), ok_outcome()])
        self.assertEqual([8.0], self.clock.sleeps)

    def test_401_403_and_5xx_never_retry(self) -> None:
        for status, reason in ((401, "http_401_no_retry"), (403, "http_403_no_retry"), (503, "http_5xx_no_retry")):
            with self.subTest(status=status):
                ledger = Path(self.temp.name) / f"attempt_{status}.jsonl"
                calls = []

                def send_once(attempt):
                    calls.append(attempt)
                    return error_outcome(status)

                with self.assertRaises(transport.RetryTransportHardStop) as caught:
                    transport.run_logical_request(
                        logical_request_id=f"case-{status}",
                        chapter=3,
                        send_once=send_once,
                        attempt_ledger_path=ledger,
                        contract_version="v1",
                        state=transport.RetryRunState(),
                        sleeper=lambda _seconds: None,
                        monotonic=lambda: 0.0,
                    )
                self.assertEqual(reason, caught.exception.reason_code)
                self.assertEqual([1], calls)

    def test_network_error_never_retries_and_keeps_distinct_reason(self) -> None:
        calls = []

        def send_once(attempt):
            calls.append(attempt)
            return transport.AttemptOutcome(
                http_status=598,
                request_sha256=SHA_A,
                wire_body_sha256=SHA_C,
                request_artifact_sha256=SHA_A,
                error_code="transport_URLError",
            )

        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            transport.run_logical_request(
                logical_request_id="network-error",
                chapter=3,
                send_once=send_once,
                attempt_ledger_path=self.ledger,
                contract_version="v1",
                state=transport.RetryRunState(),
                sleeper=lambda _seconds: None,
                monotonic=lambda: 0.0,
            )
        self.assertEqual("transport_error_no_retry", caught.exception.reason_code)
        self.assertEqual([1], calls)

    def test_same_chapter_and_cross_chapter_spacing(self) -> None:
        state = transport.RetryRunState()
        self.run_request([ok_outcome()], state=state, chapter=3, logical_request_id="ch3-a")
        self.clock.value += 2
        self.run_request([ok_outcome()], state=state, chapter=3, logical_request_id="ch3-b")
        self.clock.value += 3
        self.run_request([ok_outcome()], state=state, chapter=13, logical_request_id="ch13-a")
        self.assertEqual([8.0, 27.0], self.clock.sleeps)

    def test_retry_request_sha_drift_hard_stops(self) -> None:
        drifted = transport.AttemptOutcome(
            http_status=429,
            request_sha256=SHA_B,
            wire_body_sha256=SHA_C,
            request_artifact_sha256=SHA_A,
        )
        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            self.run_request([error_outcome(429), drifted])
        self.assertEqual("retry_request_drift", caught.exception.reason_code)

    def test_retry_wire_sha_drift_hard_stops(self) -> None:
        drifted = transport.AttemptOutcome(
            http_status=200,
            request_sha256=SHA_A,
            raw_response_sha256=SHA_B,
            usage={"total_tokens": 1},
            wire_body_sha256="d" * 64,
            request_artifact_sha256=SHA_A,
        )
        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            self.run_request([error_outcome(429), drifted])
        self.assertEqual("retry_wire_or_artifact_drift", caught.exception.reason_code)

    def test_same_logical_request_cannot_be_sent_twice(self) -> None:
        self.run_request([ok_outcome()], logical_request_id="same-id")
        with self.assertRaises(transport.RetryTransportHardStop) as caught:
            self.run_request([ok_outcome()], logical_request_id="same-id")
        self.assertEqual("logical_request_already_attempted", caught.exception.reason_code)

    def test_checkpoint_validator_rejects_extra_fields(self) -> None:
        checkpoint = transport.build_checkpoint(
            request_sha256=SHA_A,
            raw_response_sha256=SHA_B,
            usage={"total_tokens": 1},
            attempt_rows=[{
                "schema": transport.ATTEMPT_LEDGER_SCHEMA,
                "logical_request_id": "x",
                "chapter": 3,
                "attempt": 1,
                "http_status": 200,
                "outcome": "success",
                "request_sha256": SHA_A,
                "raw_response_sha256": SHA_B,
                "usage": {"total_tokens": 1},
                "retry_after_seconds": None,
            }],
            contract_version="v1",
        )
        checkpoint["semantic_truth"] = "forbidden"
        with self.assertRaises(transport.ZBatchError):
            transport.validate_checkpoint(checkpoint)

    def test_attempt_validator_rejects_429_usage_zero(self) -> None:
        row = {
            "schema": transport.ATTEMPT_LEDGER_SCHEMA,
            "logical_request_id": "x",
            "chapter": 3,
            "attempt": 1,
            "http_status": 429,
            "outcome": "http_error",
            "request_sha256": SHA_A,
            "raw_response_sha256": None,
            "usage": {"total_tokens": 0},
            "retry_after_seconds": None,
        }
        with self.assertRaises(transport.ZBatchError):
            transport.validate_attempt_rows([row])

    def test_five_file_checkpoint_is_exclusive_and_has_no_self_hash_cycle(self) -> None:
        result = self.run_request([ok_outcome()])
        root = Path(self.temp.name) / "checkpoint"
        seal = transport.write_checkpoint_bundle(
            root,
            request_record={
                "schema": "z83-retry13-checkpoint-request-v1",
                "logical_request_id": "ch3-case",
                "request_artifact_path": "requests/ch3-case.json",
                "request_artifact_sha256": SHA_A,
                "wire_body_sha256": SHA_C,
                "model": "deepseek-v4-flash",
                "stage": "targeted_retry_single_object",
                "contract_version": "single-object-v1",
            },
            response_record={
                "schema": "z83-retry13-checkpoint-response-v1",
                "logical_request_id": "ch3-case",
                "request_artifact_sha256": SHA_A,
                "http_status": 200,
                "raw_response_path": "raw/ch3-case.json",
                "raw_response_sha256": SHA_B,
                "response_model": "deepseek-v4-flash",
                "finish_reason": "stop",
                "content_sha256": SHA_C,
                "error_code": None,
            },
            usage_record={
                "schema": "z83-retry13-checkpoint-usage-v1",
                "logical_request_id": "ch3-case",
                "request_artifact_sha256": SHA_A,
                "raw_response_sha256": SHA_B,
                "usage": {"total_tokens": 12},
            },
            attempt_rows=result.attempt_rows,
            contract_version="single-object-v1",
            mechanical_verdict="pass",
        )
        self.assertEqual(64, len(seal["checkpoint_id"]))
        self.assertEqual(seal, transport.validate_checkpoint_bundle(root))
        with self.assertRaises(transport.ZBatchError):
            transport.write_checkpoint_bundle(
                root,
                request_record={},
                response_record={},
                usage_record={},
                attempt_rows=result.attempt_rows,
                contract_version="single-object-v1",
                mechanical_verdict="pass",
            )

        extra = root / "06_forbidden.json"
        extra.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(transport.ZBatchError, "第六件"):
            transport.validate_checkpoint_bundle(root)

    def test_empty_records_cannot_be_sealed_as_pass(self) -> None:
        result = self.run_request([ok_outcome()])
        with self.assertRaises(transport.ZBatchError):
            transport.write_checkpoint_bundle(
                Path(self.temp.name) / "empty-pass",
                request_record={},
                response_record={},
                usage_record={},
                attempt_rows=result.attempt_rows,
                contract_version="single-object-v1",
                mechanical_verdict="pass",
            )


if __name__ == "__main__":
    unittest.main()
