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
            cleaned = []
            seen = set()
            for index, row in enumerate(paragraphs, 1):
                full = str(row.get("paragraph_id", ""))
                short = full.rsplit(":", 1)[-1] if full else "p" + str(index).zfill(3)
                if not re.fullmatch(r"p\d+", short) or short in seen:
                    raise ValueError("正文段号无效或重复")
                seen.add(short)
                text = row.get("text")
                if not isinstance(text, str):
                    raise ValueError("正文内容不是字符串")
                cleaned.append({"paragraph_id": short, "full_id": full or
                                book_id + ":ch" + chapter + ":" + short, "text": text})
            if not cleaned:
                raise ValueError("正文段落为空")
            result.append({"book_id": book_id, "chapter": chapter,
                           "paragraphs": cleaned, "source_member": member,
                           "source_sha256": hashlib.sha256(package.read(member)).hexdigest()})
    return result
