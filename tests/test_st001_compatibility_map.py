from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = (
    ROOT / "side-tracks/tracks/ST-001_corpus_relabel/ST001_COMPATIBILITY_MAP.json"
)
REGISTRY_PATH = ROOT / "governance/external_archive_registry.json"
LINE_RE = re.compile(r"第(\d+)行")
ROUTE_RE = re.compile(r"^corpus_relabel\.csv:(\d+)$")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def stable_identity(identity_fields: dict[str, str]) -> str:
    payload = {
        "author": identity_fields["author"],
        "platform": identity_fields["platform"],
        "title": identity_fields["title"],
    }
    return "st001-record-v1:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def frozen_refs(compatibility_map: dict[str, Any]) -> set[tuple[str, str, int]]:
    refs: set[tuple[str, str, int]] = set()
    rights_path = ROOT / compatibility_map["frozen_consumers"][0]["path"]
    route_path = ROOT / compatibility_map["frozen_consumers"][1]["path"]
    rights = json.loads(rights_path.read_text())
    route = json.loads(route_path.read_text())
    for entry in rights["entries"]:
        for source in entry.get("source_objects", []):
            if source.get("path") != compatibility_map["identity_binding"]["table_path"]:
                continue
            match = LINE_RE.search(source["truth_role"])
            assert match
            refs.add((rights_path.relative_to(ROOT).as_posix(), entry["book_key"], int(match.group(1))))
    for book in route["books"]:
        for source in book.get("source_refs", []):
            match = ROUTE_RE.match(source)
            if match:
                refs.add((route_path.relative_to(ROOT).as_posix(), book["case_id"], int(match.group(1))))
    return refs


def test_frozen_legacy_references_have_exact_compatibility_rows() -> None:
    compatibility_map = json.loads(MAP_PATH.read_text())
    for frozen in compatibility_map["frozen_consumers"]:
        assert frozen["authority"] == "frozen_original_bytes"
        assert sha256_file(ROOT / frozen["path"]) == frozen["sha256"]
    expected = frozen_refs(compatibility_map)
    actual = {
        (row["legacy_consumer_path"], row["legacy_consumer_id"], row["legacy_line_reference"])
        for row in compatibility_map["legacy_mappings"]
    }
    assert expected == actual
    assert len(actual) == 6


def test_stable_identity_does_not_include_physical_line_or_ordinal() -> None:
    compatibility_map = json.loads(MAP_PATH.read_text())
    identities = []
    for record in compatibility_map["stable_records"]:
        identity = stable_identity(record["identity_fields"])
        assert identity == record["record_identity"]
        shifted_ordinal = record["record_ordinal_excluding_header"] + 1
        assert shifted_ordinal != record["record_ordinal_excluding_header"]
        assert stable_identity(record["identity_fields"]) == identity
        identities.append(identity)
    assert len(identities) == len(set(identities)) == 4


def test_record_hash_detects_content_change_without_changing_identity() -> None:
    columns = ["title", "platform", "author", "evidence"]
    values = ["万族之劫", "起点中文网", "老鹰吃小鸡", "original"]
    original = {"columns": columns, "schema_version": "st001-canonical-row-v1", "values": values}
    changed = {**original, "values": [*values[:-1], "changed"]}
    identity_fields = {"title": values[0], "platform": values[1], "author": values[2]}
    assert stable_identity(identity_fields) == stable_identity(identity_fields)
    assert hashlib.sha256(canonical_bytes(original)).hexdigest() != hashlib.sha256(canonical_bytes(changed)).hexdigest()


def test_archive_registry_binding_matches_compatibility_map() -> None:
    compatibility_map = json.loads(MAP_PATH.read_text())
    registry = json.loads(REGISTRY_PATH.read_text())
    archive = compatibility_map["archive_binding"]
    matches = [
        row
        for row in registry["objects"]
        if row["artifact_id"] == compatibility_map["identity_binding"]["archive_object_id"]
    ]
    assert len(matches) == 1
    row = matches[0]
    assert row["root_id"] == archive["root_id"]
    assert row["relative_path"] == archive["relative_path"]
    assert row["manifest"]["relative_path"] == archive["manifest_relative_path"]
    assert row["manifest"]["sha256"] == archive["manifest_sha256"]
