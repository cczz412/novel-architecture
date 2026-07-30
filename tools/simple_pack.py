#!/usr/bin/env python3
"""清版外发包：Prompt 文件 + 可回读校验的材料 ZIP。"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from pipeline_common import artifacts  # noqa: E402


CONTROLLED_TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
}
CONTROLLED_FORBIDDEN_MEMBER_PATTERNS = {
    "nested_zip": re.compile(r"\.zip$", re.I),
    "reserved_zip_member": re.compile(
        r"^(?:MANIFEST\.json|SHA256SUMS)$",
        re.I,
    ),
    "lockbox": re.compile(r"lockbox", re.I),
    "formal_gold": re.compile(
        r"(?:^|[_-])(?:question_)?gold(?:[_\.-]|$)",
        re.I,
    ),
    "raw_candidate_projection": re.compile(
        r"(?:raw|structure)_candidate_projection"
        r"|candidate_structure_projection",
        re.I,
    ),
    "chapter_body": re.compile(
        r"chapter[_-]?body|novel[_-]?body|正文",
        re.I,
    ),
}
CONTROLLED_SECRET_PATTERNS = {
    "bearer_token": re.compile(
        rb"Bearer\s+[A-Za-z0-9._~+/=-]{12,}",
        re.I,
    ),
    "sk_token": re.compile(rb"\bsk-[A-Za-z0-9_-]{12,}\b"),
    "api_key_assignment": re.compile(
        rb"(?:API[_-]?KEY|ACCESS[_-]?TOKEN|SECRET[_-]?KEY)"
        rb"[\"']?\s*[=:]\s*[\"']?[A-Za-z0-9._~+/=-]{12,}[\"']?",
        re.I,
    ),
    "private_key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
CONTROLLED_ABSOLUTE_PATH_PATTERNS = {
    "mac_user_path": re.compile(rb"/Users/[^\s\"']+"),
    "linux_home_path": re.compile(rb"/home/[^\s\"']+"),
    "mac_temporary_path": re.compile(rb"/var/folders/[^\s\"']+"),
    "windows_drive_path": re.compile(rb"\b[A-Za-z]:\\[^\r\n\"']+"),
}


def _collect_input_files(
    files: list[Path],
    *,
    source_dir: Path | None,
) -> list[Path]:
    if source_dir is not None and files:
        raise SystemExit("受控材料目录和位置文件列表只能二选一")
    if source_dir is None:
        if not files:
            raise SystemExit("至少提供一个材料文件，或使用 --source-dir")
        return files

    if source_dir.is_symlink():
        raise SystemExit(f"受控材料目录无效：{source_dir}")
    directory = source_dir.resolve()
    if not directory.is_dir():
        raise SystemExit(f"受控材料目录无效：{source_dir}")
    entries = sorted(directory.iterdir(), key=lambda path: path.name)
    if not entries:
        raise SystemExit(f"受控材料目录为空：{source_dir}")
    invalid = [
        entry.name for entry in entries if entry.is_symlink() or not entry.is_file()
    ]
    if invalid:
        raise SystemExit(
            "受控材料目录必须平铺且只含普通文件："
            + json.dumps(invalid, ensure_ascii=False)
        )
    return entries


def _scan_controlled_payloads(
    payloads: dict[str, bytes],
    *,
    max_text_line_chars: int,
) -> dict[str, Any]:
    if max_text_line_chars < 80:
        raise SystemExit("--max-text-line-chars 不能小于 80")

    unsupported_members: list[str] = []
    forbidden_name_hits: list[dict[str, str]] = []
    secret_hits: list[dict[str, str]] = []
    absolute_path_hits: list[dict[str, str]] = []
    invalid_utf8_members: list[str] = []
    invalid_json_members: list[dict[str, str]] = []
    long_line_hits: list[dict[str, int | str]] = []
    max_observed_line_chars = 0

    for member, data in sorted(payloads.items()):
        suffix = Path(member).suffix.lower()
        if suffix not in CONTROLLED_TEXT_SUFFIXES:
            unsupported_members.append(member)
        for label, pattern in CONTROLLED_FORBIDDEN_MEMBER_PATTERNS.items():
            if pattern.search(member):
                forbidden_name_hits.append({"member": member, "reason": label})
        for label, pattern in CONTROLLED_SECRET_PATTERNS.items():
            if pattern.search(data):
                secret_hits.append({"member": member, "pattern": label})
        for label, pattern in CONTROLLED_ABSOLUTE_PATH_PATTERNS.items():
            if pattern.search(data):
                absolute_path_hits.append({"member": member, "pattern": label})
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            invalid_utf8_members.append(member)
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            line_chars = len(line)
            max_observed_line_chars = max(
                max_observed_line_chars,
                line_chars,
            )
            if line_chars > max_text_line_chars:
                long_line_hits.append(
                    {
                        "member": member,
                        "line": line_number,
                        "chars": line_chars,
                    }
                )
        if suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                invalid_json_members.append(
                    {
                        "member": member,
                        "line": exc.lineno,
                        "column": exc.colno,
                    }
                )

    hit_count = sum(
        len(rows)
        for rows in (
            unsupported_members,
            forbidden_name_hits,
            secret_hits,
            absolute_path_hits,
            invalid_utf8_members,
            invalid_json_members,
            long_line_hits,
        )
    )
    return {
        "schema_version": "controlled-review-preflight-v1",
        "result": "PASS" if hit_count == 0 else "FAIL",
        "scanned_members": len(payloads),
        "hit_count": hit_count,
        "secret_scan": {
            "result": "PASS" if not secret_hits else "FAIL",
            "hit_count": len(secret_hits),
            "hits": secret_hits,
        },
        "forbidden_payload_scan": {
            "result": (
                "PASS"
                if not (
                    unsupported_members
                    or forbidden_name_hits
                    or absolute_path_hits
                    or invalid_utf8_members
                )
                else "FAIL"
            ),
            "unsupported_members": unsupported_members,
            "forbidden_name_hits": forbidden_name_hits,
            "absolute_path_hits": absolute_path_hits,
            "invalid_utf8_members": invalid_utf8_members,
        },
        "json_validation": {
            "result": "PASS" if not invalid_json_members else "FAIL",
            "invalid_members": invalid_json_members,
        },
        "text_scan": {
            "result": "PASS" if not long_line_hits else "FAIL",
            "max_allowed_line_chars": max_text_line_chars,
            "max_observed_line_chars": max_observed_line_chars,
            "long_line_hits": long_line_hits,
        },
    }


def _preflight(
    prompt: Path,
    files: list[Path],
    *,
    zip_name: str,
    controlled_review: bool = False,
    max_text_line_chars: int = 500,
) -> tuple[bytes, dict[str, bytes], dict[str, Any] | None]:
    if not prompt.is_file() or (controlled_review and prompt.is_symlink()):
        raise SystemExit(f"Prompt 不是文件：{prompt}")
    if Path(zip_name).name != zip_name or not zip_name.endswith(".zip"):
        raise SystemExit(f"ZIP 名称必须是单个 .zip 文件名：{zip_name}")

    prompt_bytes = prompt.read_bytes()
    payloads: dict[str, bytes] = {}
    for raw in files:
        if controlled_review and raw.is_symlink():
            raise SystemExit(f"受控材料不能使用符号链接：{raw}")
        path = raw.resolve()
        if not path.is_file():
            raise SystemExit(f"不是文件：{raw}")
        member = path.name
        if member in payloads:
            raise SystemExit(f"ZIP 成员重名，拒绝静默覆盖：{member}")
        payloads[member] = path.read_bytes()

    controlled_preflight = None
    if controlled_review:
        controlled_preflight = _scan_controlled_payloads(
            {
                **payloads,
                "__PROMPT__.md": prompt_bytes,
            },
            max_text_line_chars=max_text_line_chars,
        )
        if controlled_preflight["result"] != "PASS":
            raise SystemExit(
                "ABORT 受控外发预检失败：\n"
                + json.dumps(
                    controlled_preflight,
                    ensure_ascii=False,
                    indent=2,
                )
            )
    return prompt_bytes, payloads, controlled_preflight


def _build_into(
    stage: Path,
    *,
    prompt_bytes: bytes,
    payloads: dict[str, bytes],
    zip_name: str,
    controlled_preflight: dict[str, Any] | None = None,
    expected_model_family: str = "GPT-5.6 Sol",
    expected_model_variant: str = "Pro",
) -> dict[str, object]:
    upload = stage / "upload"
    upload.mkdir(parents=True, exist_ok=True)
    prompt_out = stage / "00_发给外部的Prompt.md"
    prompt_out.write_bytes(prompt_bytes)
    zip_path = upload / zip_name
    metadata = {"package_kind": "simple-pack-v2"}
    if controlled_preflight:
        metadata = {
            "package_kind": "controlled-review-simple-pack-v1",
            "expected_model_family": expected_model_family,
            "expected_model_variant": expected_model_variant,
        }
    integrity = artifacts.write_verified_zip(
        zip_path,
        payloads,
        metadata=metadata,
    )
    send_checklist = None
    send_checklist_sha256 = None
    if controlled_preflight:
        send_checklist = {
            "schema_version": "chatgpt-review-send-checklist-v1",
            "package": {
                "attachment_count": 1,
                "attachment_filename": zip_name,
                "attachment_sha256": integrity["zip_sha256"],
                "prompt_filename": prompt_out.name,
                "prompt_sha256": artifacts.sha256_bytes(prompt_bytes),
            },
            "model": {
                "expected_family": expected_model_family,
                "expected_variant": expected_model_variant,
                "require_visible_family_evidence": True,
                "require_checked_variant_evidence": True,
            },
            "pre_send_checks": [
                "模型家族与精确档位页面证据一致",
                "页面恰好出现一个冻结ZIP附件",
                "Prompt开头、核心问题与回包合同可见",
                "发送按钮可用",
            ],
            "post_send_checks": [
                "URL变为https://chatgpt.com/c/...",
                "用户消息下仍显示冻结ZIP",
                "用户Prompt已进入对话",
                "ChatGPT说与思考中或正式回答可见",
            ],
            "transport_states": ["NOT_SENT", "SENT", "UNKNOWN"],
            "response_rules": {
                "click_immediate_answer": False,
                "click_regenerate": False,
                "resend_after_unknown": False,
                "recover_only_downloadable_zip": True,
            },
        }
        checklist_bytes = (
            json.dumps(
                send_checklist,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        (stage / "SEND_CHECKLIST.json").write_bytes(checklist_bytes)
        send_checklist_sha256 = artifacts.sha256_bytes(checklist_bytes)

    receipt: dict[str, object] = {
        "schema_version": "simple-pack-receipt-v2",
        "prompt": {
            "path": prompt_out.name,
            "bytes": len(prompt_bytes),
            "sha256": artifacts.sha256_bytes(prompt_bytes),
        },
        "zip": {
            "path": f"upload/{zip_name}",
            "bytes": integrity["zip_bytes"],
            "sha256": integrity["zip_sha256"],
        },
        "payload_file_count": len(payloads),
        "integrity": integrity,
    }
    if controlled_preflight:
        receipt.update(
            {
                "controlled_review": controlled_preflight,
                "secret_scan": controlled_preflight["secret_scan"],
                "forbidden_payload_scan": controlled_preflight[
                    "forbidden_payload_scan"
                ],
                "json_validation": controlled_preflight["json_validation"],
                "text_scan": controlled_preflight["text_scan"],
                "send_contract": {
                    "expected_model_family": expected_model_family,
                    "expected_model_variant": expected_model_variant,
                },
                "send_checklist": {
                    "path": "SEND_CHECKLIST.json",
                    "sha256": send_checklist_sha256,
                },
            }
        )
    (stage / "PACKAGE_RECEIPT.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> int:
    p = argparse.ArgumentParser(description="小说架构 · 清版打包（Prompt + ZIP）")
    p.add_argument("--prompt", required=True, type=Path, help="要外发粘贴的 Prompt .md")
    p.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="输出目录（会写 Prompt 副本 + upload/*.zip）",
    )
    p.add_argument("--zip-name", default="arch_pack.zip", help="ZIP 文件名")
    p.add_argument(
        "--source-dir",
        type=Path,
        help="平铺材料目录；与位置文件列表二选一",
    )
    p.add_argument(
        "--controlled-review",
        action="store_true",
        help="启用外审卫生门并生成浏览器发送清单",
    )
    p.add_argument(
        "--expected-model-family",
        default="GPT-5.6 Sol",
        help="浏览器发送时必须逐字回读的模型家族",
    )
    p.add_argument(
        "--expected-model-variant",
        default="Pro",
        help="浏览器发送时必须确认已勾选的精确档位",
    )
    p.add_argument(
        "--max-text-line-chars",
        type=int,
        default=500,
        help="受控摘要材料单行字符上限，默认 500",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只预检输入和成员名，不创建目录、不写文件",
    )
    p.add_argument("files", nargs="*", type=Path, help="打进 ZIP 的章节或材料文件")
    args = p.parse_args()

    if args.controlled_review and (
        not args.expected_model_family.strip()
        or not args.expected_model_variant.strip()
    ):
        raise SystemExit("受控模式的模型家族和精确档位不能为空")

    out = args.out_dir
    input_files = _collect_input_files(
        args.files,
        source_dir=args.source_dir,
    )
    prompt_bytes, payloads, controlled_preflight = _preflight(
        args.prompt,
        input_files,
        zip_name=args.zip_name,
        controlled_review=args.controlled_review,
        max_text_line_chars=args.max_text_line_chars,
    )
    if out.exists():
        raise SystemExit(f"输出目录已存在，拒绝覆盖：{out}")
    if args.dry_run:
        total = sum(len(data) for data in payloads.values())
        print(f"dry-run files={len(payloads)} bytes={total} out={out}（零写入）")
        if controlled_preflight:
            print(
                "controlled-review=PASS "
                f"model={args.expected_model_family}/{args.expected_model_variant}"
            )
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            dir=out.parent,
            prefix=f".{out.name}.",
        )
    )
    try:
        receipt = _build_into(
            stage,
            prompt_bytes=prompt_bytes,
            payloads=payloads,
            zip_name=args.zip_name,
            controlled_preflight=controlled_preflight,
            expected_model_family=args.expected_model_family,
            expected_model_variant=args.expected_model_variant,
        )
        os.replace(stage, out)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    print("交件双件：")
    print(f"  Prompt: {out / '00_发给外部的Prompt.md'}")
    print(f"  ZIP:    {out / 'upload' / args.zip_name}")
    print(f"  验收票: {out / 'PACKAGE_RECEIPT.json'}")
    if controlled_preflight:
        print(f"  发送清单: {out / 'SEND_CHECKLIST.json'}")
    print(f"  文件数: {receipt['payload_file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
