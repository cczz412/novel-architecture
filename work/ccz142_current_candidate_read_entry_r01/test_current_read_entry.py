"""Offline entry checks, including missing/tampered files and arbitrary cwd."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("issue270_entry_check", HERE / "self_check.py")
assert SPEC is not None and SPEC.loader is not None
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


@pytest.fixture
def entry(tmp_path: Path) -> Path:
    target = tmp_path / "已解压 样张入口"
    target.mkdir()
    for name in [CHECK.ENTRY_NAME, "SOURCE_SAMPLES.json", "self_check.py"]:
        shutil.copyfile(HERE / name, target / name)
    shutil.copytree(HERE / "samples", target / "samples")
    return target


def fingerprints(root: Path) -> dict:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*") if path.is_file()
    }


def test_shipped_entry_passes() -> None:
    result = CHECK.check_entry(HERE)
    assert result["status"] == "PASS"
    assert result["source_comparison"] == "PINNED_COPIES_ONLY"


def test_no_live_store_no_source_repo_and_zero_writes(entry: Path) -> None:
    before = fingerprints(entry)
    result = CHECK.check_entry(entry)
    assert result["samples_verified"] == 3
    assert result["live_store_checked"] is False
    assert result["check_scope"] == "STATIC_FILES_ONLY"
    assert fingerprints(entry) == before
    assert not list(entry.rglob("*.db"))


@pytest.mark.parametrize("name", sorted(CHECK.EXPECTED))
def test_copies_match_fixed_source_hashes(entry: Path, name: str) -> None:
    content = (entry / "samples" / name).read_bytes()
    import hashlib
    assert hashlib.sha256(content).hexdigest() == CHECK.EXPECTED[name][0]
    blob = b"blob " + str(len(content)).encode() + b"\0" + content
    assert hashlib.sha1(blob).hexdigest() == CHECK.EXPECTED[name][1]


@pytest.mark.parametrize("name", sorted(CHECK.EXPECTED))
def test_missing_sample_fails(entry: Path, name: str) -> None:
    (entry / "samples" / name).unlink()
    with pytest.raises(CHECK.CheckError, match="缺文件"):
        CHECK.check_entry(entry)


@pytest.mark.parametrize("name", sorted(CHECK.EXPECTED))
def test_even_one_added_byte_fails(entry: Path, name: str) -> None:
    path = entry / "samples" / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(CHECK.CheckError, match="不是原样副本"):
        CHECK.check_entry(entry)


@pytest.mark.parametrize("old,new", [
    ('href="samples/no_live_store.html"', 'href="https://example.invalid/card"'),
    ('href="samples/no_live_store.html"', 'href="../outside.html"'),
    ('id="open-gap"', 'id="open-types"'),
    ('<body>', '<body onload="alert(1)">'),
    ('</head>', '<script>fetch("https://example.invalid")</script></head>'),
    ('</head>', '<base href="https://example.invalid/"></head>'),
    ('</head>', '<meta http-equiv="refresh" content="0;url=elsewhere"></head>'),
    ('</style>', 'body{background:url(https://example.invalid/x)}</style>'),
    ('</style>', '@import "https://example.invalid/x";</style>'),
    ('<body>', '<body><form action="/submit"></form>'),
    ('<body>', '<body><img src="https://example.invalid/pixel">'),
    ('<body>', '<body><iframe src="samples/no_live_store.html"></iframe>'),
])
def test_active_or_changed_landing_fails(entry: Path, old: str, new: str) -> None:
    path = entry / CHECK.ENTRY_NAME
    assert old in path.read_text(encoding="utf-8")
    path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    with pytest.raises(CHECK.CheckError):
        CHECK.check_entry(entry)


@pytest.mark.parametrize("field,value", [
    ("source_commit", "main"),
    ("status", "MERGED"),
    ("product_adopted", True),
    ("live_store_checked", True),
    ("samples", []),
])
def test_manifest_identity_drift_fails(entry: Path, field: str, value: object) -> None:
    path = entry / "SOURCE_SAMPLES.json"
    manifest = json.loads(path.read_bytes())
    manifest[field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CHECK.CheckError):
        CHECK.check_entry(entry)


def test_exact_source_comparison_reads_only_three_html_files(entry: Path, tmp_path: Path) -> None:
    root = tmp_path / "仓库切片"
    source = root / CHECK.SOURCE_DIR
    shutil.copytree(entry / "samples", source)
    before = fingerprints(root)
    assert CHECK.check_entry(entry, root)["source_comparison"] == "MATCHED_THREE_SOURCE_FILES"
    assert fingerprints(root) == before
    (source / "types_layout.html").write_bytes(b"changed")
    with pytest.raises(CHECK.CheckError, match="仓库样张"):
        CHECK.check_entry(entry, root)


def test_missing_explicit_source_is_not_silently_skipped(entry: Path, tmp_path: Path) -> None:
    with pytest.raises(CHECK.CheckError, match="缺文件"):
        CHECK.check_entry(entry, tmp_path / "absent")


def test_self_check_runs_from_unrelated_cwd(entry: Path, tmp_path: Path) -> None:
    before = fingerprints(entry)
    result = subprocess.run(
        [sys.executable, "-B", str(entry / "self_check.py")],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"
    assert fingerprints(entry) == before


def test_cli_failure_has_nonzero_exit(entry: Path, tmp_path: Path) -> None:
    (entry / "samples" / "no_live_store.html").unlink()
    result = subprocess.run(
        [sys.executable, "-B", str(entry / "self_check.py")],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "FAIL"


def test_pr_draft_has_only_one_linear_reference() -> None:
    references = re.findall(r"\b[A-Z]{2,10}-\d+\b", (HERE / "PR_DRAFT.md").read_text(encoding="utf-8"))
    assert references == ["CCZ-142"]
