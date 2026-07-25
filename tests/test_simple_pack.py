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
    receipt = json.loads(
        (out / "PACKAGE_RECEIPT.json").read_text(encoding="utf-8")
    )
    zip_path = out / "upload/arch_pack.zip"
    assert receipt["integrity"]["passed"] is True
    assert receipt["zip"]["sha256"] == artifacts.sha256_file(zip_path)
    assert (out / "00_发给外部的Prompt.md").read_bytes() == prompt.read_bytes()
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert {"chapter.txt", "MANIFEST.json", "SHA256SUMS"} == set(
            archive.namelist()
        )


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
