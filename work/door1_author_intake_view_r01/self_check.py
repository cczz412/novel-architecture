"""机械核对交付文件、输入指纹和边界；不把单测替身当成真实库联调。"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
for path in (REPO, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_view import BASE_MAIN_SHA, DOCUMENT_IDENTITY, LEDGER_NAMES  # noqa: E402
from marks_sidecar import ENVELOPE_KEYS, MARK_KEYS, MAX_BYTES, MAX_MARKS, SCHEMA_VERSION  # noqa: E402
from view_render import SCRIPT  # noqa: E402

EXPECTED_FILES = {
    "build_view.py",
    "view_render.py",
    "marks_sidecar.py",
    "test_door1_view.py",
    "self_check.py",
    "README.md",
    "SOURCE_INDEX.md",
    "OBJECT_SHAPES.json",
    "TEST_RECEIPT_R01.json",
    "MANIFEST.sha256",
}
HISTORICAL_INPUT_PATHS = frozenset(
    (
        "work/ccz142_human_card_vertical_wire_r01/test_human_card_vertical_wire.py",
        "work/ccz142_human_card_vertical_wire_r01/MANIFEST.sha256",
        "work/ccz142_named_chapter_txt_card_r01/test_named_chapter_txt_card.py",
        "work/ccz142_named_chapter_txt_card_r01/MANIFEST.sha256",
        "work/ccz142_current_candidate_read_preview_r01/test_current_read_preview.py",
        "work/ccz142_current_candidate_read_preview_r01/self_check.py",
        "work/ccz142_current_candidate_read_preview_r01/MANIFEST.sha256",
        "governance/agent_ticket_rules.md",
        "governance/START_HERE.md",
    )
)

IMPLEMENTATION_FILES = {"build_view.py", "view_render.py", "marks_sidecar.py"}
FORBIDDEN_IMPORTS = {
    "socket",
    "requests",
    "httpx",
    "urllib",
    "aiohttp",
    "openai",
    "anthropic",
    "subprocess",
    "sqlite3",
}
FORBIDDEN_CALLS = {
    "initialize_authority_schema",
    "initialize_root",
    "wire_synthetic_chapter_to_card",
    "drop_named_chapter",
    "execute",
    "executemany",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest() -> int:
    listed = {}
    for line in (ROOT / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if name in listed or name not in EXPECTED_FILES - {"MANIFEST.sha256"}:
            raise RuntimeError("DOOR1_MANIFEST_SET")
        if sha(ROOT / name) != digest:
            raise RuntimeError("DOOR1_MANIFEST_HASH:" + name)
        listed[name] = digest
    if set(listed) != EXPECTED_FILES - {"MANIFEST.sha256"}:
        raise RuntimeError("DOOR1_MANIFEST_SET")
    return len(listed)


def check_protected_inputs(shapes: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    protected = shapes["protected_input_sha256"]
    classification = shapes.get("historical_input_evidence")
    if (
        not isinstance(classification, dict)
        or set(classification) != HISTORICAL_INPUT_PATHS
        or not isinstance(protected, dict)
        or len(protected) != 71
        or not HISTORICAL_INPUT_PATHS <= protected.keys()
        or shapes.get("base_main_sha") != BASE_MAIN_SHA
    ):
        raise RuntimeError("DOOR1_HISTORICAL_CLASSIFICATION")
    for metadata in classification.values():
        if (
            not isinstance(metadata, dict)
            or set(metadata) != {"reason", "change_source"}
            or any(not isinstance(v, str) or not v.strip() for v in metadata.values())
        ):
            raise RuntimeError("DOOR1_HISTORICAL_CLASSIFICATION")
    checked = 0
    historical = []
    for rel, expected in protected.items():
        if rel not in HISTORICAL_INPUT_PATHS:
            if not (REPO / rel).is_file() or sha(REPO / rel) != expected:
                raise RuntimeError("DOOR1_PROTECTED_INPUT_DRIFT:" + rel)
            checked += 1
            continue
        record = {"path": rel, "historical_sha256": expected, "current_sha256": None}
        try:
            record["current_sha256"] = sha(REPO / rel)
        except FileNotFoundError:
            record["status"] = "missing"
        except OSError:
            record["status"] = "unreadable"
        else:
            record["status"] = (
                "same" if record["current_sha256"] == expected else "changed"
            )
        historical.append(record)
    return checked, historical


def run_self_check() -> dict[str, Any]:
    actual = {p.name for p in ROOT.iterdir() if p.is_file()}
    if actual != EXPECTED_FILES:
        raise RuntimeError(
            "DOOR1_FILE_SET:" + ",".join(sorted(actual ^ EXPECTED_FILES))
        )
    manifest_count = check_manifest()
    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if (
        shapes["schema_version"] != SCHEMA_VERSION
        or shapes["envelope_keys"] != sorted(ENVELOPE_KEYS)
        or shapes["mark_keys"] != sorted(MARK_KEYS)
        or shapes["max_bytes"] != MAX_BYTES
        or shapes["max_marks"] != MAX_MARKS
        or shapes["ledger_names"] != list(LEDGER_NAMES)
        or shapes["authority_wrote"] is not False
        or shapes["product_adopted"] is not False
    ):
        raise RuntimeError("DOOR1_OBJECT_SHAPES_DRIFT")
    checked, historical = check_protected_inputs(shapes)
    for name in IMPLEMENTATION_FILES:
        source = (ROOT / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            a.name.split(".")[0]
            for n in ast.walk(tree)
            if isinstance(n, ast.Import)
            for a in n.names
        }
        imports |= {
            (n.module or "").split(".")[0]
            for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom)
        }
        if imports & FORBIDDEN_IMPORTS:
            raise RuntimeError("DOOR1_FORBIDDEN_IMPORT:" + name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                if callee in FORBIDDEN_CALLS:
                    raise RuntimeError("DOOR1_FORBIDDEN_CALL:" + name + ":" + callee)
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket(",
        "sendBeacon(",
        "localStorage.setItem",
        "eval(",
    ):
        if forbidden in SCRIPT:
            raise RuntimeError("DOOR1_FORBIDDEN_JS_CALL")
    if (
        "createWritable" not in SCRIPT
        or "queryPermission" not in SCRIPT
        or "标记没读到" not in SCRIPT
    ):
        raise RuntimeError("DOOR1_MARKS_BRANCH_MISSING")
    missing = [
        p for p in shapes["integration_required_paths"] if not (REPO / p).is_file()
    ]
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "base_main_sha": BASE_MAIN_SHA,
        "result": "FAIL"
        if any(r["status"] in {"missing", "unreadable"} for r in historical)
        else "PASS",
        "manifest_verified_files": manifest_count,
        "protected_input_verified_files": checked,
        "historical_input_evidence": historical,
        "historical_input_compared_files": sum(
            r["status"] in {"same", "changed"} for r in historical
        ),
        "authority_wrote": False,
        "product_adopted": False,
        "network_calls": False,
        "integration_dependencies_present": not missing,
        "missing_integration_paths": missing,
        "note": "这是文件与边界机械检查，不是浏览器验收，也不代替真实库联调。",
    }


if __name__ == "__main__":
    report = run_self_check()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["result"] == "PASS" else 1)
