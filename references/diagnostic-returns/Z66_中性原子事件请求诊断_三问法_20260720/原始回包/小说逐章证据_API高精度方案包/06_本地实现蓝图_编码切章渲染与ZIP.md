# 本地实现蓝图：编码、切章、API 编排、渲染与 ZIP

> 下面代码是可落地的骨架，不绑定某一家模型。接口按常见的 `/chat/completions` 形态编写；字段不被你的提供商支持时，应在配置层调整。生产环境需补充日志、数据库和单元测试。

## 1. 推荐目录

```text
project/
├─ input/
│  └─ novel.zip
├─ work/
│  ├─ raw/
│  ├─ chapters/
│  ├─ line_maps/
│  ├─ requests/
│  ├─ responses/
│  ├─ candidates/
│  ├─ verification/
│  ├─ accepted/
│  └─ state/
├─ output/
│  ├─ 第01章.md
│  ├─ 第02章.md
│  └─ 全书逐章证据.md
├─ prompts/
├─ schemas/
└─ run.py
```

## 2. 依赖与配置

```bash
pip install httpx jsonschema
```

环境变量：

```text
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=...
LLM_MODEL=your-model
```

不要把密钥写入请求日志、Markdown 或 ZIP。

## 3. 安全解压并修复旧 ZIP 文件名

当前归档的中文文件名缺少 UTF-8 标志。下面函数兼容正常 ZIP，也尝试修复“UTF-8 字节被按 CP437 解码”的旧文件名。

```python
from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

SKIP_NAMES = {".DS_Store"}


def repair_legacy_zip_name(name: str) -> str:
    """只在可逆时修复 CP437→UTF-8 乱码。"""
    try:
        repaired = name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name

    # 修复后至少应出现非 ASCII，且不能含替换字符。
    if repaired != name and "\\ufffd" not in repaired:
        return repaired
    return name


def safe_extract_zip(zip_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    root = out_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            fixed_name = repair_legacy_zip_name(info.filename)
            normalized = fixed_name.replace("\\", "/")

            if normalized.endswith("/"):
                continue
            if normalized.startswith("__MACOSX/"):
                continue
            if "/._" in normalized or Path(normalized).name.startswith("._"):
                continue
            if Path(normalized).name in SKIP_NAMES:
                continue

            target = (out_dir / normalized).resolve()
            if root not in target.parents:
                raise ValueError(f"ZIP 路径穿越：{normalized}")

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(target)

    return extracted
```

## 4. 严格解码，不要静默丢字

```python
from pathlib import Path


def decode_text(data: bytes, source: str) -> tuple[str, str]:
    """返回文本与实际编码。优先严格 UTF-8，再尝试 GB18030。"""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"

    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass

    raise UnicodeError(f"无法可靠解码：{source}")


def normalize_newlines(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text or "\\ufffd" in text:
        raise ValueError("文本含 NUL 或替换字符，禁止继续")
    return text
```

不要使用：

```python
data.decode("utf-8", errors="ignore")
```

`errors="ignore"` 会在不报警的情况下丢字，之后短引永远无法精确匹配原文。

## 5. 切章与连续性校验

章节格式因来源而异，正则需配置。下面示例适配“第3章 第3章 标题”一类标题，并保留原始内容。

```python
from dataclasses import dataclass
import hashlib
import re

@dataclass(frozen=True)
class Chapter:
    number: int
    title: str
    raw_text: str
    sha256: str


CHAPTER_RE = re.compile(r"(?m)^第(\d+)章\s+第\1章\s+(.+?)\s*$")


def split_chapters(text: str) -> list[Chapter]:
    matches = list(CHAPTER_RE.finditer(text))
    if not matches:
        raise ValueError("没有识别到章节标题")

    chapters: list[Chapter] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[start:end].strip() + "\n"
        number = int(match.group(1))
        title = match.group(2).strip()
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        chapters.append(Chapter(number, title, raw, digest))

    numbers = [item.number for item in chapters]
    expected = list(range(numbers[0], numbers[-1] + 1))
    if numbers != expected:
        raise ValueError(f"章节断号或重复：{numbers}")
    return chapters
```

全书由多个文件组成时，应在合并后再次检查第1～N章连续、无重复。

## 6. 生成行号文本与映射

推荐以段落为单位；空行不编号。重复章标题和作者 `ps` 不要直接删除，而是标记类型，便于审计。

```python
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class SourceLine:
    line_id: str
    text: str
    kind: str  # title | narrative | author_note


def make_line_map(chapter: Chapter) -> list[SourceLine]:
    result: list[SourceLine] = []
    counter = 1

    for raw_line in chapter.raw_text.splitlines():
        line = raw_line.strip("\u3000 ")
        if not line:
            continue

        if re.match(rf"^第{chapter.number}章", line):
            kind = "title"
        elif re.match(r"^(ps|PS|作者说|注)[:：]", line):
            kind = "author_note"
        else:
            kind = "narrative"

        line_id = f"L{counter:04d}"
        result.append(SourceLine(line_id, line, kind))
        counter += 1

    return result


def render_line_map(lines: list[SourceLine]) -> str:
    return "\n".join(f"[{x.line_id}] {x.text}" for x in lines)
```

若一段很长，可以在完整标点边界拆句，但应保留 `paragraph_id` 与原始偏移，避免丢失跨句关系。

## 7. 构造请求

```python
from typing import Any
import json


def build_messages(
    system_prompt: str,
    chapter: Chapter,
    lines: list[SourceLine],
    prior_state: dict[str, Any],
    extractor: str,
) -> list[dict[str, str]]:
    user_payload = f"""
<JOB>
job_type: chapter_evidence_extraction_{extractor}
schema_version: novel-evidence-candidate-v2
chapter_no: {chapter.number}
chapter_title: {chapter.title}
source_sha256: {chapter.sha256}
</JOB>

<PRIOR_STATE context_only=\"true\" citable=\"false\">
{json.dumps(prior_state, ensure_ascii=False, indent=2)}
</PRIOR_STATE>

<CURRENT_CHAPTER sole_evidence_source=\"true\">
{render_line_map(lines)}
</CURRENT_CHAPTER>
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_payload},
    ]
```

`来源：Codex`、文件哈希报告、调试说明等不要拼进 `user_payload`。

## 8. 调用 OpenAI-compatible API

```python
from dataclasses import dataclass
import hashlib
import httpx
import json
import os
import time

@dataclass
class LLMResult:
    content: str
    finish_reason: str | None
    raw: dict


class LLMClient:
    def __init__(self) -> None:
        self.base_url = os.environ["LLM_BASE_URL"].rstrip("/")
        self.api_key = os.environ["LLM_API_KEY"]
        self.model = os.environ["LLM_MODEL"]

    def chat_json(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 12000,
        retries: int = 3,
    ) -> LLMResult:
        payload = {
            "model": self.model,
            "temperature": 0,
            "n": 1,
            "max_tokens": max_tokens,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                response.raise_for_status()
                raw = response.json()
                choice = raw["choices"][0]
                content = choice["message"]["content"]
                finish_reason = choice.get("finish_reason")
                if finish_reason in {"length", "max_tokens"}:
                    raise RuntimeError("模型输出被截断")
                return LLMResult(content, finish_reason, raw)
            except (httpx.HTTPError, KeyError, ValueError, RuntimeError) as exc:
                last_error = exc
                if attempt + 1 >= retries:
                    break
                time.sleep(2 ** attempt)

        raise RuntimeError("模型调用失败") from last_error
```

生产环境建议：

- 网络重试只处理超时、连接失败和5xx；
- 4xx 不应盲目重试；
- 语义问题进入 Verifier／Repairer，而不是把相同请求重复发送；
- 日志只保存去掉 Authorization 的请求体；
- 保存完整响应、usage、finish_reason 和提供商 request id。

## 9. JSON 与引用机械校验

```python
from typing import Any
import json
from jsonschema import Draft202012Validator


def parse_and_validate_json(raw_content: str, schema: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(raw_content)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        detail = "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:20])
        raise ValueError(f"Schema 校验失败：\n{detail}")
    return data


def validate_source_refs(result: dict, lines: list[SourceLine], chapter_no: int) -> None:
    line_map = {line.line_id: line.text for line in lines}

    if result["chapter"] != chapter_no:
        raise ValueError("响应章号不匹配")

    seen_ids: set[str] = set()
    for item in result["candidates"]:
        temp_id = item["temp_id"]
        if temp_id in seen_ids:
            raise ValueError(f"重复 temp_id：{temp_id}")
        seen_ids.add(temp_id)

        for ref in item["source_refs"]:
            selected: list[str] = []
            for line_id in ref["line_ids"]:
                if line_id not in line_map:
                    raise ValueError(f"未知 line_id：{line_id}")
                selected.append(line_map[line_id])

            haystack = "\n".join(selected)
            quote = ref["quote"]
            if quote not in haystack:
                raise ValueError(f"短引不匹配：{temp_id} / {quote!r}")
```

若换行或空格规范化会影响短引匹配，应统一对 `model_text` 进行匹配，并保存回原始文本的偏移映射；不要模糊匹配后直接判定通过。

## 10. 排序和正式编号

模型不生成 `E-03-01`。程序从短引位置计算排序键：

```python
import re


def first_line_number(item: dict) -> int:
    ids = [line_id for ref in item["source_refs"] for line_id in ref["line_ids"]]
    return min(int(re.search(r"\d+", line_id).group()) for line_id in ids)


def assign_evidence_ids(chapter_no: int, accepted: list[dict]) -> list[dict]:
    ordered = sorted(accepted, key=lambda item: (first_line_number(item), item["temp_id"]))
    width = max(2, len(str(len(ordered))))

    result: list[dict] = []
    for index, item in enumerate(ordered, start=1):
        copy = dict(item)
        copy["evidence_id"] = f"E-{chapter_no:02d}-{index:0{width}d}"
        result.append(copy)
    return result
```

同一行内有多项时，最好进一步保存 quote 在行内的起始位置，避免仅按 temp_id 排序。

## 11. 确定性渲染 Markdown

```python
from pathlib import Path


def render_chapter_md(chapter: Chapter, evidence: list[dict]) -> str:
    output = [f"## 第{chapter.number:02d}章 {chapter.title}", ""]
    for item in evidence:
        source = f"第{chapter.number}章"
        output.append(f"- **{item['evidence_id']}** {item['fact']}【来源：{source}】")
    output.append("")
    return "\n".join(output)


def write_utf8(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
```

这样可保证：

- 编号连续；
- 一条一行；
- 来源章不会写错；
- 不会因模型 Markdown 习惯出现漏号、重复标题或围栏错误。

## 12. 正确创建 UTF-8 ZIP

```python
from pathlib import Path
import zipfile


def build_utf8_zip(md_dir: Path, zip_path: Path) -> None:
    files = sorted(md_dir.glob("*.md"))
    if not files:
        raise ValueError("没有 Markdown 文件")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            # arcname 是真正的 Unicode str；Python 会为非 ASCII 名称设置 UTF-8 标志。
            zf.write(path, arcname=path.name)

    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC 错误：{bad}")

        for info in zf.infolist():
            if any(ord(ch) > 127 for ch in info.filename):
                if not (info.flag_bits & 0x800):
                    raise ValueError(f"中文文件名缺少 UTF-8 标志：{info.filename}")
            if info.filename.startswith("__MACOSX/") or "/._" in info.filename:
                raise ValueError(f"ZIP 混入 macOS 元数据：{info.filename}")
```

## 13. 全书编排伪代码

```python
prior_state = empty_state()
all_chapter_outputs = []

for chapter in chapters:
    lines = make_line_map(chapter)

    result_a = run_extractor_A(chapter, lines, prior_state)
    result_b = run_extractor_B(chapter, lines, prior_state)

    mechanical_validate(result_a, lines)
    mechanical_validate(result_b, lines)

    merged = deterministic_merge(result_a["candidates"], result_b["candidates"])

    verification = run_verifier(chapter, lines, prior_state, merged)
    repaired = run_repairer_for_issues(chapter, lines, verification, merged)
    current = apply_repairs(merged, verification, repaired)

    gaps = run_gap_finder(chapter, lines, current)
    mechanical_validate(gaps, lines)
    verify_new_gaps(chapter, lines, gaps)
    current.extend(gaps["missing_candidates"])

    current = semantic_dedupe_small_batches(current)
    accepted = assign_evidence_ids(chapter.number, current)

    write_chapter_markdown(chapter, accepted)
    persist_json(accepted)

    delta = run_state_updater(prior_state, accepted)
    prior_state = apply_state_delta(prior_state, delta)
    persist_state(prior_state)

    all_chapter_outputs.append(accepted)

run_global_checks(all_chapter_outputs, chapters)
render_combined_markdown(all_chapter_outputs)
build_utf8_zip(output_dir, final_zip)
```

## 14. 日志与可重放性

每次调用保存：

```json
{
  "job_id": "NOVELSHA-C0003-extractorA-v2",
  "chapter_sha256": "…",
  "prior_state_sha256": "…",
  "prompt_version": "extractor-A-v2.0",
  "model": "…",
  "parameters": {"temperature": 0, "max_tokens": 12000},
  "request_sha256": "…",
  "response_sha256": "…",
  "finish_reason": "stop",
  "schema_status": "pass",
  "quote_status": "pass",
  "semantic_status": "pending|pass|fail"
}
```

密钥、Authorization、Cookie 不落盘。

## 15. 最小数据库表

可先用 SQLite：

```text
novels(id, source_sha, title)
chapters(id, novel_id, chapter_no, title, source_sha, raw_path, line_map_path)
model_runs(id, chapter_id, stage, prompt_version, model, request_sha, response_sha, status)
candidates(id, chapter_id, temp_id, fact, category, assertion_mode, json_blob)
evidence(id, chapter_id, evidence_id, fact, order_key, json_blob)
state_versions(id, through_chapter, state_sha, json_path)
issues(id, chapter_id, temp_id, issue_type, status, json_blob)
```

## 16. 不要让模型承担的事情

以下工作本地代码更可靠：

- 解压和编码；
- 切章；
- 章号与标题核验；
- SHA；
- 最终 E 编号；
- 短引是否为原文子串；
- JSON Schema；
- ID 连续性；
- Markdown 排版；
- ZIP 创建和 UTF-8 标志；
- 重试、缓存和状态机。

模型只做程序难以机械完成的语义工作：事实抽取、模态判断、原子性、语义重复和补漏。
