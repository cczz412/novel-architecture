# 执行身份：Codex
"""Read only explicitly addressed source members from an input archive."""
import hashlib
import json
import re
import zipfile
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(value, dict):
        value = {"data": value}
    path.write_text(json.dumps({"execution_identity": "Codex", **value},
                              ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def chapter_range(value):
    match = re.fullmatch(r"(\d+)-(\d+)", value)
    if not match:
        raise ValueError("章节范围须用起止数字")
    lo, hi = (int(x) for x in match.groups())
    if lo < 1 or hi < lo or hi - lo > 99:
        raise ValueError("章节范围无效")
    return [str(n).zfill(2) for n in range(lo, hi + 1)]


def read_sources(archive, book_id, chapters):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", book_id):
        raise ValueError("书号含不允许的路径字符")
    result = []
    with zipfile.ZipFile(archive) as package:
        for chapter in chapters:
            member = "books/" + book_id + "/sources/" + chapter + "_paragraphs.json"
            data = json.loads(package.read(member))
            paragraphs = data.get("paragraphs") if isinstance(data, dict) else data
            if not isinstance(paragraphs, list):
                raise ValueError("正文段落不是数组")
            # Grok Bot 作业外 v111（外部审查⑦）：书号、章号与输入一致性硬校验；带了就必须对得上。
            prefix = book_id + ":ch" + chapter + ":"
            if isinstance(data, dict):
                if "source_key" in data and data["source_key"] != book_id + ":ch" + chapter:
                    raise ValueError("正文来源书号或章号与请求不一致")
                if "original_sha256" in data and hashlib.sha256(str(data.get("text", "")).encode()).hexdigest() != data["original_sha256"]:
                    raise ValueError("正文全文与登记指纹不一致")
            cleaned = []
            seen = set()
            for index, row in enumerate(paragraphs, 1):
                if not isinstance(row, dict):
                    raise ValueError("正文段落须为对象")
                full = str(row.get("paragraph_id", ""))
                short = full.rsplit(":", 1)[-1] if full else "p" + str(index).zfill(3)
                if not re.fullmatch(r"p\d+", short) or short in seen:
                    raise ValueError("正文段号无效或重复")
                if ":" in full and full != prefix + short:
                    raise ValueError("段号所属书号或章号与请求不一致：" + full)
                if "paragraph_number" in row and row["paragraph_number"] != index:
                    raise ValueError("段序号与位置不一致：" + full)
                if isinstance(data, dict) and isinstance(data.get("text"), str) and isinstance(row.get("start"), int) and isinstance(row.get("end"), int) \
                        and data["text"][row["start"]:row["end"]] != row.get("text"):
                    raise ValueError("段落内容与全文位置不一致：" + full)
                seen.add(short)
                text = row.get("text")
                if not isinstance(text, str):
                    raise ValueError("正文内容不是字符串")
                cleaned.append({"paragraph_id": short, "full_id": prefix + short, "text": text})
            if not cleaned:
                raise ValueError("正文段落为空")
            result.append({"book_id": book_id, "chapter": chapter,
                           "paragraphs": cleaned, "source_member": member,
                           "source_sha256": hashlib.sha256(package.read(member)).hexdigest()})
    return result
