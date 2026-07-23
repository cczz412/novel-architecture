from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import zbatch  # noqa: E402
from zbatch_modules import classify_rules, neutral_extract  # noqa: E402
from zbatch_modules.errors import ZBatchError  # noqa: E402


CONFIG = ROOT / "config/batches/D-MOD-002_X01_接线切流零调用重放_5章_v1.0.json"
CURRENT_CONFIG = ROOT / "config/batches/Z00s_X01_20章分类正门兼容_20章_v1.0.json"
SOURCE_RUN = ROOT / "runs/Z00n_X01_第6至10章程序清点单变量_5章_v1.1_20260717"
BOOK = ROOT / "TEMP/X批材料包_20260716/books/X01_诡秘之主"
CURRENT_SOURCE_PINS = {
    "tools/zbatch_modules/classify_rules.py": "eed588211111f89f5c6968c490686124bf94e7cd09d65aee3f1bc02dd9011104",
    "tools/zbatch_modules/README.md": "d00fa021517984b5279b3886ed2b63541da292d8a1569c4e35dafeb0d72d9480",
}


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json", "X-Request-Id": "cutover-test"}

    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class ZBatchCutoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch, cls.provider = zbatch.load_configs(CONFIG)
        cls.chapters = zbatch.load_chapters(BOOK, 6, 10)
        cls.contract = classify_rules.load_contract(
            ROOT / "config/contracts/classify_rules_v1.json",
            project_root=ROOT,
        )
        cls.decisions = classify_rules.promote_approved_reference(cls.contract, project_root=ROOT)

    def source_documents(self):
        documents = []
        catalogs = {}
        for chapter in range(6, 11):
            stored = zbatch.read_json(SOURCE_RUN / f"01_event_extract/parsed/ch{chapter:04d}.json")
            catalog = zbatch.read_json(
                SOURCE_RUN / f"01_event_extract/evidence_catalogs/ch{chapter:04d}.json"
            )["entries"]
            documents.append(stored)
            catalogs[chapter] = {row["anchor_id"]: row["quote"] for row in catalog}
        return documents, catalogs

    def test_shared_error_class_is_exact_same_object(self):
        self.assertIs(zbatch.ZBatchError, ZBatchError)
        self.assertIs(zbatch.modular_api_transport.ZBatchError, ZBatchError)
        self.assertIs(zbatch.modular_classify_rules.ZBatchError, ZBatchError)

    def test_cutover_has_one_fixed_profile_and_no_runtime_legacy_switch(self):
        self.assertEqual(zbatch.ACTIVE_STAGE_PROFILE, "d_mod_cutover_v1")
        self.assertFalse(any(key in self.batch for key in ("use_legacy", "legacy_mode", "pipeline_mode")))
        self.assertTrue(callable(zbatch.legacy_stage_extract))
        source = inspect.getsource(zbatch.run_pipeline)
        self.assertIn("stage_extract(ctx", source)
        self.assertNotIn("legacy_stage_extract", source)

    def test_only_deepseek_v4_flash_is_callable(self):
        self.assertEqual(zbatch.ALLOWED_TEXT_MODELS, {"deepseek-v4-flash"})
        self.assertEqual(self.provider["model"], "deepseek-v4-flash")
        self.assertEqual(self.provider["allowed_models"], ["deepseek-v4-flash"])

    def test_zero_call_preflight_passes_without_loading_key(self):
        frozen = zbatch.read_json(CURRENT_CONFIG)
        frozen["runner_sha256"] = zbatch.sha256_file(ROOT / "tools/zbatch.py")
        frozen["pinned_sha256"]["tools/zbatch_modules/__init__.py"] = zbatch.sha256_file(
            ROOT / "tools/zbatch_modules/__init__.py"
        )
        old_neutral_sha = frozen["pinned_sha256"][
            "tools/zbatch_modules/neutral_extract.py"
        ]
        self.assertEqual(
            old_neutral_sha,
            "f567ebef481dc33775ba7974c09744d185d6b8fa2b7b5e947e0be89f145dd7a7",
        )
        frozen["pinned_sha256"]["tools/zbatch_modules/neutral_extract.py"] = (
            zbatch.sha256_file(ROOT / "tools/zbatch_modules/neutral_extract.py")
        )
        self.assertNotEqual(
            frozen["pinned_sha256"]["tools/zbatch_modules/neutral_extract.py"],
            old_neutral_sha,
        )
        for relative, expected_sha in CURRENT_SOURCE_PINS.items():
            self.assertEqual(zbatch.sha256_file(ROOT / relative), expected_sha)
            frozen["pinned_sha256"][relative] = expected_sha
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            config_path = Path(temp_dir) / "current_source_cutover.json"
            zbatch.write_json(config_path, frozen)
            with mock.patch.dict(os.environ, {}, clear=True):
                result = zbatch.preflight(config_path, require_key=False)
        self.assertEqual(result["preflight"], "pass")
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(all(row["ok"] for row in result["checks"]))

    def test_active_transport_rejects_length_finish_reason(self):
        response = {
            "model": "deepseek-v4-flash",
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "length"}],
            "usage": {"total_tokens": 2},
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            ctx = zbatch.RunContext({"max_calls": 1}, self.provider, Path(temp_dir))
            ctx.transport.opener = mock.Mock(return_value=FakeResponse(response))
            with mock.patch.dict(os.environ, {"SENSENOVA_API_KEY": "unit-key"}, clear=False):
                with self.assertRaisesRegex(ZBatchError, "finish_reason=length"):
                    ctx.call_json(
                        stage="neutral_extract",
                        case_id="length_gate",
                        messages=[{"role": "user", "content": "test"}],
                    )
            failure = Path(temp_dir) / "errors/neutral_extract_length_gate_response.txt"
            self.assertTrue(failure.is_file())
            self.assertIn("reason_code=response_finish_reason_not_stop", failure.read_text(encoding="utf-8"))

    def test_regression_gate_blocks_compiler_before_compile(self):
        with mock.patch.object(
            zbatch.modular_classify_rules,
            "regression_reasons",
            return_value=["approved_case_drift"],
        ), mock.patch.object(zbatch.modular_classify_rules, "compile_records") as compiler:
            with self.assertRaisesRegex(ZBatchError, "分类个案回归闸失败"):
                zbatch.compile_with_regression_gate(
                    [],
                    self.decisions,
                    contract=self.contract,
                    chapters={},
                    catalogs={},
                )
        compiler.assert_not_called()

    def test_new_batch_decisions_use_approved_reference_for_regression_only(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            decision_path = Path(temp_dir) / "current_decisions.json"
            current = {
                "schema_version": self.contract.decision_schema_version,
                "run_id": "Z00s_contract_entry_test",
                "rules_sha256": self.contract.rules_sha256,
                "decisions": [],
            }
            zbatch.write_json(decision_path, current)
            batch = dict(self.batch)
            batch.update({
                "run_id": current["run_id"],
                "classification_decisions": zbatch.rel(decision_path),
                "classification_decisions_sha256": zbatch.sha256_file(decision_path),
            })

            contract, loaded, regression_reference = zbatch._classification_inputs(batch)

        self.assertEqual(contract, self.contract)
        self.assertEqual(loaded, current)
        self.assertEqual(regression_reference["run_id"], self.contract.predecessor_run_id)
        self.assertEqual(
            classify_rules.regression_reasons(regression_reference, contract=self.contract),
            [],
        )

    def test_new_batch_decisions_must_match_batch_run_id(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            decision_path = Path(temp_dir) / "wrong_run.json"
            zbatch.write_json(decision_path, {
                "schema_version": self.contract.decision_schema_version,
                "run_id": "not-this-batch",
                "rules_sha256": self.contract.rules_sha256,
                "decisions": [],
            })
            batch = dict(self.batch)
            batch.update({
                "run_id": "expected-batch",
                "classification_decisions": zbatch.rel(decision_path),
                "classification_decisions_sha256": zbatch.sha256_file(decision_path),
            })
            with self.assertRaisesRegex(ZBatchError, "run_id 与批次不一致"):
                zbatch._classification_inputs(batch)

    def test_new_batch_cannot_reuse_approved_decisions_without_replay_marker(self):
        batch = dict(self.batch)
        batch["run_id"] = "new-batch-must-have-own-decisions"
        batch.pop("replay_source_run_id", None)
        with self.assertRaisesRegex(ZBatchError, "只允许显式历史回放"):
            zbatch._classification_inputs(batch)

    def test_current_decisions_sha_drift_stops_before_loading(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            decision_path = Path(temp_dir) / "current_decisions.json"
            zbatch.write_json(decision_path, {
                "schema_version": self.contract.decision_schema_version,
                "run_id": "sha-drift-test",
                "rules_sha256": self.contract.rules_sha256,
                "decisions": [],
            })
            batch = dict(self.batch)
            batch.update({
                "run_id": "sha-drift-test",
                "classification_decisions": zbatch.rel(decision_path),
                "classification_decisions_sha256": "0" * 64,
            })
            with self.assertRaisesRegex(ZBatchError, "主控分类决定 SHA 漂移"):
                zbatch._classification_inputs(batch)

    def test_compiler_uses_current_decisions_after_separate_regression_gate(self):
        current = {"run_id": "current", "decisions": []}
        approved_reference = {"run_id": "approved", "decisions": []}
        compilation = {"records": []}
        validation = {"invalid_total": 0}
        with mock.patch.object(
            zbatch.modular_classify_rules,
            "regression_reasons",
            return_value=[],
        ) as regression, mock.patch.object(
            zbatch.modular_classify_rules,
            "compile_records",
            return_value=compilation,
        ) as compiler, mock.patch.object(
            zbatch.modular_classify_rules,
            "validate_compiled_records",
            return_value=validation,
        ):
            actual = zbatch.compile_with_regression_gate(
                [],
                current,
                contract=self.contract,
                chapters={},
                catalogs={},
                regression_decisions_data=approved_reference,
            )

        self.assertEqual(actual, (compilation, validation))
        regression.assert_called_once_with(approved_reference, contract=self.contract)
        compiler.assert_called_once_with(
            [], current, contract=self.contract, evidence_catalogs={}
        )

    def test_empty_regression_reference_does_not_fall_back_to_current_decisions(self):
        current = {"run_id": "current", "decisions": []}
        with mock.patch.object(
            zbatch.modular_classify_rules,
            "regression_reasons",
            return_value=["bad-approved-reference"],
        ) as regression, mock.patch.object(
            zbatch.modular_classify_rules,
            "compile_records",
        ) as compiler:
            with self.assertRaisesRegex(ZBatchError, "分类个案回归闸失败"):
                zbatch.compile_with_regression_gate(
                    [],
                    current,
                    contract=self.contract,
                    chapters={},
                    catalogs={},
                    regression_decisions_data={},
                )
        regression.assert_called_once_with({}, contract=self.contract)
        compiler.assert_not_called()

    def test_stage_classify_keeps_current_and_regression_inputs_separate(self):
        current = {"run_id": "current", "decisions": []}
        approved_reference = {"run_id": "approved", "decisions": []}
        compilation = {
            "candidate_envelopes": {},
            "resolved_decisions": [],
            "classification_conflicts": {},
            "metrics": {"candidate_total": 0},
        }
        validation = {
            "rows": [],
            "valid_total": 0,
            "invalid_total": 0,
            "anchor_valid_rate": 0.0,
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            chapter = 6
            zbatch.write_json(
                run_dir / f"01_extract/events/ch{chapter:04d}.json",
                zbatch.read_json(SOURCE_RUN / f"01_event_extract/parsed/ch{chapter:04d}.json"),
            )
            zbatch.write_json(
                run_dir / f"01_extract/evidence_catalogs/ch{chapter:04d}.json",
                zbatch.read_json(
                    SOURCE_RUN / f"01_event_extract/evidence_catalogs/ch{chapter:04d}.json"
                ),
            )
            zbatch.write_json(run_dir / "01_extract/metrics.json", {})
            ctx = zbatch.RunContext(self.batch, self.provider, run_dir)
            with mock.patch.object(
                zbatch,
                "_classification_inputs",
                return_value=(self.contract, current, approved_reference),
            ), mock.patch.object(
                zbatch,
                "compile_with_regression_gate",
                return_value=(compilation, validation),
            ) as compile_gate:
                zbatch.stage_classify(ctx, {chapter: self.chapters[chapter]})

        args, kwargs = compile_gate.call_args
        self.assertIs(args[1], current)
        self.assertIs(kwargs["regression_decisions_data"], approved_reference)

    def test_five_chapter_real_artifact_replay_is_byte_equivalent(self):
        documents = []
        catalogs = {}
        audits_same = True
        events_same = True
        for chapter in range(6, 11):
            stored = zbatch.read_json(SOURCE_RUN / f"01_event_extract/parsed/ch{chapter:04d}.json")
            catalog = zbatch.read_json(
                SOURCE_RUN / f"01_event_extract/evidence_catalogs/ch{chapter:04d}.json"
            )["entries"]
            materialized, audit = neutral_extract.process_model_data(
                zbatch._raw_neutral_event_document(stored),
                chapter=chapter,
                catalog=catalog,
            )
            events_same &= materialized == stored
            audits_same &= audit == zbatch.read_json(
                SOURCE_RUN / f"01_event_extract/program_audits/ch{chapter:04d}.json"
            )
            documents.append(materialized)
            catalogs[chapter] = {row["anchor_id"]: row["quote"] for row in catalog}

        compilation, validation = zbatch.compile_with_regression_gate(
            documents,
            self.decisions,
            contract=self.contract,
            chapters=self.chapters,
            catalogs=catalogs,
        )
        gold = zbatch.read_json(SOURCE_RUN / "03_verify/valid_records.json")["records"]
        self.assertTrue(events_same)
        self.assertTrue(audits_same)
        self.assertEqual(compilation["records"], gold)
        self.assertEqual(compilation["metrics"]["by_type"], {"A": 28, "B": 9, "C": 3, "D": 3})
        self.assertEqual(validation["invalid_total"], 0)

    def test_candidate_envelope_only_has_approved_rules_sha_metadata_delta(self):
        documents, catalogs = self.source_documents()
        compilation, _ = zbatch.compile_with_regression_gate(
            documents,
            self.decisions,
            contract=self.contract,
            chapters=self.chapters,
            catalogs=catalogs,
        )
        for chapter in range(6, 11):
            historical = zbatch.read_json(SOURCE_RUN / f"02_classify/parsed/ch{chapter:04d}.json")
            active = compilation["candidate_envelopes"][chapter]
            historical_marker = historical.pop("decision_markers")
            active_marker = active.pop("decision_markers")
            self.assertEqual(active, historical, chapter)
            self.assertEqual(
                historical_marker,
                [
                    "分类权由主控规则执行；弱模型仅交中性事件。"
                    f"规则SHA={self.contract.predecessor_rules_sha256}"
                ],
            )
            self.assertEqual(
                active_marker,
                [
                    "分类权由主控规则执行；弱模型仅交中性事件。"
                    f"规则SHA={self.contract.rules_sha256}"
                ],
            )
            self.assertNotIn(self.contract.predecessor_rules_sha256, active_marker[0])

    def test_stage_classify_then_verify_uses_new_paths_with_zero_calls(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "TEMP") as temp_dir:
            run_dir = Path(temp_dir)
            ctx = zbatch.RunContext(self.batch, self.provider, run_dir)
            for chapter in range(6, 11):
                zbatch.write_json(
                    run_dir / f"01_extract/events/ch{chapter:04d}.json",
                    zbatch.read_json(SOURCE_RUN / f"01_event_extract/parsed/ch{chapter:04d}.json"),
                )
                zbatch.write_json(
                    run_dir / f"01_extract/evidence_catalogs/ch{chapter:04d}.json",
                    zbatch.read_json(
                        SOURCE_RUN / f"01_event_extract/evidence_catalogs/ch{chapter:04d}.json"
                    ),
                )
            zbatch.write_json(
                run_dir / "01_extract/metrics.json",
                {"empty_chapters": [], "empty_chapter_count": 0, "program_audit_pass": True},
            )
            classified = zbatch.stage_classify(ctx, self.chapters)
            verified = zbatch.stage_verify(ctx, self.chapters)
            self.assertEqual(ctx.calls_made, 0)
            self.assertTrue(classified["regression_gate_called"])
            self.assertEqual(classified["candidate_total"], 43)
            self.assertEqual(verified["valid_total"], 43)
            self.assertEqual(verified["invalid_total"], 0)

    def test_verbatim_candidate_builds_messages_but_cannot_auto_run(self):
        text = "这段文字必须逐字保持。"
        source = {
            "schema_version": "z-verbatim-restatement-input-v1",
            "items": [
                {
                    "item_id": "ITEM-0001",
                    "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "source_text": text,
                }
            ],
        }
        built = zbatch.prepare_verbatim_restatement_candidate(self.batch, source)
        self.assertEqual(built["temperature"], 0.1)
        self.assertEqual(built["n"], 1)
        self.assertEqual(built["contract_status"], "candidate_unverified")
        self.assertFalse(built["auto_callable"])
        self.assertNotIn("verbatim_restatement", self.batch["stages"])

    def test_runner_dispatches_all_approved_module_families(self):
        source = (ROOT / "tools/zbatch.py").read_text(encoding="utf-8")
        expected = (
            "modular_evidence_catalog.",
            "modular_anchor_kit.",
            "modular_candidate_envelope.",
            "modular_prompt_render_pin.",
            "modular_downstream_validate.",
            "modular_api_transport.",
            "modular_neutral_extract.",
            "modular_classify_rules.",
            "modular_verbatim_restatement.",
        )
        for marker in expected:
            self.assertIn(marker, source, marker)


if __name__ == "__main__":
    unittest.main()
