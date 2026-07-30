from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from tools.pipeline_common import artifacts


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/simple_pack.py"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_dry_run_preflights_without_writing(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    payload = tmp_path / "chapter.txt"
    out = tmp_path / "out"
    prompt.write_text("提示", encoding="utf-8")
    payload.write_text("正文", encoding="utf-8")

    completed = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(out),
        "--dry-run",
        str(payload),
    )

    assert completed.returncode == 0, completed.stderr
    assert "零写入" in completed.stdout
    assert not out.exists()


def test_simple_pack_writes_verified_zip_and_receipt(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    payload = tmp_path / "chapter.txt"
    out = tmp_path / "out"
    prompt.write_text("提示", encoding="utf-8")
    payload.write_text("正文", encoding="utf-8")

    completed = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(out),
        str(payload),
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads((out / "PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    zip_path = out / "upload/arch_pack.zip"
    assert receipt["integrity"]["passed"] is True
    assert receipt["zip"]["sha256"] == artifacts.sha256_file(zip_path)
    assert (out / "00_发给外部的Prompt.md").read_bytes() == prompt.read_bytes()
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert {"chapter.txt", "MANIFEST.json", "SHA256SUMS"} == set(archive.namelist())


def test_simple_pack_rejects_duplicate_member_names_without_output(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    one = tmp_path / "one"
    two = tmp_path / "two"
    out = tmp_path / "out"
    prompt.write_text("提示", encoding="utf-8")
    one.mkdir()
    two.mkdir()
    (one / "same.txt").write_text("甲", encoding="utf-8")
    (two / "same.txt").write_text("乙", encoding="utf-8")

    completed = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(out),
        str(one / "same.txt"),
        str(two / "same.txt"),
    )

    assert completed.returncode != 0
    assert "成员重名" in completed.stderr
    assert not out.exists()


def test_controlled_review_builds_flat_zip_receipt_and_send_checklist(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    source = tmp_path / "source"
    out = tmp_path / "out"
    source.mkdir()
    prompt.write_text("请只依据附件回答，并返回一个 ZIP。", encoding="utf-8")
    (source / "00_READ_ME.md").write_text("这是摘要材料。", encoding="utf-8")
    (source / "01_EVIDENCE.json").write_text(
        json.dumps({"result": "candidate_only"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    completed = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(out),
        "--source-dir",
        str(source),
        "--controlled-review",
        "--zip-name",
        "review.zip",
    )

    assert completed.returncode == 0, completed.stderr
    receipt = json.loads((out / "PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    checklist_path = out / "SEND_CHECKLIST.json"
    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    zip_path = out / "upload/review.zip"
    assert receipt["controlled_review"]["result"] == "PASS"
    assert receipt["secret_scan"]["hit_count"] == 0
    assert receipt["forbidden_payload_scan"]["result"] == "PASS"
    assert receipt["json_validation"]["result"] == "PASS"
    assert receipt["text_scan"]["result"] == "PASS"
    assert receipt["send_checklist"]["sha256"] == artifacts.sha256_file(checklist_path)
    assert checklist["model"] == {
        "expected_family": "GPT-5.6 Sol",
        "expected_variant": "Pro",
        "require_visible_family_evidence": True,
        "require_checked_variant_evidence": True,
    }
    assert checklist["package"]["attachment_count"] == 1
    assert checklist["package"]["attachment_sha256"] == artifacts.sha256_file(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert {
            "00_READ_ME.md",
            "01_EVIDENCE.json",
            "MANIFEST.json",
            "SHA256SUMS",
        } == set(archive.namelist())
        manifest = json.loads(archive.read("MANIFEST.json"))
    assert manifest["metadata"] == {
        "expected_model_family": "GPT-5.6 Sol",
        "expected_model_variant": "Pro",
        "package_kind": "controlled-review-simple-pack-v1",
    }


def test_controlled_review_dry_run_is_zero_write(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    source = tmp_path / "source"
    out = tmp_path / "out"
    source.mkdir()
    prompt.write_text("提示", encoding="utf-8")
    (source / "evidence.md").write_text("候选证据", encoding="utf-8")

    completed = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(out),
        "--source-dir",
        str(source),
        "--controlled-review",
        "--dry-run",
        "--expected-model-family",
        "GPT-5.6 Sol",
        "--expected-model-variant",
        "Pro",
    )

    assert completed.returncode == 0, completed.stderr
    assert "controlled-review=PASS model=GPT-5.6 Sol/Pro" in completed.stdout
    assert not out.exists()


def test_controlled_review_rejects_symlink_file_and_directory(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    real_file = tmp_path / "evidence.md"
    linked_file = tmp_path / "linked.md"
    real_source = tmp_path / "real-source"
    linked_source = tmp_path / "linked-source"
    prompt.write_text("提示", encoding="utf-8")
    real_file.write_text("材料", encoding="utf-8")
    linked_file.symlink_to(real_file)
    real_source.mkdir()
    (real_source / "evidence.md").write_text("材料", encoding="utf-8")
    linked_source.symlink_to(real_source, target_is_directory=True)

    linked_file_result = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "file-out"),
        "--controlled-review",
        str(linked_file),
    )
    linked_dir_result = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "dir-out"),
        "--source-dir",
        str(linked_source),
        "--controlled-review",
    )

    assert linked_file_result.returncode != 0
    assert "不能使用符号链接" in linked_file_result.stderr
    assert linked_dir_result.returncode != 0
    assert "受控材料目录无效" in linked_dir_result.stderr
    assert not (tmp_path / "file-out").exists()
    assert not (tmp_path / "dir-out").exists()


def test_controlled_review_rejects_symlink_prompt(tmp_path: Path) -> None:
    real_prompt = tmp_path / "prompt.md"
    linked_prompt = tmp_path / "linked-prompt.md"
    payload = tmp_path / "evidence.md"
    out = tmp_path / "out"
    real_prompt.write_text("提示", encoding="utf-8")
    linked_prompt.symlink_to(real_prompt)
    payload.write_text("材料", encoding="utf-8")

    completed = _run(
        "--prompt",
        str(linked_prompt),
        "--out-dir",
        str(out),
        "--controlled-review",
        str(payload),
    )

    assert completed.returncode != 0
    assert "Prompt 不是文件" in completed.stderr
    assert not out.exists()


def test_source_dir_rejects_empty_nested_and_mixed_inputs(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("提示", encoding="utf-8")
    empty_source = tmp_path / "empty"
    nested_source = tmp_path / "nested"
    empty_source.mkdir()
    nested_source.mkdir()
    (nested_source / "subdir").mkdir()
    payload = tmp_path / "evidence.md"
    payload.write_text("材料", encoding="utf-8")

    empty_result = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "empty-out"),
        "--source-dir",
        str(empty_source),
        "--controlled-review",
    )
    nested_result = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "nested-out"),
        "--source-dir",
        str(nested_source),
        "--controlled-review",
    )
    mixed_result = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "mixed-out"),
        "--source-dir",
        str(empty_source),
        "--controlled-review",
        str(payload),
    )

    assert empty_result.returncode != 0
    assert "目录为空" in empty_result.stderr
    assert nested_result.returncode != 0
    assert "必须平铺" in nested_result.stderr
    assert mixed_result.returncode != 0
    assert "只能二选一" in mixed_result.stderr


def test_controlled_review_rejects_forbidden_names_without_output(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("提示", encoding="utf-8")
    cases = [
        ("nested.zip", b"zip"),
        ("MANIFEST.json", b"{}"),
        ("SHA256SUMS", b"sha"),
        ("LOCKBOX.md", "锁箱".encode()),
        ("question_gold.json", b"{}"),
        ("raw_candidate_projection.json", b"{}"),
        ("chapter_body.txt", "正文".encode()),
    ]

    for index, (name, data) in enumerate(cases):
        payload = tmp_path / name
        out = tmp_path / f"out-{index}"
        payload.write_bytes(data)
        completed = _run(
            "--prompt",
            str(prompt),
            "--out-dir",
            str(out),
            "--controlled-review",
            str(payload),
        )
        assert completed.returncode != 0, name
        assert "受控外发预检失败" in completed.stderr
        assert not out.exists()


def test_controlled_review_rejects_secrets_and_absolute_paths(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("提示", encoding="utf-8")
    cases = [
        "Authorization: Bearer abcdefghijklmnop",
        "token=sk-abcdefghijklmnop",
        "API_KEY='abcdefghijklmnop'",
        "API_KEY=abcdefghijklmnop",
        "X-API-Key: abcdefghijklmnop",
        "-----BEGIN PRIVATE KEY-----",
        "/Users/example/private/file.txt",
        "/home/example/private/file.txt",
        "/var/folders/ab/private/file.txt",
        r"C:\Users\example\private.txt",
    ]

    for index, body in enumerate(cases):
        payload = tmp_path / f"evidence-{index}.md"
        out = tmp_path / f"out-{index}"
        payload.write_text(body, encoding="utf-8")
        completed = _run(
            "--prompt",
            str(prompt),
            "--out-dir",
            str(out),
            "--controlled-review",
            str(payload),
        )
        assert completed.returncode != 0, body
        assert "受控外发预检失败" in completed.stderr
        assert not out.exists()


def test_controlled_review_scans_prompt_and_rejects_bad_text_inputs(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "evidence.md"
    payload.write_text("材料", encoding="utf-8")
    secret_prompt = tmp_path / "secret-prompt.md"
    secret_prompt.write_text("Bearer abcdefghijklmnop", encoding="utf-8")
    invalid_utf8 = tmp_path / "invalid.md"
    invalid_utf8.write_bytes(b"\xff\xfe")
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text('{"broken":', encoding="utf-8")
    long_line = tmp_path / "long.md"
    long_line.write_text("甲" * 81, encoding="utf-8")
    plain_prompt = tmp_path / "prompt.md"
    plain_prompt.write_text("提示", encoding="utf-8")
    cases = [
        (secret_prompt, payload, []),
        (plain_prompt, invalid_utf8, []),
        (plain_prompt, invalid_json, []),
        (plain_prompt, long_line, ["--max-text-line-chars", "80"]),
    ]

    for index, (prompt, material, extra) in enumerate(cases):
        out = tmp_path / f"out-{index}"
        completed = _run(
            "--prompt",
            str(prompt),
            "--out-dir",
            str(out),
            "--controlled-review",
            *extra,
            str(material),
        )
        assert completed.returncode != 0
        assert "受控外发预检失败" in completed.stderr
        assert not out.exists()


def test_controlled_review_rejects_unsupported_suffix_and_low_line_limit(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    binary = tmp_path / "evidence.bin"
    prompt.write_text("提示", encoding="utf-8")
    binary.write_bytes(b"plain bytes")

    unsupported = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "unsupported-out"),
        "--controlled-review",
        str(binary),
    )
    low_limit = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "low-limit-out"),
        "--controlled-review",
        "--max-text-line-chars",
        "79",
        str(binary),
    )

    assert unsupported.returncode != 0
    assert "受控外发预检失败" in unsupported.stderr
    assert low_limit.returncode != 0
    assert "不能小于 80" in low_limit.stderr
    assert not (tmp_path / "unsupported-out").exists()
    assert not (tmp_path / "low-limit-out").exists()


def test_controlled_review_requires_nonempty_model_contract(
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    payload = tmp_path / "evidence.md"
    prompt.write_text("提示", encoding="utf-8")
    payload.write_text("材料", encoding="utf-8")

    completed = _run(
        "--prompt",
        str(prompt),
        "--out-dir",
        str(tmp_path / "out"),
        "--controlled-review",
        "--expected-model-family",
        " ",
        str(payload),
    )

    assert completed.returncode != 0
    assert "模型家族和精确档位不能为空" in completed.stderr
    assert not (tmp_path / "out").exists()
