from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from zbatch_modules import api_transport, stage_sampling  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402
import zbatch  # noqa: E402


CONTRACT_PATH = ROOT / "config/contracts/sensenova_stage_sampling_v1.json"
Z00M_RUN = ROOT / "runs/Z00m_X01_第6至10章分类收权单变量复跑_5章_v1.0_20260717"


class FakeResponse:
    status = 200
    headers = {
        "Content-Type": "application/json",
        "X-Request-Id": "test-request",
        "Set-Cookie": "must-not-persist",
    }

    def __init__(self, payload: dict):
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.raw


class RawResponse(FakeResponse):
    def __init__(self, raw: bytes):
        self.raw = raw


class IncompleteResponse(FakeResponse):
    def __init__(self):
        super().__init__({})

    def read(self) -> bytes:
        raise http.client.IncompleteRead(b"partial-response-secret", 100)


def response_payload(content: str = '{"ok": true}') -> dict:
    return {
        "model": "deepseek-v4-flash",
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class ApiTransportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy = stage_sampling.load_contract_bundle(CONTRACT_PATH, profile="legacy_reference")
        cls.z00m = stage_sampling.load_contract_bundle(CONTRACT_PATH, profile="z00m_transport_reference")
        cls.route = api_transport.TransportRoute.from_mapping(cls.legacy.route)
        cls.messages = [
            {"role": "system", "content": "只输出 JSON。"},
            {"role": "user", "content": "测试"},
        ]

    def test_retired_runner_is_archived_and_current_runner_keeps_thin_compatibility_names(self):
        digest = hashlib.sha256((ROOT / "tools/zbatch.py").read_bytes()).hexdigest()
        config = json.loads(
            (ROOT / "config/batches/Z00s_X01_20章分类正门兼容_20章_v1.0.json").read_text(
                encoding="utf-8"
            )
        )
        archive = ROOT / "runs/Z00z_X01_局部段覆盖试点_ch0003_v1.0_20260718/provenance/runner_zbatch.py"
        archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(archive_digest, config["runner_sha256"])
        self.assertNotEqual(digest, config["runner_sha256"])
        self.assertNotEqual(digest, "cc4f42f798f8f537524f5a458008ae76f0bbbfea8588c7618dc03be17cbe437b")
        self.assertIs(zbatch.ZBatchError, ZBatchError)
        source = (ROOT / "tools/zbatch.py").read_text(encoding="utf-8")
        self.assertIn("from zbatch_modules import", source)
        self.assertNotIn("import urllib.request", source)
        self.assertNotIn("http.client.HTTPSConnection", source)
        for name in ("z00l_classification_split.py", "z00m_classification_split.py"):
            self.assertNotIn("zbatch_modules", (ROOT / "tools" / name).read_text(encoding="utf-8"))

    def test_sidecar_modules_do_not_import_old_monolith(self):
        for name in ("api_transport.py", "stage_sampling.py"):
            path = ROOT / "tools/zbatch_modules" / name
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            self.assertFalse(any(item == "zbatch" or item.startswith("zbatch.") for item in imports), name)

    def test_contract_has_explicit_stage_values_and_mechanical_nulls(self):
        self.assertEqual(set(self.legacy.stages), {"extract", "thin", "fold", "answer", "compare"})
        self.assertTrue(all(contract.n == 1 for contract in self.legacy.stages.values()))
        self.assertTrue(all(contract.temperature == 0.2 for contract in self.legacy.stages.values()))
        self.assertEqual(self.z00m.stage("extract").max_tokens, 16000)
        self.assertEqual(self.z00m.stage("extract").n, 1)
        self.assertEqual(set(self.legacy.mechanical_modules), {
            "evidence_catalog",
            "anchor_kit",
            "candidate_envelope",
            "classify_rules",
            "prompt_render_pin",
            "downstream_validate",
        })
        self.assertTrue(all(item["temperature"] is None for item in self.legacy.mechanical_modules.values()))

    def test_candidate_temperatures_are_registered_but_not_callable_by_default(self):
        self.assertEqual(self.legacy.candidates["thin"].temperature, 0.3)
        self.assertEqual(self.legacy.candidates["fold"].temperature, 0.3)
        self.assertEqual(self.legacy.candidates["answer"].temperature, 0.3)
        self.assertEqual(self.legacy.candidates["compare"].temperature, 0.2)
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            transport = api_transport.ApiTransport(
                route=self.route,
                contracts=self.legacy.candidates,
                run_dir=Path(temp_dir),
                max_calls=1,
            )
            with self.assertRaisesRegex(ZBatchError, "未验证候选参数"):
                transport.request_body(stage="thin", messages=self.messages)

    def test_n_must_be_explicitly_one_and_missing_stage_has_no_fallback(self):
        bad = {
            "temperature": 0.2,
            "max_tokens": 100,
            "n": 2,
            "reasoning_effort": "medium",
            "response_format": {"type": "json_object"},
            "status": "baseline_reference",
        }
        with self.assertRaisesRegex(ZBatchError, "只允许 n=1"):
            stage_sampling.StageSamplingContract.from_mapping("extract", bad)
        bad["n"] = 1.5
        with self.assertRaisesRegex(ZBatchError, "n 必须是整数 1"):
            stage_sampling.StageSamplingContract.from_mapping("extract", bad)
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            transport = api_transport.ApiTransport.from_bundle(
                self.legacy, run_dir=Path(temp_dir), max_calls=1
            )
            with self.assertRaisesRegex(ZBatchError, "没有阶段级采样合同"):
                transport.request_body(stage="unknown", messages=self.messages)

    def test_route_allows_only_deepseek_v4_flash(self):
        raw = dict(self.legacy.route)
        raw["model"] = "sensenova-6.7-flash-lite"
        raw["allowed_models"] = ["deepseek-v4-flash", "sensenova-6.7-flash-lite"]
        with self.assertRaisesRegex(ZBatchError, "只允许模型 deepseek-v4-flash"):
            api_transport.TransportRoute.from_mapping(raw)
        misplaced = dict(self.legacy.route)
        misplaced["temperature"] = 0.2
        with self.assertRaisesRegex(ZBatchError, "路由层混入阶段采样字段"):
            api_transport.TransportRoute.from_mapping(misplaced)
        wrong_key_env = dict(self.legacy.route)
        wrong_key_env["api_key_env"] = "SENSOVA_API_KEY"
        with self.assertRaisesRegex(ZBatchError, "api_key_env 必须钉死"):
            api_transport.TransportRoute.from_mapping(wrong_key_env)

    def test_legacy_profile_matches_old_provider_values_plus_explicit_n(self):
        provider = json.loads((ROOT / "config/providers/sensenova.json").read_text(encoding="utf-8"))
        for stage, contract in self.legacy.stages.items():
            self.assertEqual(contract.temperature, provider["temperature"])
            self.assertEqual(contract.max_tokens, provider["max_tokens_by_stage"][stage])
            self.assertEqual(contract.reasoning_effort, provider["reasoning_effort"])
            self.assertEqual(contract.n, 1)

    def test_z00m_real_request_body_matches_stage_contract_exactly(self):
        stored = json.loads((Z00M_RUN / "requests/extract/ch0006_request.json").read_text(encoding="utf-8"))
        rebuilt = api_transport.build_request_body(
            model=self.route.model,
            messages=stored["body"]["messages"],
            contract=self.z00m.stage("extract"),
        )
        self.assertEqual(rebuilt, stored["body"])

    def test_fake_success_preserves_raw_response_and_never_persists_key(self):
        secret = "sidecar-super-secret"
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport.from_bundle(
                self.z00m,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: FakeResponse(response_payload()),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: secret}, clear=False):
                result = transport.call(stage="extract", case_id="unit", messages=self.messages)
            self.assertEqual(result.content, '{"ok": true}')
            self.assertEqual(json.loads(result.raw_response.decode("utf-8")), response_payload())
            self.assertEqual(result.metadata["sampling_n"], 1)
            self.assertEqual(result.metadata["stage_temperature"], 0.2)
            self.assertEqual(result.metadata["stage_max_tokens"], 16000)
            request = json.loads((run_dir / "requests/extract/unit_request.json").read_text(encoding="utf-8"))
            self.assertEqual(request["body"]["n"], 1)
            self.assertNotIn("Authorization", json.dumps(request))
            for path in run_dir.rglob("*"):
                if path.is_file():
                    self.assertNotIn(secret.encode("utf-8"), path.read_bytes(), str(path))
            meta = json.loads((run_dir / "responses/extract/unit_meta.json").read_text(encoding="utf-8"))
            self.assertNotIn("Set-Cookie", meta["headers"])

    def test_reflected_key_rejects_response_before_raw_is_written(self):
        secret = "reflected-secret"
        raw = json.dumps(response_payload(content=secret)).encode("utf-8")
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport.from_bundle(
                self.z00m,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: RawResponse(raw),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: secret}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "回显 API Key"):
                    transport.call(stage="extract", case_id="echo", messages=self.messages)
            self.assertFalse((run_dir / "responses/extract/echo_raw.json").exists())

    def test_response_model_mismatch_is_rejected_and_audited(self):
        payload = response_payload()
        payload["model"] = "unexpected-model"
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport.from_bundle(
                self.z00m,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: FakeResponse(payload),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "响应模型与请求不一致"):
                    transport.call(stage="extract", case_id="wrong_model", messages=self.messages)
            error_text = (run_dir / "errors/extract_wrong_model_response.txt").read_text(encoding="utf-8")
            self.assertIn("reason_code=response_model_mismatch", error_text)
            self.assertNotIn("unexpected-model", error_text)
            self.assertFalse((run_dir / "responses/extract/wrong_model_meta.json").exists())

    def test_http_200_invalid_json_has_failure_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport.from_bundle(
                self.z00m,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: RawResponse(b'{"broken":'),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "响应不是 JSON"):
                    transport.call(stage="extract", case_id="invalid_json", messages=self.messages)
            self.assertTrue((run_dir / "responses/extract/invalid_json_raw.json").is_file())
            error_text = (run_dir / "errors/extract_invalid_json_response.txt").read_text(encoding="utf-8")
            self.assertIn("reason_code=http_200_invalid_json", error_text)

    def test_valid_json_with_length_finish_reason_is_rejected(self):
        payload = response_payload(content='{"schema_version":"z-event-v1","chapter":6,"events":[]}')
        payload["choices"][0]["finish_reason"] = "length"
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport.from_bundle(
                self.z00m,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: FakeResponse(payload),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "finish_reason=length"):
                    transport.call(stage="extract", case_id="length_json", messages=self.messages)
            self.assertTrue((run_dir / "responses/extract/length_json_raw.json").is_file())
            self.assertFalse((run_dir / "responses/extract/length_json_meta.json").exists())
            error_text = (run_dir / "errors/extract_length_json_response.txt").read_text(encoding="utf-8")
            self.assertIn("reason_code=response_finish_reason_not_stop", error_text)
            self.assertIn("raw_response_persisted=true", error_text)

    def test_shared_run_directory_has_one_atomic_call_budget(self):
        calls = []

        def opener(request, timeout):
            calls.append(request)
            return FakeResponse(response_payload())

        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            first = api_transport.ApiTransport.from_bundle(
                self.z00m, run_dir=run_dir, max_calls=1, opener=opener
            )
            second = api_transport.ApiTransport.from_bundle(
                self.z00m, run_dir=run_dir, max_calls=1, opener=opener
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                first.call(stage="extract", case_id="first", messages=self.messages)
                with self.assertRaisesRegex(ZBatchError, "调用闸已满：1/1"):
                    second.call(stage="extract", case_id="second", messages=self.messages)
            self.assertEqual(len(calls), 1)
            attempts = (run_dir / "call_attempts.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(attempts), 1)
            self.assertFalse((run_dir / "requests/extract/second_request.json").exists())

    def test_explicit_candidate_override_is_written_to_request_and_meta(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport(
                route=self.route,
                contracts=self.legacy.candidates,
                run_dir=run_dir,
                max_calls=1,
                allow_unverified_candidates=True,
                opener=lambda request, timeout: FakeResponse(response_payload()),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                transport.call(stage="thin", case_id="candidate", messages=self.messages)
            request = json.loads((run_dir / "requests/thin/candidate_request.json").read_text(encoding="utf-8"))
            meta = json.loads((run_dir / "responses/thin/candidate_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(request["contract_status"], "candidate_unverified")
            self.assertTrue(request["unverified_candidate_override"])
            self.assertTrue(meta["unverified_candidate_override"])

    def test_key_in_prompt_and_path_traversal_are_rejected_before_write(self):
        secret = "prompt-secret-key"
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport.from_bundle(
                self.z00m,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: FakeResponse(response_payload()),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: secret}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "请求内容意外包含 API Key"):
                    transport.call(
                        stage="extract",
                        case_id="secret",
                        messages=[{"role": "user", "content": f"误贴：{secret}"}],
                    )
                with self.assertRaisesRegex(ZBatchError, "case_id 不安全"):
                    transport.call(stage="extract", case_id="../escape", messages=self.messages)
            self.assertFalse(any(run_dir.rglob("*_request.json")))

    def test_http_error_body_is_hashed_not_persisted(self):
        secret_body = b"server-error-secret"
        error = urllib.error.HTTPError(
            self.route.url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(secret_body),
        )
        route = replace(self.route, network_attempts=1)
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport(
                route=route,
                contracts=self.z00m.stages,
                run_dir=run_dir,
                max_calls=1,
                opener=lambda request, timeout: (_ for _ in ()).throw(error),
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "API 调用失败"):
                    transport.call(stage="extract", case_id="error", messages=self.messages)
            error_text = next((run_dir / "errors").glob("*.txt")).read_text(encoding="utf-8")
            self.assertNotIn(secret_body.decode("utf-8"), error_text)
            self.assertIn(hashlib.sha256(secret_body).hexdigest(), error_text)
            self.assertIn("error_body_not_persisted=security_policy", error_text)

    def test_incomplete_response_retries_without_persisting_partial_body(self):
        route = replace(self.route, network_attempts=2)
        responses = iter([IncompleteResponse(), FakeResponse(response_payload())])
        sleeps = []
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            transport = api_transport.ApiTransport(
                route=route,
                contracts=self.z00m.stages,
                run_dir=run_dir,
                max_calls=2,
                opener=lambda request, timeout: next(responses),
                sleeper=sleeps.append,
            )
            with mock.patch.dict(os.environ, {self.route.api_key_env: "unit-key"}, clear=False):
                result = transport.call(stage="extract", case_id="retry", messages=self.messages)
            self.assertEqual(result.finish_reason, "stop")
            self.assertEqual(transport.calls_made, 2)
            self.assertEqual(sleeps, [2])
            error_text = next((run_dir / "errors").glob("*.txt")).read_text(encoding="utf-8")
            self.assertNotIn("partial-response-secret", error_text)
            self.assertIn("partial_body_not_persisted=security_and_integrity_policy", error_text)


if __name__ == "__main__":
    unittest.main()
