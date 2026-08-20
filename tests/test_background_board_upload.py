from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tools import build_background_board_upload_zip as builder


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _manifest_rows(root: Path, relatives: list[str]) -> list[dict]:
    return [
        {
            "path": relative,
            "bytes": (root / relative).stat().st_size,
            "sha256": _sha256(root / relative),
        }
        for relative in relatives
    ]


def _fixture_repo(tmp_path: Path, *, add_symlink: bool = False) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    product = root / "references/shared-context/PRODUCT_BOARD_R13"
    report_parent = root / "references/external-knowledge-base"
    report = report_parent / "REPORT_BOARD_R01"
    atomic_parent = root / "references/atomic-expectations"
    atomic = atomic_parent / "ATOMIC_EXPECTATION_BOARD_R01"
    product.joinpath("assets").mkdir(parents=True)
    report.joinpath("background").mkdir(parents=True)
    atomic.mkdir(parents=True)

    product.joinpath("00_READ_ME_FIRST.md").write_text(
        "# 产品\n\n[同名页](same.md) [图片](assets/picture.png)\n",
        encoding="utf-8",
    )
    product.joinpath("same.md").write_text("产品同名页\n", encoding="utf-8")
    product.joinpath("BUILD_RECEIPT.json").write_text(
        '{"status":"PASS"}\n', encoding="utf-8"
    )
    product.joinpath("assets/picture.png").write_bytes(b"\x89PNG\r\nfixture")
    product.joinpath(".DS_Store").write_bytes(b"cache")
    product.joinpath("__pycache__").mkdir()
    product.joinpath("__pycache__/cache.pyc").write_bytes(b"cache")
    if add_symlink:
        product.joinpath("linked.md").symlink_to("same.md")
    product_manifest = product / "CORE_MATERIALS_MANIFEST.json"
    _write_json(
        product_manifest,
        {
            "members": _manifest_rows(
                product,
                ["00_READ_ME_FIRST.md", "same.md", "assets/picture.png"],
            )
        },
    )
    incomplete = root / "references/shared-context/PRODUCT_BOARD_R14"
    incomplete.mkdir()
    incomplete.joinpath("00_READ_ME_FIRST.md").write_text(
        "# 尚未完成的 R14\n", encoding="utf-8"
    )
    draft = root / "references/shared-context/PRODUCT_BOARD_R99_DRAFT"
    draft.mkdir()
    draft.joinpath("00_READ_ME_FIRST.md").write_text("# 草稿\n", encoding="utf-8")
    _write_json(draft / "CORE_MATERIALS_MANIFEST.json", {"members": []})

    report.joinpath("00_READ_ME_FIRST.md").write_text(
        "# 报告\n\n[主题页](background/topic.md)\n", encoding="utf-8"
    )
    report.joinpath("same.md").write_text("报告同名页\n", encoding="utf-8")
    report.joinpath("background/topic.md").write_text(
        "# 主题\n\n[报告同名页](../same.md)\n", encoding="utf-8"
    )
    report.joinpath("background/._topic.md").write_bytes(b"apple double")
    report.joinpath("__MACOSX").mkdir()
    report.joinpath("__MACOSX/cache").write_bytes(b"cache")
    report_manifest = report / "MANIFEST.json"
    _write_json(
        report_manifest,
        {
            "files": [
                *_manifest_rows(
                    report,
                    ["00_READ_ME_FIRST.md", "same.md", "background/topic.md"],
                ),
                {"path": "MANIFEST.json", "bytes": None, "sha256": None},
            ]
        },
    )
    _write_json(
        report_parent / "CURRENT.json",
        {
            "current_version": "R01",
            "current_package_id": "REPORT_BOARD_R01",
            "entry_path": "REPORT_BOARD_R01/00_READ_ME_FIRST.md",
            "manifest_path": "REPORT_BOARD_R01/MANIFEST.json",
            "manifest_sha256": _sha256(report_manifest),
        },
    )
    atomic.joinpath("00_READ_ME_FIRST.md").write_text(
        "# 原子预期\n\n[机器数据](expectations.json)\n",
        encoding="utf-8",
    )
    _write_json(
        atomic / "expectations.json",
        {
            "records": [
                {
                    "id": "M1-E01",
                    "expectation": "输入不能静默丢失",
                }
            ]
        },
    )
    atomic_manifest = atomic / "MANIFEST.json"
    _write_json(
        atomic_manifest,
        {
            "files": [
                *_manifest_rows(
                    atomic,
                    ["00_READ_ME_FIRST.md", "expectations.json"],
                ),
                {"path": "MANIFEST.json", "bytes": None, "sha256": None},
            ]
        },
    )
    _write_json(
        atomic_parent / "CURRENT.json",
        {
            "current_version": "R01",
            "current_package_id": "ATOMIC_EXPECTATION_BOARD_R01",
            "entry_path": "ATOMIC_EXPECTATION_BOARD_R01/00_READ_ME_FIRST.md",
            "manifest_path": "ATOMIC_EXPECTATION_BOARD_R01/MANIFEST.json",
            "manifest_sha256": _sha256(atomic_manifest),
        },
    )
    root.joinpath("AGENTS.md").write_text(
        "[当前产品板](references/shared-context/PRODUCT_BOARD_R13/00_READ_ME_FIRST.md)\n",
        encoding="utf-8",
    )
    config_path = root / "config/background_board_upload/sources.json"
    _write_json(
        config_path,
        {
            "schema_version": builder.CONFIG_SCHEMA,
            "output_directory": "TEMP/background-board-upload",
            "sources": [
                {
                    "source_id": "product_background",
                    "label": "产品共同背景板",
                    "role": "product_authority",
                    "prefix": "PRODUCT",
                    "resolver": "highest_version_directory",
                    "base_directory": "references/shared-context",
                    "additional_included_files": ["BUILD_RECEIPT.json"],
                    "directory_prefix": "PRODUCT_BOARD_",
                    "entry_name": "00_READ_ME_FIRST.md",
                    "manifest_name": "CORE_MATERIALS_MANIFEST.json",
                    "daily_directory": None,
                    "flatten_aliases": {},
                },
                {
                    "source_id": "report_background",
                    "label": "外部报告背景板",
                    "role": "external_evidence",
                    "prefix": "REPORT",
                    "resolver": "current_pointer",
                    "pointer_path": "references/external-knowledge-base/CURRENT.json",
                    "entry_field": "entry_path",
                    "manifest_field": "manifest_path",
                    "version_field": "current_version",
                    "daily_directory": "background",
                    "flatten_aliases": {"background": "BG"},
                },
                {
                    "source_id": "atomic_expectations_background",
                    "label": "原子需求与验收背景板",
                    "role": "requirements_acceptance_baseline",
                    "prefix": "ATOMIC",
                    "resolver": "current_pointer",
                    "pointer_path": "references/atomic-expectations/CURRENT.json",
                    "entry_field": "entry_path",
                    "manifest_field": "manifest_path",
                    "version_field": "current_version",
                    "daily_directory": None,
                    "flatten_aliases": {},
                },
            ],
        },
    )
    return root, config_path


def test_builds_deterministic_flat_prefixed_clean_zip(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path)

    first = builder.compile_package(root, config_path)
    second = builder.compile_package(root, config_path)
    assert first.zip_bytes == second.zip_bytes
    assert first.source_file_count == 12
    assert first.zip_member_count == 15
    assert first.skipped_count == 4
    assert first.sources[0].version == "R13"

    created = builder.run(root, config_path, check=False)
    assert created["status"] == "CREATED"
    reused = builder.run(root, config_path, check=False)
    assert reused["status"] == "REUSED_BYTE_IDENTICAL"
    checked = builder.run(root, config_path, check=True)
    assert checked["status"] == "PASS_BYTE_IDENTICAL"

    zip_path = Path(created["zip_path"])
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        assert all("/" not in name for name in names)
        assert "PRODUCT_R13__00_READ_ME_FIRST.md" in names
        assert "REPORT_R01__00_READ_ME_FIRST.md" in names
        assert "REPORT_R01__BG__topic.md" in names
        assert "ATOMIC_R01__00_READ_ME_FIRST.md" in names
        assert "ATOMIC_R01__expectations.json" in names
        assert "PRODUCT_R13__same.md" in names
        assert "PRODUCT_R13__BUILD_RECEIPT.json" in names
        assert "REPORT_R01__same.md" in names
        assert all(".DS_Store" not in name for name in names)
        assert all("__MACOSX" not in name for name in names)
        assert archive.read("PRODUCT_R13__assets__picture.png") == b"\x89PNG\r\nfixture"
        product_entry = archive.read("PRODUCT_R13__00_READ_ME_FIRST.md").decode()
        assert "(PRODUCT_R13__same.md)" in product_entry
        assert "(PRODUCT_R13__assets__picture.png)" in product_entry
        report_topic = archive.read("REPORT_R01__BG__topic.md").decode()
        assert "(REPORT_R01__same.md)" in report_topic
        atomic_entry = archive.read("ATOMIC_R01__00_READ_ME_FIRST.md").decode()
        assert "(ATOMIC_R01__expectations.json)" in atomic_entry
        router = archive.read(builder.ROUTER_NAME).decode()
        assert "原子需求与验收背景板" in router
        assert "怎样验收" in router
        assert "## 当前背景板" in router
        assert "## 两套当前背景板" not in router
        manifest = json.loads(archive.read(builder.MANIFEST_NAME))
        assert manifest["source_count"] == 3
        assert manifest["junk_excluded_count"] == 4


def test_rejects_symlink_inside_source_board(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path, add_symlink=True)

    with pytest.raises(builder.BackgroundPackageError, match="符号链接"):
        builder.compile_package(root, config_path)


def test_rejects_unmanifested_plain_file(tmp_path: Path) -> None:
    root, config_path = _fixture_repo(tmp_path)
    unexpected = root / "references/shared-context/PRODUCT_BOARD_R13/unexpected.md"
    unexpected.write_text("不能顺手打包\n", encoding="utf-8")

    with pytest.raises(builder.BackgroundPackageError, match="清单外普通文件"):
        builder.compile_package(root, config_path)


def test_current_atomic_board_is_stable_projection() -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "references/atomic-expectations"
    pointer = json.loads((base / "CURRENT.json").read_text(encoding="utf-8"))
    manifest = base / pointer["manifest_path"]
    assert _sha256(manifest) == pointer["manifest_sha256"]

    board = manifest.parent
    payload = json.loads(
        (board / "02_ATOMIC_EXPECTATIONS.json").read_text(encoding="utf-8")
    )
    records = payload["records"]
    assert len(records) == 127
    assert len({row["预期ID"] for row in records}) == 127
    assert payload["totals"] == {
        "records": 127,
        "core": 78,
        "bonus": 49,
        "needs_real_novel": 44,
    }

    forbidden = {
        "当前状态",
        "当前完成度",
        "本地证据",
        "基线分",
        "本次分",
        "回归结论",
        "回归阈值",
        "材料状态",
        "数据包ID",
    }
    for row in records:
        assert set(row) == {
            "预期ID",
            "长期需求",
            "当前产品判断",
            "现行验收参考",
        }
        assert forbidden.isdisjoint(row)
        assert "/Users/" not in json.dumps(row, ensure_ascii=False)
