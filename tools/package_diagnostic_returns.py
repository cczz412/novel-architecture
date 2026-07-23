#!/usr/bin/env python3
"""归档外部诊断回包，并生成只含 Markdown 的可审计 ZIP。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = (
    ROOT
    / "references/diagnostic-returns/Z66_中性原子事件请求诊断_三问法_20260720"
)
DEFAULT_SOURCES = (
    Path("/Users/a1234/Downloads/小说逐章证据_API高精度方案包"),
    Path("/Users/a1234/Downloads/LLM中性原子事件诊断包"),
    Path("/Users/a1234/Downloads/第3章LLM请求诊断_修正版与抽取结果"),
)
ZIP_NAME = "小说中性原子事件诊断_三问法_全MD_20260720.zip"
PACKAGE_ROOT = "小说中性原子事件诊断_三问法_全MD_20260720"
SKIPPED_NAMES = {".DS_Store"}
LANGUAGE_BY_SUFFIX = {
    ".txt": "text",
    ".json": "json",
    ".py": "python",
}


@dataclass(frozen=True)
class ConvertedFile:
    source_relative: str
    source_sha256: str
    source_bytes: int
    output_relative: str
    output_sha256: str
    output_bytes: int
    conversion: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def choose_fence(text: str) -> str:
    longest = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(4, longest + 1)


def converted_name(path: Path) -> str:
    if path.suffix.lower() == ".md":
        return path.name
    return f"{path.stem}.md"


def render_markdown(source: Path, source_root: Path) -> tuple[bytes, str]:
    suffix = source.suffix.lower()
    raw = source.read_bytes()
    if suffix == ".md":
        return raw, "Markdown原样保留"
    if suffix not in LANGUAGE_BY_SUFFIX:
        raise ValueError(f"没有转换规则：{source}")
    text = raw.decode("utf-8")
    fence = choose_fence(text)
    language = LANGUAGE_BY_SUFFIX[suffix]
    relative = source.relative_to(source_root).as_posix()
    rendered = (
        f"# 原文件：{source.name}\n\n"
        f"> 来源路径：`{relative}`  \n"
        f"> 转换说明：原内容未重排，放入 `{language}` 代码块；原始文件另存于同批归档。\n\n"
        f"{fence}{language}\n{text}"
    )
    if not text.endswith("\n"):
        rendered += "\n"
    rendered += f"{fence}\n\n来源：Codex\n"
    return rendered.encode("utf-8"), f"{suffix}→Markdown代码块"


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def build_readme(source_names: list[str], content_count: int) -> str:
    folder_lines = "\n".join(f"- `{name}/`" for name in source_names)
    return f"""# 小说中性原子事件诊断｜三问法全 Markdown 包

这三份文件夹处理的是同一个问题：检查现役中性原子事件请求为什么与人工金标差距大，并分别给出请求诊断、修正版请求体、抽取样张和 API 高精度方案。

## 本包目录

{folder_lines}

正文材料共 {content_count} 份，包内所有文件均为 `.md`。

## 转换口径

- 原 `.md`：字节原样保留，不清洗措辞和排版。
- 原 `.txt`：原文放进 `text` 代码块。
- 原 `.json`：原文放进 `json` 代码块，不重排字段。
- 原 `.py`：原文放进 `python` 代码块。
- `.DS_Store`：macOS 目录缓存，不是材料正文；原始归档保留，MD 包排除。

## 使用边界

这批只作外部诊断候选材料，不改现役默认链、金标、分类规则或 outbox。三种问法的结果可以并排调查，但不能直接当最终改法。

来源：Codex
"""


def build_manifest(rows: list[ConvertedFile], skipped: list[str]) -> str:
    lines = [
        "# 文件清单与校验",
        "",
        f"内容文件：{len(rows)}；排除的系统缓存：{len(skipped)}。",
        "",
        "| 原文件 | 转换 | 原SHA-256 | MD文件 | MD SHA-256 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{md_escape(row.source_relative)}`",
                    md_escape(row.conversion),
                    f"`{row.source_sha256}`",
                    f"`{md_escape(row.output_relative)}`",
                    f"`{row.output_sha256}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "## 排除项", ""])
    if skipped:
        lines.extend(f"- `{item}`：系统缓存，不是正文材料。" for item in skipped)
    else:
        lines.append("- 无。")
    lines.extend(["", "来源：Codex", ""])
    return "\n".join(lines)


def build_receipt(
    target: Path,
    rows: list[ConvertedFile],
    skipped: list[str],
    zip_path: Path,
    zip_members: list[str],
) -> str:
    raw_files = sum(1 for path in (target / "原始回包").rglob("*") if path.is_file())
    return f"""# Z66外部诊断三问法｜归档与打包回执

- 原始文件夹：3个，已按原目录名复制进 `原始回包/`。
- 原始文件：{raw_files}份，其中正文材料{len(rows)}份、系统缓存{len(skipped)}份。
- 全MD版正文：{len(rows)}份；另含 `README.md` 与 `MANIFEST.md`。
- ZIP成员：{len(zip_members)}份，全部为 `.md`。
- ZIP：`{ZIP_NAME}`
- ZIP SHA-256：`{sha256_file(zip_path)}`
- ZIP CRC：`testzip() = None`
- 原下载目录：未删、未移动、未改写。

这批只登记为第66道外部诊断候选回包，不写入现役链。

来源：Codex
"""


def package(sources: tuple[Path, ...], target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"目标已存在，拒绝覆盖：{target}")
    for source in sources:
        if not source.is_dir():
            raise FileNotFoundError(source)
    if len({source.name for source in sources}) != len(sources):
        raise ValueError("源文件夹重名")

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".z66-diagnostic-pack-", dir=target.parent) as tmp:
        stage = Path(tmp) / target.name
        raw_root = stage / "原始回包"
        md_root = stage / "全MD版" / PACKAGE_ROOT
        raw_root.mkdir(parents=True)
        md_root.mkdir(parents=True)

        rows: list[ConvertedFile] = []
        skipped: list[str] = []
        for source in sources:
            raw_destination = raw_root / source.name
            shutil.copytree(source, raw_destination, copy_function=shutil.copy2)
            md_source_root = md_root / source.name
            for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
                relative = file_path.relative_to(source)
                source_relative = f"{source.name}/{relative.as_posix()}"
                if file_path.name in SKIPPED_NAMES:
                    skipped.append(source_relative)
                    continue
                output_relative_path = relative.with_name(converted_name(relative))
                output_path = md_source_root / output_relative_path
                if output_path.exists():
                    raise FileExistsError(f"转换后文件名冲突：{output_path}")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_bytes, conversion = render_markdown(file_path, source)
                output_path.write_bytes(output_bytes)
                rows.append(
                    ConvertedFile(
                        source_relative=source_relative,
                        source_sha256=sha256_file(file_path),
                        source_bytes=file_path.stat().st_size,
                        output_relative=f"{source.name}/{output_relative_path.as_posix()}",
                        output_sha256=sha256_bytes(output_bytes),
                        output_bytes=len(output_bytes),
                        conversion=conversion,
                    )
                )

        readme = build_readme([source.name for source in sources], len(rows))
        (md_root / "README.md").write_text(readme, encoding="utf-8")
        manifest = build_manifest(rows, skipped)
        (md_root / "MANIFEST.md").write_text(manifest, encoding="utf-8")

        zip_path = stage / ZIP_NAME
        md_files = sorted(path for path in md_root.rglob("*") if path.is_file())
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in md_files:
                archive.write(file_path, file_path.relative_to(md_root.parent).as_posix())

        with zipfile.ZipFile(zip_path) as archive:
            zip_members = archive.namelist()
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC 校验失败")
            if any(not name.endswith(".md") for name in zip_members):
                raise ValueError("ZIP 内出现非 Markdown 文件")
            if len(zip_members) != len(rows) + 2:
                raise ValueError("ZIP 成员数与转换清单不一致")
            if any(not (info.flag_bits & 0x800) for info in archive.infolist()):
                raise ValueError("ZIP 中文文件名缺 UTF-8 标志")

        receipt = build_receipt(stage, rows, skipped, zip_path, zip_members)
        (stage / "归档与打包回执.md").write_text(receipt, encoding="utf-8")
        stage.rename(target)


def verify(sources: tuple[Path, ...], target: Path) -> dict[str, object]:
    raw_root = target / "原始回包"
    md_root = target / "全MD版" / PACKAGE_ROOT
    zip_path = target / ZIP_NAME
    if not raw_root.is_dir() or not md_root.is_dir() or not zip_path.is_file():
        raise FileNotFoundError("归档目录、全MD目录或ZIP缺失")

    raw_checked = 0
    md_checked = 0
    skipped: list[str] = []
    expected_md_paths: set[str] = {"README.md", "MANIFEST.md"}
    for source in sources:
        copied_root = raw_root / source.name
        source_files = sorted(path for path in source.rglob("*") if path.is_file())
        copied_files = sorted(path for path in copied_root.rglob("*") if path.is_file())
        source_relatives = [path.relative_to(source) for path in source_files]
        copied_relatives = [path.relative_to(copied_root) for path in copied_files]
        if source_relatives != copied_relatives:
            raise ValueError(f"原始副本文件清单不一致：{source.name}")
        for source_file, relative in zip(source_files, source_relatives, strict=True):
            copied_file = copied_root / relative
            if sha256_file(source_file) != sha256_file(copied_file):
                raise ValueError(f"原始副本SHA不一致：{source.name}/{relative}")
            raw_checked += 1
            if source_file.name in SKIPPED_NAMES:
                skipped.append(f"{source.name}/{relative.as_posix()}")
                continue
            output_relative = relative.with_name(converted_name(relative))
            output_path = md_root / source.name / output_relative
            expected_bytes, _ = render_markdown(source_file, source)
            if output_path.read_bytes() != expected_bytes:
                raise ValueError(f"Markdown转换不一致：{source.name}/{relative}")
            expected_md_paths.add(f"{source.name}/{output_relative.as_posix()}")
            md_checked += 1

    actual_md_paths = {
        path.relative_to(md_root).as_posix()
        for path in md_root.rglob("*")
        if path.is_file()
    }
    if actual_md_paths != expected_md_paths:
        raise ValueError("全MD目录文件清单不一致")
    if any(Path(name).suffix.lower() != ".md" for name in actual_md_paths):
        raise ValueError("全MD目录出现非Markdown文件")

    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC校验失败")
        zip_names = archive.namelist()
        expected_zip_names = sorted(f"{PACKAGE_ROOT}/{name}" for name in actual_md_paths)
        if sorted(zip_names) != expected_zip_names:
            raise ValueError("ZIP成员清单与全MD目录不一致")
        for name in zip_names:
            relative = Path(name).relative_to(PACKAGE_ROOT)
            if archive.read(name) != (md_root / relative).read_bytes():
                raise ValueError(f"ZIP成员内容不一致：{name}")
        if any(not (info.flag_bits & 0x800) for info in archive.infolist()):
            raise ValueError("ZIP成员名缺UTF-8标志")

    receipt_text = (target / "归档与打包回执.md").read_text(encoding="utf-8")
    match = re.search(r"ZIP SHA-256：`([0-9a-f]{64})`", receipt_text)
    if not match or match.group(1) != sha256_file(zip_path):
        raise ValueError("回执中的ZIP SHA与现物不一致")
    return {
        "status": "pass",
        "source_folders": len(sources),
        "raw_files_checked": raw_checked,
        "content_files_converted": md_checked,
        "skipped_system_files": skipped,
        "markdown_files_in_zip": len(actual_md_paths),
        "zip_members": len(zip_names),
        "zip_testzip": None,
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--source", action="append", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sources = tuple(args.source) if args.source else DEFAULT_SOURCES
    if args.check:
        print(json.dumps(verify(sources, args.target), ensure_ascii=False, sort_keys=True))
    else:
        package(sources, args.target)
        print(args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
