#!/usr/bin/env python3
"""第57道：可回退地把默认分类合同切到稳定语义身份载体。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import zbatch_default_registry
from zbatch_modules import classify_rules


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = Path("config/defaults/zbatch_v1.2_full_chain.json")
COMMIT_PATH = Path("config/defaults/zbatch_v1.2_full_chain.COMMITTED.json")
OLD_CONTRACT_PATH = Path("config/contracts/classify_rules_v1.2.json")
NEW_CONTRACT_PATH = Path("config/contracts/classify_rules_v1.2_semantic_identity_v1.json")
CLASSIFY_MODULE_PATH = Path("tools/zbatch_modules/classify_rules.py")
RUNNER_PATH = Path("tools/zbatch.py")
FORMAL_DECISIONS_PATH = Path("work/zbatch_decisions/Z57_X01_ch1_20_main_control_decisions_v1.2.json")
SOURCE_EXTRACT_PATH = Path("runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719/01_extract")
TRANSACTION_PATH = Path("config/defaults/zbatch_v1.2_full_chain.Z57_TRANSACTION.json")
OUTBOX_MANIFEST_PATH = Path(
    "outbox/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/manifest.json"
)
OLD_DEFAULT_SHA256 = "61bc6ca45fe450d382995b29dd998c9119ade2db6049d29963c83eee30c5f9da"
OLD_COMMIT_SHA256 = "9259d3958e97aed982a798545ae889e3c608a3c8ef12dad87ea9f18f9cdddc48"
OLD_CONTRACT_SHA256 = "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de"
OUTBOX_MANIFEST_SHA256 = "aecfcf93a265fa5f9f61ee7003bf8f7118833a12b8e2a0ffcc4899631cec6aa2"
NEW_CONTRACT_SHA256 = "45f7610b86d5962e0d3d9d4d95886aad9022f1beaece200c2452b9a361f6c108"
CLASSIFY_MODULE_SHA256 = "eed588211111f89f5c6968c490686124bf94e7cd09d65aee3f1bc02dd9011104"
RUNNER_SHA256 = "160c28b3ef0210fd05c392f713534cf1ffdf041fa596ec790545b64955280850"
FORMAL_DECISIONS_SHA256 = "ba856a487e6fcc416c83b05a0b9e6c458ea85f5d8a7e23354f8c2865b8e97650"
OLD_RUNNER_PIN_PATH = Path(
    "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/provenance/runner_zbatch.py"
)
OLD_RUNNER_SHA256 = "4090169dd53a71badd21d42d3c1c1e8809bd54ac46f461ab3e33137e94c3ca11"
OLD_MODULE_PIN_PATH = Path(
    "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/provenance/pinned/tools/zbatch_modules/classify_rules.py"
)
OLD_MODULE_SHA256 = "76b3c1e208abaf0ab47c8dafee4c4e1ccb7d6d4cb3d364fc30afa00c6179eb7b"
REVISION_ID = "Z57-stable-semantic-identity-v1"
AUTHORITY = "第57道；CZ 2026-07-19 19:41拍a"
ACTIVATED_AT = "2026-07-19T19:41:00+08:00"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".z57.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def archive_exact(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f"回退档已存在但内容不符：{path}")
        return
    write_atomic(path, data)


def _load_catalogs(root: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, str]]]:
    documents: list[dict[str, Any]] = []
    catalogs: dict[int, dict[str, str]] = {}
    for chapter in range(1, 21):
        event_path = root / SOURCE_EXTRACT_PATH / f"events/ch{chapter:04d}.json"
        catalog_path = root / SOURCE_EXTRACT_PATH / f"evidence_catalogs/ch{chapter:04d}.json"
        documents.append(json.loads(event_path.read_text(encoding="utf-8")))
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalogs[chapter] = {
            str(row["anchor_id"]): str(row["quote"])
            for row in catalog["entries"]
        }
    return documents, catalogs


def validate_new_artifacts(root: Path) -> dict[str, Any]:
    expected = {
        NEW_CONTRACT_PATH: NEW_CONTRACT_SHA256,
        CLASSIFY_MODULE_PATH: CLASSIFY_MODULE_SHA256,
        RUNNER_PATH: RUNNER_SHA256,
        FORMAL_DECISIONS_PATH: FORMAL_DECISIONS_SHA256,
        OLD_RUNNER_PIN_PATH: OLD_RUNNER_SHA256,
        OLD_MODULE_PIN_PATH: OLD_MODULE_SHA256,
    }
    for relative, expected_sha in expected.items():
        if sha256_file(root / relative) != expected_sha:
            raise RuntimeError(f"第57道已验收工件SHA漂移：{relative}")
    contract = classify_rules.load_contract(root / NEW_CONTRACT_PATH, project_root=root)
    documents, catalogs = _load_catalogs(root)
    decisions = json.loads((root / FORMAL_DECISIONS_PATH).read_text(encoding="utf-8"))
    event_map, _ = classify_rules.index_events(documents)
    reasons = classify_rules.decision_reasons(
        decisions,
        run_id=str(decisions.get("run_id") or ""),
        event_ids=set(event_map),
        contract=contract,
        event_documents=documents,
        evidence_catalogs=catalogs,
    )
    if reasons:
        raise RuntimeError(f"第57道正式决定零调用回归失败：{reasons}")
    return {
        "new_contract_sha256": NEW_CONTRACT_SHA256,
        "classify_module_sha256": CLASSIFY_MODULE_SHA256,
        "runner_sha256": RUNNER_SHA256,
        "formal_decisions_sha256": FORMAL_DECISIONS_SHA256,
        "event_total": len(event_map),
        "model_api_calls": 0,
    }


def recover_prepared_transaction(root: Path) -> dict[str, Any] | None:
    transaction_path = root / TRANSACTION_PATH
    if not transaction_path.is_file():
        return None
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    if transaction.get("revision_id") != REVISION_ID or transaction.get("status") != "prepared":
        return transaction
    default_archive = root / str(transaction["rollback_default_registry"])
    commit_archive = root / str(transaction["rollback_commit_marker"])
    if sha256_file(default_archive) != OLD_DEFAULT_SHA256 or sha256_file(commit_archive) != OLD_COMMIT_SHA256:
        raise RuntimeError("第57道半写恢复所需前代档不可信")
    default_path = root / DEFAULT_PATH
    commit_path = root / COMMIT_PATH
    current_default_sha = sha256_file(default_path)
    current_commit_sha = sha256_file(commit_path)
    planned_default_sha = str(transaction.get("planned_default_registry_sha256") or "")
    if current_default_sha == planned_default_sha:
        commit = json.loads(commit_path.read_text(encoding="utf-8"))
        if commit.get("default_registry", {}).get("sha256") == planned_default_sha:
            transaction["status"] = "recovered_as_committed"
            write_atomic(transaction_path, json_bytes(transaction))
            return transaction
    write_atomic(default_path, default_archive.read_bytes())
    write_atomic(commit_path, commit_archive.read_bytes())
    transaction["status"] = "recovered_to_predecessor"
    transaction["observed_partial_default_sha256"] = current_default_sha
    transaction["observed_partial_commit_sha256"] = current_commit_sha
    write_atomic(transaction_path, json_bytes(transaction))
    return transaction


def activate(root: Path, *, full_verify: bool = True) -> dict[str, Any]:
    root = root.resolve()
    recover_prepared_transaction(root)
    artifact_validation = validate_new_artifacts(root)
    default_path = root / DEFAULT_PATH
    commit_path = root / COMMIT_PATH
    old_contract_path = root / OLD_CONTRACT_PATH
    new_contract_path = root / NEW_CONTRACT_PATH
    module_path = root / CLASSIFY_MODULE_PATH
    runner_path = root / RUNNER_PATH
    outbox_manifest_path = root / OUTBOX_MANIFEST_PATH
    old_default_archive = root / (
        "config/defaults/history/zbatch_v1.2_full_chain_"
        f"{OLD_DEFAULT_SHA256}.json"
    )
    old_commit_archive = root / (
        "config/defaults/history/zbatch_v1.2_full_chain.COMMITTED_"
        f"{OLD_COMMIT_SHA256}.json"
    )

    if sha256_file(old_contract_path) != OLD_CONTRACT_SHA256:
        raise RuntimeError("旧v1.2分类合同发生漂移，拒绝施工")
    if sha256_file(outbox_manifest_path) != OUTBOX_MANIFEST_SHA256:
        raise RuntimeError("第36道outbox清单发生漂移，拒绝施工")

    current_default = json.loads(default_path.read_text(encoding="utf-8"))
    if (current_default.get("compatibility_revision") or {}).get("revision_id") == REVISION_ID:
        revision = current_default["compatibility_revision"]
        expected_active_refs = {
            "authority": AUTHORITY,
            "predecessor_default_registry_sha256": OLD_DEFAULT_SHA256,
            "semantic_rules_changed": False,
            "sequential_event_id_scope": "run_local_only",
        }
        if any(revision.get(key) != value for key, value in expected_active_refs.items()):
            raise RuntimeError("第57道已激活登记的固定身份字段不可信")
        if current_default["chain"]["classify_contract"] != {
            "path": NEW_CONTRACT_PATH.as_posix(),
            "sha256": NEW_CONTRACT_SHA256,
        }:
            raise RuntimeError("第57道已激活登记没有绑定已验收新合同")
        if current_default["chain"]["classify_rules_module"].get("sha256") != CLASSIFY_MODULE_SHA256:
            raise RuntimeError("第57道已激活登记没有绑定已验收分类模块")
        if current_default["chain"]["runner"].get("sha256") != RUNNER_SHA256:
            raise RuntimeError("第57道已激活登记没有绑定已验收运行器")
        current_sha = sha256_file(default_path)
        commit = json.loads(commit_path.read_text(encoding="utf-8"))
        if commit.get("default_registry", {}).get("sha256") != current_sha:
            raise RuntimeError("第57道默认登记已在，但提交标记未绑定它")
        if full_verify:
            zbatch_default_registry.verify(root, default_path)
        return {
            "status": "already_active",
            "revision_id": REVISION_ID,
            "default_registry_sha256": current_sha,
            "old_contract_sha256": OLD_CONTRACT_SHA256,
            **artifact_validation,
            "outbox_rewritten": False,
            "model_api_calls": 0,
        }

    old_default_bytes = default_path.read_bytes()
    old_commit_bytes = commit_path.read_bytes()
    if sha256_bytes(old_default_bytes) != OLD_DEFAULT_SHA256:
        raise RuntimeError("活跃默认登记不是第36道已知前代，拒绝覆盖")
    if sha256_bytes(old_commit_bytes) != OLD_COMMIT_SHA256:
        raise RuntimeError("默认提交标记不是第36道已知前代，拒绝覆盖")
    archive_exact(old_default_archive, old_default_bytes)
    archive_exact(old_commit_archive, old_commit_bytes)

    new_contract_sha = sha256_file(new_contract_path)
    module_sha = sha256_file(module_path)
    runner_sha = sha256_file(runner_path)
    registry = copy.deepcopy(current_default)
    registry["authority"] = (
        "第44道重发第36道施工令升默认；第57道CZ拍a，仅改回归锚载体为稳定语义身份"
    )
    registry["compatibility_revision"] = {
        "schema_version": "zbatch-default-compatibility-revision-v1",
        "revision_id": REVISION_ID,
        "authority": AUTHORITY,
        "activated_at": ACTIVATED_AT,
        "predecessor_default_registry_sha256": OLD_DEFAULT_SHA256,
        "predecessor_commit_marker_sha256": OLD_COMMIT_SHA256,
        "semantic_rules_changed": False,
        "semantic_rules_sha256": registry["chain"]["classification_prompt"]["sha256"],
        "sequential_event_id_scope": "run_local_only",
        "identity_carrier": "chapter+frozen-anchor-quote-fingerprint+semantic-term-groups",
        "old_contract": {
            "path": OLD_CONTRACT_PATH.as_posix(),
            "sha256": OLD_CONTRACT_SHA256,
            "status": "archived_unchanged_rollback_source"
        },
        "new_contract": {
            "path": NEW_CONTRACT_PATH.as_posix(),
            "sha256": new_contract_sha
        },
        "classify_rules_module": {
            "path": CLASSIFY_MODULE_PATH.as_posix(),
            "sha256": module_sha,
            "predecessor_pinned_path": OLD_MODULE_PIN_PATH.as_posix(),
            "predecessor_sha256": OLD_MODULE_SHA256
        },
        "runner": {
            "path": RUNNER_PATH.as_posix(),
            "sha256": runner_sha,
            "predecessor_pinned_path": OLD_RUNNER_PIN_PATH.as_posix(),
            "predecessor_sha256": OLD_RUNNER_SHA256,
            "behavior_change": "只把已落盘冻结证据目录交给稳定身份闸；旧合同路径行为等价"
        },
        "validation_fixture": {
            "decisions_path": FORMAL_DECISIONS_PATH.as_posix(),
            "decisions_sha256": FORMAL_DECISIONS_SHA256,
            "source_extract_path": SOURCE_EXTRACT_PATH.as_posix(),
            "event_total": artifact_validation["event_total"],
            "gate_failures": []
        },
        "frozen_outbox": {
            "mode": "historical_promotion_snapshot_no_rewrite",
            "manifest_path": OUTBOX_MANIFEST_PATH.as_posix(),
            "manifest_sha256": OUTBOX_MANIFEST_SHA256
        },
        "rollback": {
            "default_registry_archive": old_default_archive.relative_to(root).as_posix(),
            "commit_marker_archive": old_commit_archive.relative_to(root).as_posix(),
            "old_contract_path": OLD_CONTRACT_PATH.as_posix(),
            "old_runner_pinned_path": OLD_RUNNER_PIN_PATH.as_posix(),
            "old_classify_module_pinned_path": OLD_MODULE_PIN_PATH.as_posix()
        }
    }
    registry["chain"]["classify_contract"] = {
        "path": NEW_CONTRACT_PATH.as_posix(),
        "sha256": new_contract_sha,
    }
    registry["chain"]["classify_rules_module"]["sha256"] = module_sha
    registry["chain"]["runner"]["sha256"] = runner_sha
    for row in registry["chain"]["program_inventory"]:
        if row.get("path") == CLASSIFY_MODULE_PATH.as_posix():
            row["sha256"] = module_sha
    registry["activation"]["rule"] = (
        "活跃登记由提交标记绑定；第36道outbox保持历史快照，由compatibility_revision显式连接前代登记，不回写。"
    )
    registry["red_lines"]["regression_anchor_carrier_changed_by_z57"] = True
    registry["red_lines"]["sequential_event_id_cross_run_semantics"] = False
    new_default_bytes = json_bytes(registry)
    new_default_sha = sha256_bytes(new_default_bytes)

    commit = json.loads(old_commit_bytes.decode("utf-8"))
    commit["committed_at"] = ACTIVATED_AT
    commit["compatibility_revision_id"] = REVISION_ID
    commit["default_registry"] = {
        "path": DEFAULT_PATH.as_posix(),
        "sha256": new_default_sha,
    }
    new_commit_bytes = json_bytes(commit)

    transaction = {
        "schema_version": "z57-default-contract-transaction-v1",
        "revision_id": REVISION_ID,
        "status": "prepared",
        "planned_default_registry_sha256": new_default_sha,
        "planned_commit_marker_sha256": sha256_bytes(new_commit_bytes),
        "rollback_default_registry": old_default_archive.relative_to(root).as_posix(),
        "rollback_commit_marker": old_commit_archive.relative_to(root).as_posix(),
        "outbox_manifest_sha256": OUTBOX_MANIFEST_SHA256,
        "outbox_rewritten": False,
    }
    transaction_path = root / TRANSACTION_PATH
    write_atomic(transaction_path, json_bytes(transaction))

    try:
        write_atomic(default_path, new_default_bytes)
        write_atomic(commit_path, new_commit_bytes)
        if full_verify:
            zbatch_default_registry.verify(root, default_path)
        transaction["status"] = "committed"
        transaction["committed_default_registry_sha256"] = sha256_file(default_path)
        transaction["committed_commit_marker_sha256"] = sha256_file(commit_path)
        write_atomic(transaction_path, json_bytes(transaction))
    except Exception:
        write_atomic(default_path, old_default_bytes)
        write_atomic(commit_path, old_commit_bytes)
        transaction["status"] = "rolled_back_after_error"
        write_atomic(transaction_path, json_bytes(transaction))
        raise

    return {
        "status": "activated",
        "revision_id": REVISION_ID,
        "default_registry_sha256": new_default_sha,
        "commit_marker_sha256": sha256_bytes(new_commit_bytes),
        "old_contract_sha256": OLD_CONTRACT_SHA256,
        "new_contract_sha256": new_contract_sha,
        "classify_module_sha256": module_sha,
        "runner_sha256": runner_sha,
        "formal_decisions_sha256": FORMAL_DECISIONS_SHA256,
        "rollback_default_registry": old_default_archive.relative_to(root).as_posix(),
        "rollback_commit_marker": old_commit_archive.relative_to(root).as_posix(),
        "outbox_manifest_sha256": OUTBOX_MANIFEST_SHA256,
        "outbox_rewritten": False,
        "model_api_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="第57道稳定语义身份合同激活器")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    result = activate(Path(args.root), full_verify=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
