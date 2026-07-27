from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

from tools import chatgpt_review_pack
from tools.pipeline_common import artifacts


def test_test_reference_scan_only_requires_z_batch_replay_scripts() -> None:
    refs = chatgpt_review_pack._experiments_referenced_by_tests()

    assert "experiments/Z91_crossbook_v2_20260723" in refs
    assert "experiments/model_benchmarks" not in refs
    assert all(ref.startswith("experiments/Z") for ref in refs)


def test_manifest_path_uses_the_declared_identity_root(
    tmp_path: Path,
) -> None:
    inside = chatgpt_review_pack.ROOT / "TEMP/example.zip"
    outside = tmp_path / "example.zip"

    assert chatgpt_review_pack._manifest_path(inside) == "TEMP/example.zip"
    assert (
        chatgpt_review_pack._manifest_path(outside, identity_root=tmp_path)
        == "example.zip"
    )


def test_current_state_v2_paths_follow_dotted_keys() -> None:
    state = json.loads(
        chatgpt_review_pack.CURRENT_STATE.read_text(encoding="utf-8")
    )
    execution = state["current_execution"]
    expected_paths = []
    for value in (
        execution["run"]["run_directory"],
        execution["artifacts"]["report_directory"],
    ):
        if isinstance(value, str):
            expected_paths.append("/".join(value.split("/")[:2]))
    paths = chatgpt_review_pack._paths_from_current_state(
        ["run.run_directory", "artifacts.report_directory"]
    )

    assert paths == expected_paths


def _configure_minimal_pack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "source.txt"
    source.write_text("review payload", encoding="utf-8")
    config = root / "profiles.json"
    config.write_text(
        json.dumps(
            {
                "default_profile": "surface",
                "max_zip_mb": 25,
                "always_exclude_globs": [],
                "secret_name_markers": ["secret"],
                "profiles": {
                    "surface": {
                        "include_globs": ["source.txt"],
                        "run_globs": [],
                        "report_globs": [],
                        "follow_current_state": False,
                        "include_test_referenced_experiments": False,
                        "require_test_experiment_coverage": False,
                        "digest_z83_tickets": False,
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    routes = root / "routes.json"
    routes.write_text(
        json.dumps(
            {
                "schema_version": "chatgpt-review-source-routes-v1",
                "layer_order": [
                    "current_truth",
                    "current_route",
                    "upstream_evidence",
                    "external_reviews",
                ],
                "routes": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(chatgpt_review_pack, "ROOT", root)
    monkeypatch.setattr(chatgpt_review_pack, "PROFILES", config)
    monkeypatch.setattr(chatgpt_review_pack, "ROUTES", routes)
    monkeypatch.setattr(
        chatgpt_review_pack,
        "CURRENT_STATE",
        root / "governance/CURRENT_STATE.json",
    )
    monkeypatch.setattr(
        chatgpt_review_pack,
        "OUT_ROOT",
        root / "TEMP/chatgpt_review_packs",
    )
    return root, source


def test_dry_run_is_zero_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_minimal_pack(monkeypatch, tmp_path)
    out = tmp_path / "dry-run-out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--profile",
            "surface",
            "--dry-run",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    assert not out.exists()


def test_review_pack_contains_verified_manifest_and_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_minimal_pack(monkeypatch, tmp_path)
    out = tmp_path / "review-out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--profile",
            "surface",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    receipt = json.loads(
        (out / "PACKAGE_RECEIPT.json").read_text(encoding="utf-8")
    )
    zip_path = next(out.glob("chatgpt_review_*.zip"))
    assert receipt["integrity"]["passed"] is True
    assert receipt["zip"]["sha256"] == artifacts.sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert {
            "source.txt",
            "00_READ_ME_FOR_REVIEWER.md",
            "MANIFEST.json",
            "SHA256SUMS",
        } == set(archive.namelist())


def test_missing_required_run_leaves_no_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    config = json.loads(
        chatgpt_review_pack.PROFILES.read_text(encoding="utf-8")
    )
    config["profiles"]["surface"]["run_globs"] = ["runs/required_missing"]
    chatgpt_review_pack.PROFILES.write_text(
        json.dumps(config),
        encoding="utf-8",
    )
    out = root / "TEMP/should-not-exist"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--profile",
            "surface",
            "--out-dir",
            str(out),
        ],
    )

    with pytest.raises(SystemExit, match="required runs missing"):
        chatgpt_review_pack.main()
    assert not out.exists()


def _write_route_config(
    path: Path,
    *,
    required_glob: str = "source.txt",
    external_required: bool = True,
    forbidden_source_globs: list[str] | None = None,
    root_exclude_globs: list[str] | None = None,
    redact_local_absolute_paths: bool = False,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "chatgpt-review-source-routes-v1",
                "layer_order": [
                    "current_truth",
                    "current_route",
                    "upstream_evidence",
                    "external_reviews",
                ],
                "routes": {
                    "demo": {
                        "label": "演示路线",
                        "purpose": "测试路线取材",
                        "snapshot_at": "2026-07-27T06:50:00+08:00",
                        "truth_source": {
                            "authority": "test",
                            "local_current_state_status": "stale_mirror_only",
                        },
                        "default_layers": [
                            "current_truth",
                            "external_reviews",
                        ],
                        "forbidden_source_globs": (
                            forbidden_source_globs or []
                        ),
                        "redact_local_absolute_paths": (
                            redact_local_absolute_paths
                        ),
                        "layers": {
                            "current_truth": {
                                "label": "真源",
                                "roots": [
                                    {
                                        "root_id": "truth",
                                        "required": True,
                                        "authority": "test",
                                        "status": "active",
                                        "globs": [required_glob],
                                        "exclude_globs": (
                                            root_exclude_globs or []
                                        ),
                                    }
                                ],
                            },
                            "current_route": {"label": "当前路线", "roots": []},
                            "upstream_evidence": {
                                "label": "上游证据",
                                "roots": [],
                            },
                            "external_reviews": {
                                "label": "外部回包",
                                "roots": [],
                            },
                        },
                        "external_slots": [
                            {
                                "slot_id": "advisor",
                                "required": external_required,
                                "provider": "ChatGPT",
                                "model": "external",
                                "status": "candidate",
                            }
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_route_pack_layers_external_slot_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    _write_route_config(chatgpt_review_pack.ROUTES)
    external = tmp_path / "advisor.md"
    external.write_text("external review", encoding="utf-8")
    out = root / "TEMP/route-out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--external",
            f"advisor={external}",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    receipt = json.loads(
        (out / "PACKAGE_RECEIPT.json").read_text(encoding="utf-8")
    )
    assert receipt["route"] == "demo"
    assert receipt["selected_layers"] == [
        "current_truth",
        "external_reviews",
    ]
    assert receipt["secret_scan"]["result"] == "PASS"
    zip_path = next(out.glob("chatgpt_review_route_*.zip"))
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        assert "01_current_truth/source.txt" in names
        assert "04_external_reviews/advisor/advisor.md" in names
        selection = json.loads(
            archive.read("_route/ROUTE_SELECTION.json")
        )
    external_rows = [
        row
        for row in selection["sources"]
        if row["layer"] == "external_reviews"
    ]
    assert external_rows == [
        {
            "authority": "ChatGPT",
            "layer": "external_reviews",
            "local_only": True,
            "member": "04_external_reviews/advisor/advisor.md",
            "model": "external",
            "root_id": "advisor",
            "source_ref": "external_slot:advisor/advisor.md",
            "status": "candidate",
        }
    ]
    assert str(tmp_path) not in json.dumps(selection, ensure_ascii=False)


@pytest.mark.parametrize(
    ("argv_tail", "message"),
    [
        (["--route", "missing"], "未知 route"),
        (
            ["--route", "demo", "--layers", "not_a_layer"],
            "未知 route layer",
        ),
        (
            ["--route", "demo"],
            "required external slot 缺件",
        ),
    ],
)
def test_route_invalid_selection_leaves_no_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv_tail: list[str],
    message: str,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    _write_route_config(chatgpt_review_pack.ROUTES)
    out = root / "TEMP/route-invalid"
    monkeypatch.setattr(
        sys,
        "argv",
        ["chatgpt_review_pack.py", *argv_tail, "--out-dir", str(out)],
    )

    with pytest.raises(SystemExit, match=message):
        chatgpt_review_pack.main()
    assert not out.exists()


def test_route_missing_required_root_and_path_escape_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    _write_route_config(
        chatgpt_review_pack.ROUTES,
        required_glob="missing.txt",
        external_required=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--layers",
            "current_truth",
            "--dry-run",
        ],
    )
    with pytest.raises(SystemExit, match="required glob 缺件"):
        chatgpt_review_pack.main()

    _write_route_config(
        chatgpt_review_pack.ROUTES,
        required_glob="../outside.txt",
        external_required=False,
    )
    with pytest.raises(SystemExit, match="不得越界"):
        chatgpt_review_pack.main()


def test_route_external_secret_value_is_rejected_before_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    _write_route_config(chatgpt_review_pack.ROUTES)
    external = tmp_path / "advisor.md"
    external.write_text(
        'API_KEY="abcdefghijklmnop1234567890"',
        encoding="utf-8",
    )
    out = root / "TEMP/route-secret"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--external",
            f"advisor={external}",
            "--out-dir",
            str(out),
        ],
    )

    with pytest.raises(SystemExit, match="疑似真实密钥值"):
        chatgpt_review_pack.main()
    assert not out.exists()


def test_route_external_unsafe_zip_member_is_rejected_before_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    _write_route_config(chatgpt_review_pack.ROUTES)
    external = tmp_path / "bad\\member.md"
    external.write_text("external review", encoding="utf-8")
    out = root / "TEMP/route-unsafe-member"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--external",
            f"advisor={external}",
            "--out-dir",
            str(out),
        ],
    )

    with pytest.raises(SystemExit, match="ZIP 成员路径不安全"):
        chatgpt_review_pack.main()
    assert not out.exists()


def test_route_forbidden_lockbox_cannot_enter_pack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    lockbox = root / "question_reference_map.lockbox.json"
    lockbox.write_text('{"answer": "hidden"}', encoding="utf-8")
    _write_route_config(
        chatgpt_review_pack.ROUTES,
        required_glob=lockbox.name,
        external_required=False,
        forbidden_source_globs=["**/*.lockbox.json"],
    )
    out = root / "TEMP/route-lockbox"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--layers",
            "current_truth",
            "--out-dir",
            str(out),
        ],
    )

    with pytest.raises(SystemExit, match="禁止外发的金标／答案锁箱"):
        chatgpt_review_pack.main()
    assert not out.exists()


def test_route_root_exclude_removes_lockbox_before_forbidden_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    (root / "evidence").mkdir()
    (root / "evidence/public.json").write_text("{}", encoding="utf-8")
    (root / "evidence/private.lockbox.json").write_text(
        '{"answer": "hidden"}',
        encoding="utf-8",
    )
    _write_route_config(
        chatgpt_review_pack.ROUTES,
        required_glob="evidence/**",
        external_required=False,
        forbidden_source_globs=["**/*.lockbox.json"],
        root_exclude_globs=["evidence/*.lockbox.json"],
    )
    out = root / "TEMP/route-excluded-lockbox"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--layers",
            "current_truth",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    zip_path = next(out.glob("chatgpt_review_route_*.zip"))
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "01_current_truth/evidence/public.json" in names
    assert not any("lockbox" in name for name in names)


def test_route_redacts_local_absolute_paths_with_sha_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, _ = _configure_minimal_pack(monkeypatch, tmp_path)
    source = root / "source.txt"
    source.write_text(
        f"repo={root}/runs/demo\nhome={Path.home()}/Downloads/demo.zip\n",
        encoding="utf-8",
    )
    _write_route_config(
        chatgpt_review_pack.ROUTES,
        external_required=False,
        redact_local_absolute_paths=True,
    )
    out = root / "TEMP/route-redacted"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chatgpt_review_pack.py",
            "--route",
            "demo",
            "--layers",
            "current_truth",
            "--out-dir",
            str(out),
        ],
    )

    assert chatgpt_review_pack.main() == 0
    zip_path = next(out.glob("chatgpt_review_route_*.zip"))
    with zipfile.ZipFile(zip_path) as archive:
        payload = archive.read("01_current_truth/source.txt").decode("utf-8")
        redaction = json.loads(
            archive.read("_route/LOCAL_PATH_REDACTION.json")
        )
    assert str(root) not in payload
    assert str(Path.home()) not in payload
    assert "<repo-root>/runs/demo" in payload
    assert "<user-home>/Downloads/demo.zip" in payload
    assert redaction["result"] == "PASS"
    assert redaction["changed_member_count"] == 1
    row = redaction["changed_members"][0]
    assert row["original_sha256"] != row["sanitized_sha256"]
