from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


PROGRAM = (
    Path(__file__).resolve().parents[1] / "program/repo_bridge.py"
)


def load_bridge() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repo_bridge_candidate", PROGRAM)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load_bridge()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def make_fixture(root: Path) -> tuple[Path, Path]:
    for directory in (
        "governance",
        "finetuning/experiments/FT_R01",
        "bridge",
        "TEMP",
        "runs",
        "reports",
        "outbox",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(
        "/TEMP/\n/runs/\n/reports/\n/outbox/\n",
        encoding="utf-8",
    )
    write_json(
        root / "governance/CURRENT_STATE.json",
        {
            "schema_version": "governance-current-state-v2",
            "snapshot_at": "2026-08-07T00:00:00+08:00",
            "current_execution": {
                "task": {
                    "task_id": "T-01",
                    "label": "fixture",
                    "status": "running",
                    "status_label": "fixture running",
                },
                "run": {
                    "run_id": "RUN-01",
                    "run_directory": "runs/RUN-01",
                    "status_label": "running",
                },
                "controls": {"next_action": "review"},
                "blockers": [],
            },
        },
    )
    directory_rows = []
    for path in ("governance", "finetuning", "TEMP", "runs", "reports", "outbox"):
        directory_rows.append(
            {
                "path": path,
                "identity": path.lower(),
                "category": "temporary" if path == "TEMP" else "governance",
                "container_authority": "derived" if path == "TEMP" else "current",
                "load_policy": "task_scoped",
                "lifecycle": "mutable",
                "git_policy": "ignored" if path in {"TEMP", "runs", "reports", "outbox"} else "tracked",
                "new_content_rule": "fixture",
            }
        )
    write_json(
        root / "governance/directory_registry.json",
        {"schema_version": "directory-registry-v1", "directories": directory_rows},
    )
    manifest_path = root / "finetuning/experiments/FT_R01/MANIFEST.json"
    write_json(
        manifest_path,
        {
            "schema_version": "fixture-manifest-v1",
            "derived_facts": {"rows": 1},
            "boundaries": {"training_authorized": False},
        },
    )
    manifest_sha = bridge.sha256_file(manifest_path)
    write_json(
        root / "finetuning/CURRENT.json",
        {
            "schema_version": "finetuning-current-pointer-v2",
            "current_experiment_id": "FT_R01",
            "manifest_revision": "r01",
            "manifest_sha256": manifest_sha,
            "scope": "navigation_only",
            "may_authorize_promotion": False,
            "may_authorize_training": False,
        },
    )
    (root / "finetuning/experiments/FT_R01/DECISION.md").write_text(
        "# Fixture decision\n",
        encoding="utf-8",
    )
    (root / "decisions.md").write_text("# Decisions\n", encoding="utf-8")
    write_json(
        root / "finetuning/R02_ACCEPTANCE_RECEIPT.json",
        {"schema_version": "fixture-receipt-v1", "status": "PASS"},
    )
    (root / "bridge/program.py").write_text("VERSION = 1\n", encoding="utf-8")
    (root / "bridge/schema.json").write_text("{}\n", encoding="utf-8")
    (root / "bridge/tests.py").write_text("assert True\n", encoding="utf-8")
    (root / "notes.txt").write_text("stable\n", encoding="utf-8")
    config_path = root / "bridge/SOURCE_CONFIG.json"
    write_json(
        config_path,
        {
            "schema_version": "repo-bridge-source-config-v1",
            "repo_id": "fixture-repo",
            "semantic_sources": [
                {
                    "source_id": "repository_current_state",
                    "adapter": "governance_current_state",
                    "path": "governance/CURRENT_STATE.json",
                    "authority_scope": "repository_current_execution_mirror",
                },
                {
                    "source_id": "directory_registry",
                    "adapter": "directory_registry",
                    "path": "governance/directory_registry.json",
                    "authority_scope": "container_identity_only",
                },
                {
                    "source_id": "finetuning_current",
                    "adapter": "finetuning_current",
                    "path": "finetuning/CURRENT.json",
                    "authority_scope": "finetuning_current_navigation",
                },
                {
                    "source_id": "legacy_decisions",
                    "adapter": "evidence_only",
                    "path": "decisions.md",
                    "authority_scope": "legacy_local_decision_mirror",
                },
                {
                    "source_id": "finetuning_r02_acceptance",
                    "adapter": "json_evidence",
                    "path": "finetuning/R02_ACCEPTANCE_RECEIPT.json",
                    "authority_scope": "finetuning_r02_acceptance_receipt",
                },
            ],
            "critical_evidence": [
                {
                    "evidence_id": "TEST-GENERATOR",
                    "path": "bridge/program.py",
                    "authority_scope": "candidate_generator",
                },
                {
                    "evidence_id": "TEST-REVIEW-SCHEMA",
                    "path": "bridge/schema.json",
                    "authority_scope": "review_schema",
                },
                {
                    "evidence_id": "TEST-TESTS",
                    "path": "bridge/tests.py",
                    "authority_scope": "mechanical_tests",
                },
            ],
            "inventory": {
                "exclude_roots": [".git"],
                "exclude_subpaths": ["TEMP/repo_bridge"],
                "high_frequency_roots": ["TEMP", "runs", "reports", "outbox"],
            },
        },
    )
    handoff_path = root / "TEMP/HANDOFF.json"
    write_json(
        handoff_path,
        {
            "schema_version": "repo-bridge-handoff-input-v1",
            "handoff_id": "fixture-handoff-r01",
            "purpose": "Review the Repo Bridge prototype.",
            "requested_by": "Codex",
            "review_scope": {
                "domains": ["finetuning"],
                "paths": ["finetuning/"],
                "evidence_ids": ["FT-CURRENT-MANIFEST"],
            },
            "questions": ["Can this package support a safe return review?"],
            "execution_authorization": False,
        },
    )
    git(root, "init", "-q")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture")
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture")
    return config_path, handoff_path


def build_fixture_package(root: Path, config_path: Path, handoff_path: Path) -> Path:
    handoff, handoff_data = bridge.load_handoff(root, handoff_path)
    components = bridge.build_snapshot_components(
        root,
        config_path,
        include_inventory=True,
    )
    payloads, package_id = bridge.build_payloads(
        root,
        components,
        handoff,
        handoff_data,
    )
    receipt = bridge.write_full_package(
        root,
        payloads,
        components["snapshot"],
        package_id,
    )
    return root / receipt["zip_relative_path"]


def make_review(package: dict[str, object]) -> dict[str, object]:
    snapshot = package["snapshot"]
    manifest = package["manifest"]
    handoff_binding = package["handoff_binding"]
    assert isinstance(snapshot, dict)
    assert isinstance(manifest, dict)
    assert isinstance(handoff_binding, dict)
    return {
        "schema_version": "repo-bridge-review-v1",
        "review_id": "chatgpt-review-fixture-r01",
        "reply_to_snapshot_id": snapshot["snapshot_id"],
        "reply_to_snapshot_digest_sha256": snapshot["snapshot_digest_sha256"],
        "reply_to_package_id": manifest["package_id"],
        "reply_to_handoff_id": handoff_binding["handoff_id"],
        "review_scope": {
            "domains": ["finetuning"],
            "paths": ["finetuning/"],
            "decision_ids": [],
            "evidence_ids": ["FT-CURRENT-MANIFEST"],
        },
        "summary": "Fixture review.",
        "findings": [],
        "open_questions": [],
        "execution_authorization": False,
    }


def test_inventory_churn_does_not_change_semantic_snapshot() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, _handoff_path = make_fixture(root)
        before = bridge.build_snapshot_components(root, config_path, include_inventory=True)
        (root / "runs/new.log").write_bytes(b"runtime-only")
        after = bridge.build_snapshot_components(root, config_path, include_inventory=True)
        assert before["snapshot"]["snapshot_id"] == after["snapshot"]["snapshot_id"]
        assert (
            before["snapshot"]["inventory_fingerprint_sha256"]
            != after["snapshot"]["inventory_fingerprint_sha256"]
        )
        assert before["snapshot"]["observation_id"] != after["snapshot"]["observation_id"]


def test_full_package_verifies_and_embeds_return_contract() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        receipt = bridge.verify_package(root, zip_path)
        assert receipt["status"] == "PASS"
        members = bridge.read_package(zip_path)["members"]
        assert "08_RETURN_INSTRUCTIONS.md" in members
        assert "_bridge/CHATGPT_RETURN_TEMPLATE.json" in members
        assert "_bridge/schemas/REVIEW_RETURN.schema.json" in members
        assert bridge.HANDOFF_BINDING_MEMBER in members
        manifest = json.loads(members[bridge.PACKAGE_MANIFEST])
        count_contract = manifest["member_count_contract"]
        assert count_contract["zip_member_count"] == len(members)
        assert count_contract["manifested_member_count"] == len(members) - 2
        assert count_contract["secret_scan_scanned_member_count"] == len(members) - 3
        assert count_contract["manifest_excluded_members"] == [
            bridge.PACKAGE_MANIFEST,
            bridge.PACKAGE_SHA256SUMS,
        ]
        assert count_contract["secret_scan_excluded_members"] == [
            bridge.PACKAGE_MANIFEST,
            bridge.SECRET_SCAN_MEMBER,
            bridge.PACKAGE_SHA256SUMS,
        ]
        template = json.loads(members["_bridge/CHATGPT_RETURN_TEMPLATE.json"])
        handoff_binding = json.loads(members[bridge.HANDOFF_BINDING_MEMBER])
        assert template["reply_to_package_id"] == manifest["package_id"]
        assert template["reply_to_handoff_id"] == handoff_binding["handoff_id"]
        for name in bridge.DERIVED_JSON_VIEWS:
            view = json.loads(members[name])
            assert view["view_kind"] == "derived_snapshot_view"
            assert view["authoritative"] is False


def test_build_freshness_receipt_stays_outside_stable_zip() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        first_zip = build_fixture_package(root, config_path, handoff_path)
        first_sha = bridge.sha256_file(first_zip)
        second_zip = build_fixture_package(root, config_path, handoff_path)
        assert second_zip == first_zip
        assert bridge.sha256_file(second_zip) == first_sha

        receipt_paths = sorted(first_zip.parent.glob("BUILD_RECEIPTS/*.json"))
        assert len(receipt_paths) == 2
        for receipt_path in receipt_paths:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            assert receipt["generated_at"]
            assert receipt["source_declared_at"] == "2026-08-07T00:00:00+08:00"
            assert receipt["freshness"] in {"fresh", "stale"}
            assert receipt["freshness_affects_snapshot_id"] is False
        members = bridge.read_package(first_zip)["members"]
        assert all("BUILD_RECEIPT" not in name for name in members)


def test_status_classifier_covers_three_relations() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        package = bridge.read_package(zip_path)
        review = make_review(package)

        exact = bridge.compare_package_to_current(
            package,
            bridge.build_snapshot_components(root, config_path, include_inventory=True),
            review,
        )
        assert exact["relation"] == "exact_match"
        assert exact["relevance_granularity"] == "file_level"

        (root / "notes.txt").write_text("unrelated change\n", encoding="utf-8")
        unrelated = bridge.compare_package_to_current(
            package,
            bridge.build_snapshot_components(root, config_path, include_inventory=True),
            review,
        )
        assert unrelated["relation"] == "changed_unrelated"
        assert unrelated["relevance_granularity"] == "file_level"

        (root / "notes.txt").write_text("stable\n", encoding="utf-8")
        manifest = root / "finetuning/experiments/FT_R01/MANIFEST.json"
        write_json(
            manifest,
            {
                "schema_version": "fixture-manifest-v1",
                "derived_facts": {"rows": 2},
                "boundaries": {"training_authorized": False},
            },
        )
        pointer = json.loads((root / "finetuning/CURRENT.json").read_text(encoding="utf-8"))
        pointer["manifest_sha256"] = bridge.sha256_file(manifest)
        write_json(root / "finetuning/CURRENT.json", pointer)
        relevant = bridge.compare_package_to_current(
            package,
            bridge.build_snapshot_components(root, config_path, include_inventory=True),
            review,
        )
        assert relevant["relation"] == "changed_relevant"
        assert relevant["relevance_granularity"] == "file_level"
        assert "domain:finetuning" in relevant["relevant_changes"]


def test_import_review_only_writes_temp_inbox() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        package = bridge.read_package(zip_path)
        review_path = root / "TEMP/CHATGPT_RETURN.json"
        write_json(review_path, make_review(package))
        receipt = bridge.import_review(root, config_path, review_path, zip_path)
        assert receipt["relation"] == "exact_match"
        assert receipt["formal_decision_event_created"] is False
        assert receipt["execution_authorized"] is False
        assert receipt["review_binding"] == "snapshot_package_handoff"
        inbox = root / receipt["proposal_inbox_relative_path"]
        assert (inbox / "CHATGPT_RETURN.json").is_file()
        assert (inbox / "IMPORT_RECEIPT.json").is_file()
        assert not (root / "governance/decision_events.jsonl").exists()


@pytest.mark.parametrize(
    ("expected_relation", "expected_status"),
    [
        ("changed_unrelated", "RECEIVED_CZ_REVIEW_REQUIRED"),
        ("changed_relevant", "HARD_STOP_REVIEW_STALE"),
    ],
)
def test_import_review_real_change_gates_in_isolated_repo(
    expected_relation: str,
    expected_status: str,
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        package = bridge.read_package(zip_path)
        review = make_review(package)
        review["review_id"] = f"chatgpt-review-{expected_relation}-r01"

        if expected_relation == "changed_unrelated":
            (root / "notes.txt").write_text("unrelated change\n", encoding="utf-8")
        else:
            manifest = root / "finetuning/experiments/FT_R01/MANIFEST.json"
            write_json(
                manifest,
                {
                    "schema_version": "fixture-manifest-v1",
                    "derived_facts": {"rows": 2},
                    "boundaries": {"training_authorized": False},
                },
            )
            pointer_path = root / "finetuning/CURRENT.json"
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            pointer["manifest_sha256"] = bridge.sha256_file(manifest)
            write_json(pointer_path, pointer)

        review_path = root / "TEMP/CHATGPT_RETURN.json"
        write_json(review_path, review)
        receipt = bridge.import_review(root, config_path, review_path, zip_path)
        assert receipt["relation"] == expected_relation
        assert receipt["status"] == expected_status
        assert receipt["status_detail"]["relevance_granularity"] == "file_level"
        assert receipt["formal_decision_event_created"] is False
        assert receipt["execution_authorized"] is False
        assert not (root / "governance/decision_events.jsonl").exists()


def test_review_must_bind_package_and_handoff() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        package = bridge.read_package(zip_path)

        second_handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        second_handoff["handoff_id"] = "fixture-handoff-r02"
        second_handoff["purpose"] = "Review a different question on the same snapshot."
        second_handoff["questions"] = ["Does question B have a safe return contract?"]
        second_handoff_path = root / "TEMP/HANDOFF_B.json"
        write_json(second_handoff_path, second_handoff)
        second_zip_path = build_fixture_package(
            root,
            config_path,
            second_handoff_path,
        )
        second_package = bridge.read_package(second_zip_path)
        assert second_package["snapshot"]["snapshot_id"] == package["snapshot"][
            "snapshot_id"
        ]
        assert second_package["manifest"]["package_id"] != package["manifest"][
            "package_id"
        ]

        wrong_package = make_review(package)
        wrong_package["review_id"] = "chatgpt-review-package-a-return-r01"
        wrong_package_path = root / "TEMP/WRONG_PACKAGE_RETURN.json"
        write_json(wrong_package_path, wrong_package)
        with pytest.raises(bridge.BridgeError) as package_error:
            bridge.import_review(
                root,
                config_path,
                wrong_package_path,
                second_zip_path,
            )
        assert package_error.value.code == "REVIEW_PACKAGE_BINDING_MISMATCH"

        wrong_handoff = make_review(package)
        wrong_handoff["review_id"] = "chatgpt-review-wrong-handoff-r01"
        wrong_handoff["reply_to_handoff_id"] = "different-handoff-r01"
        wrong_handoff_path = root / "TEMP/WRONG_HANDOFF_RETURN.json"
        write_json(wrong_handoff_path, wrong_handoff)
        with pytest.raises(bridge.BridgeError) as handoff_error:
            bridge.import_review(root, config_path, wrong_handoff_path, zip_path)
        assert handoff_error.value.code == "REVIEW_HANDOFF_BINDING_MISMATCH"


def test_review_contract_rejects_approval_and_execution() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        package = bridge.read_package(zip_path)
        review = make_review(package)
        review["findings"] = [
            {
                "finding_id": "F-01",
                "kind": "approved",
                "severity": "high",
                "claim": "not allowed",
                "evidence_ids": [],
                "suggested_action": "execute",
                "requires_cz_decision": False,
            }
        ]
        review["execution_authorization"] = True
        review_path = root / "TEMP/INVALID_RETURN.json"
        write_json(review_path, review)
        with pytest.raises(bridge.BridgeError) as error:
            bridge.load_review(review_path)
        assert error.value.code == "REVIEW_SCHEMA_INVALID"


def test_verify_rejects_tampered_payload() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config_path, handoff_path = make_fixture(root)
        zip_path = build_fixture_package(root, config_path, handoff_path)
        tampered = root / "TEMP/tampered.zip"
        with zipfile.ZipFile(zip_path) as source, zipfile.ZipFile(tampered, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "00_HANDOFF.md":
                    data += b"tampered"
                target.writestr(info.filename, data)
        with pytest.raises(bridge.BridgeError) as error:
            bridge.verify_package(root, tampered)
        assert error.value.code in {
            "PACKAGE_MANIFEST_HASH_MISMATCH",
            "PACKAGE_SHA256SUMS_MISMATCH",
        }
