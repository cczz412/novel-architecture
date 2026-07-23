from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zbatch_default_registry",
    ROOT / "tools/zbatch_default_registry.py",
)
assert SPEC and SPEC.loader
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)


class DefaultRegistryTests(unittest.TestCase):
    def valid_chain(self, root: Path) -> tuple[dict, dict[str, str]]:
        pins: dict[str, str] = {}

        def reference(value: str) -> dict[str, str]:
            path = root / value
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
            digest = registry.sha256_file(path)
            pins[value] = digest
            return {"path": value, "sha256": digest}

        chain = {
            name: reference(value)
            for name, value in registry.EXPECTED_CHAIN_PATHS.items()
        }
        chain["program_inventory"] = [reference(value) for value in registry.EXPECTED_PROGRAM_PATHS]
        chain["transport"] = {
            "model": "deepseek-v4-flash",
            "profile": "d_mod_cutover_v1",
            "neutral_extract": {
                "temperature": 0.2,
                "max_tokens": 16000,
                "n": 1,
                "reasoning_effort": "medium",
            },
        }
        return chain, pins

    def test_root_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(registry.DefaultRegistryError):
                registry.root_path(root, "../escape.json")

    def test_validate_product_requires_target_double_anchor(self):
        records = [{"id": f"A-{index:04d}"} for index in range(121)]
        records.append({"id": "D-C0013-02", "anchors": [{"anchor_id": "E0129"}]})
        with self.assertRaises(registry.DefaultRegistryError):
            registry.validate_product({"records": records})
        records[-1]["anchors"].append({"anchor_id": "E0130"})
        registry.validate_product({"records": records})

    def test_validate_chain_rejects_transport_drift(self):
        chain = {
            "runner": {},
            "provider": {},
            "stage_sampling_contract": {},
            "neutral_extract_module": {},
            "neutral_extract_prompt": {},
            "classify_rules_module": {},
            "classify_contract": {},
            "classification_prompt": {},
            "classification_decisions": {},
            "program_inventory": [{"path": f"p{n}", "sha256": "x"} for n in range(8)],
            "transport": {
                "model": "deepseek-v4-flash",
                "profile": "d_mod_cutover_v1",
                "neutral_extract": {
                    "temperature": 0.3,
                    "max_tokens": 16000,
                    "n": 1,
                    "reasoning_effort": "medium",
                },
            },
        }
        with self.assertRaises(registry.DefaultRegistryError):
            registry.validate_chain({"chain": chain})

    def test_validate_chain_rejects_wrong_runner_even_if_pinned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, pins = self.valid_chain(root)
            wrong = root / "wrong.py"
            wrong.write_text("wrong", encoding="utf-8")
            pins["wrong.py"] = registry.sha256_file(wrong)
            chain["runner"] = {"path": "wrong.py", "sha256": pins["wrong.py"]}
            with self.assertRaises(registry.DefaultRegistryError):
                registry.validate_chain({"chain": chain}, pins)

    def test_validate_ref_rejects_declared_sha_not_bound_to_pin(self):
        with self.assertRaises(registry.DefaultRegistryError):
            registry.validate_ref(
                {"path": registry.EXPECTED_PRODUCT_PATH, "sha256": "declared"},
                registry.EXPECTED_PRODUCT_PATH,
                {registry.EXPECTED_PRODUCT_PATH: "actual"},
            )

    def test_package_entries_reject_unpinned_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in ("a.txt", "extra.txt"):
                (root / value).write_text(value, encoding="utf-8")
            plan = {
                "report_entries": ["a.txt"],
                "audit_entries": ["a.txt", "extra.txt"],
            }
            pins = {"a.txt": registry.sha256_file(root / "a.txt")}
            with self.assertRaises(registry.DefaultRegistryError):
                registry.validate_package_entries(root, plan, pins)

    def test_package_entries_reject_audit_missing_pinned_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in ("a.txt", "missing-from-audit.txt"):
                (root / value).write_text(value, encoding="utf-8")
            pins = {
                value: registry.sha256_file(root / value)
                for value in ("a.txt", "missing-from-audit.txt")
            }
            plan = {"report_entries": ["a.txt"], "audit_entries": ["a.txt"]}
            with self.assertRaises(registry.DefaultRegistryError):
                registry.validate_package_entries(root, plan, pins)

    def test_team_attestation_rejects_nonzero_p1(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            review = root / registry.EXPECTED_LUNA_REVIEW_PATH
            review.parent.mkdir(parents=True)
            review.write_text(
                "- 结论：PASS。\n- P0：0；P1：0；P2：0。\n复核者：Luna-High-6（`/root/step1_coverage_review`）\n",
                encoding="utf-8",
            )
            team = {
                "run_id": registry.EXPECTED_RUN_ID,
                "reviewer": "Luna-High-6",
                "review_task": "/root/step1_coverage_review",
                "decision": "pass",
                "p0": 0,
                "p1": 1,
                "p2": 0,
                "mechanical_review_sha256": "mechanical",
                "review_file": registry.EXPECTED_LUNA_REVIEW_PATH,
                "review_file_sha256": registry.sha256_file(review),
            }
            with self.assertRaises(registry.DefaultRegistryError):
                registry.validate_team_attestation(root, team, mechanical_sha256="mechanical")

    def test_zip_entries_writes_and_tests_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("ok", encoding="utf-8")
            output = root / "package.zip"
            result = registry.zip_entries(
                output,
                root,
                ["source.txt"],
                {"extra.json": json.dumps({"ok": True}).encode("utf-8")},
            )
            self.assertEqual(result["zip_test"], "ok")
            self.assertEqual(result["entries"], 2)

    def test_zip_entries_normalizes_archive_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("ok", encoding="utf-8")
            output = root / "package.zip"
            registry.zip_entries(output, root, ["folder/../source.txt"], {})
            with zipfile.ZipFile(output, "r") as archive:
                self.assertEqual(archive.namelist(), ["files/source.txt"])

    def test_commit_failure_rolls_back_published_outbox(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            registry.write_json_atomic(
                stage / "manifest.json",
                {"run_id": registry.EXPECTED_RUN_ID},
            )
            outbox = root / f"outbox/{registry.EXPECTED_RUN_ID}"
            default = root / registry.DEFAULT_REGISTRY
            commit = root / registry.COMMIT_MARKER
            original = registry.write_bytes_atomic

            def fail_default(path: Path, data: bytes) -> None:
                if path == default:
                    raise OSError("injected default write failure")
                original(path, data)

            with mock.patch.object(registry, "write_bytes_atomic", side_effect=fail_default):
                with self.assertRaises(OSError):
                    registry.commit_promotion(
                        root,
                        staged_outbox=stage,
                        outbox_path=outbox,
                        default_path=default,
                        default_bytes=b"{}\n",
                        commit_path=commit,
                        commit_document={},
                        post_commit_verify=lambda: {"status": "pass"},
                    )
            self.assertFalse(outbox.exists())
            self.assertFalse(default.exists())
            self.assertFalse(commit.exists())

    def test_commit_marker_failure_rolls_back_both_sides(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            registry.write_json_atomic(stage / "manifest.json", {"run_id": registry.EXPECTED_RUN_ID})
            outbox = root / f"outbox/{registry.EXPECTED_RUN_ID}"
            default = root / registry.DEFAULT_REGISTRY
            commit = root / registry.COMMIT_MARKER
            default_bytes = registry.json_bytes(
                {"default_id": registry.EXPECTED_DEFAULT_ID, "promotion_run_id": registry.EXPECTED_RUN_ID}
            )
            original = registry.write_json_atomic

            def fail_marker(path: Path, data) -> None:
                if path == commit:
                    raise OSError("injected commit marker failure")
                original(path, data)

            with mock.patch.object(registry, "write_json_atomic", side_effect=fail_marker):
                with self.assertRaises(OSError):
                    registry.commit_promotion(
                        root,
                        staged_outbox=stage,
                        outbox_path=outbox,
                        default_path=default,
                        default_bytes=default_bytes,
                        commit_path=commit,
                        commit_document={},
                        post_commit_verify=lambda: {"status": "pass"},
                    )
            self.assertFalse(outbox.exists())
            self.assertFalse(default.exists())
            self.assertFalse(commit.exists())

    def test_post_commit_verify_failure_rolls_back_everything(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            registry.write_json_atomic(stage / "manifest.json", {"run_id": registry.EXPECTED_RUN_ID})
            outbox = root / f"outbox/{registry.EXPECTED_RUN_ID}"
            default = root / registry.DEFAULT_REGISTRY
            commit = root / registry.COMMIT_MARKER
            default_bytes = registry.json_bytes(
                {"default_id": registry.EXPECTED_DEFAULT_ID, "promotion_run_id": registry.EXPECTED_RUN_ID}
            )

            def fail_verify():
                raise registry.DefaultRegistryError("injected post-commit verify failure")

            with self.assertRaises(registry.DefaultRegistryError):
                registry.commit_promotion(
                    root,
                    staged_outbox=stage,
                    outbox_path=outbox,
                    default_path=default,
                    default_bytes=default_bytes,
                    commit_path=commit,
                    commit_document={},
                    post_commit_verify=fail_verify,
                )
            self.assertFalse(outbox.exists())
            self.assertFalse(default.exists())
            self.assertFalse(commit.exists())

    def test_recover_uncommitted_removes_only_matching_residue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outbox = root / f"outbox/{registry.EXPECTED_RUN_ID}"
            default = root / registry.DEFAULT_REGISTRY
            commit = root / registry.COMMIT_MARKER
            registry.write_json_atomic(
                outbox / "manifest.json",
                {"run_id": registry.EXPECTED_RUN_ID},
            )
            registry.write_json_atomic(
                default,
                {"default_id": registry.EXPECTED_DEFAULT_ID, "promotion_run_id": registry.EXPECTED_RUN_ID},
            )
            registry.recover_uncommitted(root, default, outbox, commit)
            self.assertFalse(outbox.exists())
            self.assertFalse(default.exists())

    def test_verify_registry_refs_detects_live_chain_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _ = self.valid_chain(root)
            historical = root / "work/zbatch_prompts/extract_v1.3.md"
            historical.parent.mkdir(parents=True, exist_ok=True)
            historical.write_text("historical", encoding="utf-8")
            audit = root / registry.EXPECTED_Z00Y3_AUDIT_PATH
            audit.parent.mkdir(parents=True, exist_ok=True)
            audit.write_text("audit", encoding="utf-8")
            value = {
                "chain": chain,
                "historical_reference": {
                    "status": "historical_reference_not_default",
                    "path": "work/zbatch_prompts/extract_v1.3.md",
                    "sha256": registry.sha256_file(historical),
                },
                "source_adjudication": {
                    "z00y3_audit": {
                        "path": registry.EXPECTED_Z00Y3_AUDIT_PATH,
                        "sha256": registry.sha256_file(audit),
                    }
                },
            }
            registry.verify_registry_refs(root, value)
            (root / registry.EXPECTED_CHAIN_PATHS["runner"]).write_text("drift", encoding="utf-8")
            with self.assertRaises(registry.DefaultRegistryError):
                registry.verify_registry_refs(root, value)

    def test_default_manifest_preserves_failure_boundaries(self):
        plan = {
            "default_id": registry.EXPECTED_DEFAULT_ID,
            "authority": "authority",
            "source_adjudication": {},
            "run_id": registry.EXPECTED_RUN_ID,
            "chain": {},
            "product": {"path": "product.json", "sha256": "x"},
            "historical_reference": {},
            "outbox_path": f"outbox/{registry.EXPECTED_RUN_ID}",
        }
        value = registry.default_manifest(plan, promoted_at="now")
        self.assertFalse(value["red_lines"]["z01d_z01f_promoted"])
        self.assertFalse(value["red_lines"]["classification_rules_changed"])


if __name__ == "__main__":
    unittest.main()
