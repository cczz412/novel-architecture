from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

LEGACY_NEUTRAL_EXTRACT = ROOT / (
    "experiments/model_benchmarks/"
    "MB_X01_C0003_longcat_LongCat-2.0_thinking_t02_r01_20260723/"
    "inputs/runtime_dependencies/tools/zbatch_modules/neutral_extract.py"
)
LEGACY_NEUTRAL_SHA256 = "f567ebef481dc33775ba7974c09744d185d6b8fa2b7b5e947e0be89f145dd7a7"

import z57_activate_semantic_identity_contract as activate_z57  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Z57DefaultContractHotfixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source_overrides = {
            activate_z57.DEFAULT_PATH: ROOT
            / "config/defaults/history/zbatch_v1.2_full_chain_61bc6ca45fe450d382995b29dd998c9119ade2db6049d29963c83eee30c5f9da.json",
            activate_z57.COMMIT_PATH: ROOT
            / "config/defaults/history/zbatch_v1.2_full_chain.COMMITTED_9259d3958e97aed982a798545ae889e3c608a3c8ef12dad87ea9f18f9cdddc48.json",
        }
        for relative in (
            activate_z57.DEFAULT_PATH,
            activate_z57.COMMIT_PATH,
            activate_z57.OLD_CONTRACT_PATH,
            activate_z57.NEW_CONTRACT_PATH,
            activate_z57.CLASSIFY_MODULE_PATH,
            activate_z57.RUNNER_PATH,
            activate_z57.FORMAL_DECISIONS_PATH,
            activate_z57.OLD_RUNNER_PIN_PATH,
            activate_z57.OLD_MODULE_PIN_PATH,
            Path("work/zbatch_prompts/candidates/main_control_classification_rules_v1.2.md"),
            Path("work/zbatch_decisions/Z00n_X01_ch6_10_main_control_decisions_v2_corrected.json"),
            Path("config/providers/sensenova_modular_v1.json"),
            Path("config/contracts/sensenova_stage_sampling_v1.json"),
            Path("tools/zbatch_modules/neutral_extract.py"),
            Path("tools/zbatch_modules/evidence_catalog.py"),
            Path("tools/zbatch_modules/anchor_kit.py"),
            Path("tools/zbatch_modules/candidate_envelope.py"),
            Path("tools/zbatch_modules/prompt_render_pin.py"),
            Path("tools/zbatch_modules/downstream_validate.py"),
            Path("tools/zbatch_modules/api_transport.py"),
            Path("tools/zbatch_modules/stage_sampling.py"),
            Path("work/zbatch_prompts/candidates/extract_event_only_no_self_audit_v1.1.md"),
            Path("work/zbatch_decisions/Z36_X01_ch1_20_main_control_decisions_v1.2.json"),
            Path("work/zbatch_prompts/extract_v1.3.md"),
            Path("work/zbatch_audits/Z00y3_new_four_semantic_audit_v1.json"),
            Path("runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json"),
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            source = source_overrides.get(relative, ROOT / relative)
            if relative == Path("tools/zbatch_modules/neutral_extract.py"):
                self.assertEqual(sha256(LEGACY_NEUTRAL_EXTRACT), LEGACY_NEUTRAL_SHA256)
                source = LEGACY_NEUTRAL_EXTRACT
            shutil.copy2(source, target)
        for relative in (
            activate_z57.SOURCE_EXTRACT_PATH,
            Path("runs/Z00n_X01_第6至10章程序清点单变量_5章_v1.1_20260717"),
            activate_z57.OUTBOX_MANIFEST_PATH.parent,
        ):
            shutil.copytree(ROOT / relative, self.root / relative)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_activation_is_reversible_idempotent_and_does_not_touch_outbox(self) -> None:
        old_registry = (self.root / activate_z57.DEFAULT_PATH).read_bytes()
        old_commit = (self.root / activate_z57.COMMIT_PATH).read_bytes()
        old_outbox = (self.root / activate_z57.OUTBOX_MANIFEST_PATH).read_bytes()
        result = activate_z57.activate(self.root, full_verify=False)
        self.assertEqual(result["status"], "activated")
        self.assertFalse(result["outbox_rewritten"])
        self.assertEqual((self.root / activate_z57.OUTBOX_MANIFEST_PATH).read_bytes(), old_outbox)

        registry_path = self.root / activate_z57.DEFAULT_PATH
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        revision = registry["compatibility_revision"]
        self.assertEqual(revision["predecessor_default_registry_sha256"], activate_z57.OLD_DEFAULT_SHA256)
        self.assertFalse(revision["semantic_rules_changed"])
        self.assertEqual(revision["sequential_event_id_scope"], "run_local_only")
        self.assertEqual(
            registry["chain"]["classify_contract"]["path"],
            activate_z57.NEW_CONTRACT_PATH.as_posix(),
        )
        self.assertEqual(
            registry["chain"]["classify_rules_module"]["sha256"],
            sha256(self.root / activate_z57.CLASSIFY_MODULE_PATH),
        )

        default_archive = self.root / revision["rollback"]["default_registry_archive"]
        commit_archive = self.root / revision["rollback"]["commit_marker_archive"]
        self.assertEqual(default_archive.read_bytes(), old_registry)
        self.assertEqual(commit_archive.read_bytes(), old_commit)
        commit = json.loads((self.root / activate_z57.COMMIT_PATH).read_text(encoding="utf-8"))
        self.assertEqual(commit["default_registry"]["sha256"], sha256(registry_path))

        second = activate_z57.activate(self.root, full_verify=False)
        self.assertEqual(second["status"], "already_active")
        self.assertEqual(second["default_registry_sha256"], result["default_registry_sha256"])

    def test_unknown_old_contract_drift_is_refused_without_default_mutation(self) -> None:
        old_registry = (self.root / activate_z57.DEFAULT_PATH).read_bytes()
        (self.root / activate_z57.OLD_CONTRACT_PATH).write_text("drift", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "旧v1.2分类合同发生漂移"):
            activate_z57.activate(self.root, full_verify=False)
        self.assertEqual((self.root / activate_z57.DEFAULT_PATH).read_bytes(), old_registry)

    def test_prepared_half_write_is_recovered_before_retry(self) -> None:
        original_write_atomic = activate_z57.write_atomic
        default_path = (self.root / activate_z57.DEFAULT_PATH).resolve()
        commit_path = (self.root / activate_z57.COMMIT_PATH).resolve()
        old_commit_sha = sha256(commit_path)
        interrupted = False

        def interrupt_after_default(path: Path, data: bytes) -> None:
            nonlocal interrupted
            original_write_atomic(path, data)
            if path == default_path and not interrupted and hashlib.sha256(data).hexdigest() != activate_z57.OLD_DEFAULT_SHA256:
                interrupted = True
                raise KeyboardInterrupt("simulate process interruption")

        activate_z57.write_atomic = interrupt_after_default
        try:
            with self.assertRaises(KeyboardInterrupt):
                activate_z57.activate(self.root, full_verify=False)
        finally:
            activate_z57.write_atomic = original_write_atomic
        self.assertNotEqual(sha256(default_path), activate_z57.OLD_DEFAULT_SHA256)
        self.assertEqual(sha256(commit_path), old_commit_sha)

        result = activate_z57.activate(self.root, full_verify=False)
        self.assertEqual(result["status"], "activated")
        commit = json.loads(commit_path.read_text(encoding="utf-8"))
        self.assertEqual(commit["default_registry"]["sha256"], sha256(default_path))
        transaction = json.loads((self.root / activate_z57.TRANSACTION_PATH).read_text(encoding="utf-8"))
        self.assertEqual(transaction["status"], "committed")

    def test_forged_already_active_revision_is_rejected_even_without_full_verify(self) -> None:
        activate_z57.activate(self.root, full_verify=False)
        registry_path = self.root / activate_z57.DEFAULT_PATH
        commit_path = self.root / activate_z57.COMMIT_PATH
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["compatibility_revision"]["authority"] = "伪造授权"
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        commit = json.loads(commit_path.read_text(encoding="utf-8"))
        commit["default_registry"]["sha256"] = sha256(registry_path)
        commit_path.write_text(json.dumps(commit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "固定身份字段不可信"):
            activate_z57.activate(self.root, full_verify=False)

    def test_full_default_registry_verification_passes_after_activation(self) -> None:
        result = activate_z57.activate(self.root, full_verify=True)
        self.assertEqual(result["status"], "activated")
        verified = activate_z57.zbatch_default_registry.verify(
            self.root,
            self.root / activate_z57.DEFAULT_PATH,
        )
        self.assertEqual(verified["status"], "pass")
        self.assertEqual(verified["model_calls"], 0)

    def test_full_rollback_drill_restores_predecessor_and_verifies(self) -> None:
        activated = activate_z57.activate(self.root, full_verify=True)
        self.assertEqual(activated["status"], "activated")
        registry = json.loads(
            (self.root / activate_z57.DEFAULT_PATH).read_text(encoding="utf-8")
        )
        rollback = registry["compatibility_revision"]["rollback"]
        shutil.copy2(
            self.root / rollback["default_registry_archive"],
            self.root / activate_z57.DEFAULT_PATH,
        )
        shutil.copy2(
            self.root / rollback["commit_marker_archive"],
            self.root / activate_z57.COMMIT_PATH,
        )
        shutil.copy2(
            self.root / rollback["old_runner_pinned_path"],
            self.root / activate_z57.RUNNER_PATH,
        )
        shutil.copy2(
            self.root / rollback["old_classify_module_pinned_path"],
            self.root / activate_z57.CLASSIFY_MODULE_PATH,
        )
        verified = activate_z57.zbatch_default_registry.verify(
            self.root,
            self.root / activate_z57.DEFAULT_PATH,
        )
        self.assertEqual(verified["status"], "pass")
        self.assertEqual(
            verified["default_registry_sha256"], activate_z57.OLD_DEFAULT_SHA256
        )
        self.assertEqual(verified["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
