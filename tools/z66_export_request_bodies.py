#!/usr/bin/env python3
"""第66道：从历史落盘账逐字导出模型可见请求体（0 模型 API）。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/Z66_请求体全量打印诊断_20260720"

DEFAULT_RUN = ROOT / "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719"
Z59_RUN = ROOT / "runs/Z59_A_X01_实体供料注入中性抽取_五靶章_v1.0_20260719"
Z60_RUN = ROOT / "runs/Z60_B_X01_实体供料大纲逻辑双臂_五靶章_v1.1_20260720"

TARGET_CHAPTERS = (3, 4, 5, 13, 19)
EXPECTED_SOURCE_SHA256 = {
    "default_ch0003": "9eeede8c451f18349692c3d24a018b38575991a83940fbbe52fae3b6ee21ae1e",
    "default_ch0004": "7d7632a1c6e5f711a287aec16cb63722979b192dfbd06f90f9e4d599fb6e8221",
    "default_ch0005": "79cf5e4e550ba0ba556100489f648f31515a37f0045d50b396a73e551595ee98",
    "default_ch0013": "738fdfef944d538c4374acabc1fa5ab7aa93a89542144b3b8991320cebebbd16",
    "default_ch0019": "b05942b2c95d6c8d11eb39ed75765fe8ed3e7960a669e622c92bf91f6d7201b4",
    "z59_a_ch0003": "fb5f86ac39a0c148888498c456e9923dfd9faf76ccbddcbaa845eddb88c6c442",
    "z60_base_ch0003": "1678d9bfb5365f654d9b157d4e934028ea08cc686ec2dd7ff047cb9d3746c9b5",
    "z60_entity_ch0003": "337b1d581e28ff73ba455af417afd08edec9ad6b6a833bafc0f9bcf3bd2fa9e2",
}

SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:api_?key|authorization|access_?token|secret|password|cookie)(?:$|_)",
    re.I,
)
SENSITIVE_TEXT_RES = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def redact_sensitive(value: Any, path: tuple[str, ...] = ()) -> tuple[Any, list[str]]:
    """仅按字段名剔除凭据；返回被剔除的 JSON 路径。"""
    redacted_paths: list[str] = []
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_path = (*path, str(key))
            if SENSITIVE_KEY_RE.search(str(key)):
                result[key] = "[REDACTED]"
                redacted_paths.append(".".join(child_path))
            else:
                result[key], child_hits = redact_sensitive(child, child_path)
                redacted_paths.extend(child_hits)
        return result, redacted_paths
    if isinstance(value, list):
        result_list: list[Any] = []
        for index, child in enumerate(value):
            clean_child, child_hits = redact_sensitive(child, (*path, str(index)))
            result_list.append(clean_child)
            redacted_paths.extend(child_hits)
        return result_list, redacted_paths
    return value, redacted_paths


def text_secret_hits(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SENSITIVE_TEXT_RES:
        for match in pattern.finditer(text):
            hits.append(f"{pattern.pattern}@{match.start()}")
    return hits


def request_sources() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chapter in TARGET_CHAPTERS:
        rows.append(
            {
                "key": f"default_ch{chapter:04d}",
                "group": "default",
                "label": f"现役 v1.2 默认链｜第{chapter}章",
                "chapter": chapter,
                "path": DEFAULT_RUN / f"requests/neutral_extract/ch{chapter:04d}_request.json",
            }
        )
    rows.extend(
        [
            {
                "key": "z59_a_ch0003",
                "group": "z59_a",
                "label": "第59道试点A注入臂｜第3章",
                "chapter": 3,
                "path": Z59_RUN / "requests/neutral_extract/ch0003_request.json",
            },
            {
                "key": "z60_base_ch0003",
                "group": "z60_b",
                "label": "第60道试点B不带实体表臂｜第3章",
                "chapter": 3,
                "path": Z60_RUN / "requests/outline_logic/base_ch0003_request.json",
            },
            {
                "key": "z60_entity_ch0003",
                "group": "z60_b",
                "label": "第60道试点B带实体表臂｜第3章",
                "chapter": 3,
                "path": Z60_RUN / "requests/outline_logic/entity_ch0003_request.json",
            },
        ]
    )
    return rows


def validate_request(row: dict[str, Any], payload: dict[str, Any]) -> None:
    required_wrapper = {
        "provider",
        "api_base_url",
        "api_endpoint",
        "stage",
        "case_id",
        "contract_status",
        "unverified_candidate_override",
        "_security",
        "body",
    }
    required_body = {
        "model",
        "temperature",
        "max_tokens",
        "n",
        "response_format",
        "reasoning_effort",
        "messages",
    }
    missing_wrapper = sorted(required_wrapper - set(payload))
    missing_body = sorted(required_body - set(payload.get("body", {})))
    if missing_wrapper or missing_body:
        raise ValueError(
            f"{row['key']} 请求字段不完整：wrapper={missing_wrapper}, body={missing_body}"
        )
    messages = payload["body"]["messages"]
    if not messages or any(set(message) != {"role", "content"} for message in messages):
        raise ValueError(f"{row['key']} messages 结构漂移")


def source_component_map(row: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, message in enumerate(payload["body"]["messages"]):
        content = message["content"]
        kind = "系统提示词" if message["role"] == "system" else "任务合同＋供料"
        if row["group"] in {"z59_a", "z60_b"} and index == 1 and len(payload["body"]["messages"]) == 3:
            kind = "实体表注入块"
        parts: list[dict[str, Any]] = []
        if message["role"] == "user":
            catalog_marker = "冻结证据目录："
            event_marker = "中性事件供料："
            if catalog_marker in content:
                before, after = content.split(catalog_marker, 1)
                parts = [
                    {"name": "任务合同与输出样式", "chars": len(before)},
                    {"name": "冻结证据目录及其围栏", "chars": len(catalog_marker + after)},
                ]
            elif event_marker in content:
                before, after = content.split(event_marker, 1)
                parts = [
                    {"name": "任务合同与输出样式", "chars": len(before)},
                    {"name": "已落盘中性事件池子集", "chars": len(event_marker + after)},
                ]
            else:
                parts = [{"name": "完整用户消息（未机械拆段）", "chars": len(content)}]
        result.append(
            {
                "index": index,
                "role": message["role"],
                "kind": kind,
                "chars": len(content),
                "bytes": len(content.encode("utf-8")),
                "sha256": sha256_text(content),
                "parts": parts,
            }
        )
    return result


def request_record(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    path: Path = row["path"]
    actual_sha = sha256_file(path)
    expected_sha = EXPECTED_SOURCE_SHA256[row["key"]]
    if actual_sha != expected_sha:
        raise ValueError(f"{row['key']} 源请求 SHA 漂移：{actual_sha} != {expected_sha}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_request(row, payload)
    clean_payload, redacted_paths = redact_sensitive(deepcopy(payload))
    clean_text = json.dumps(clean_payload, ensure_ascii=False, indent=2)
    secret_hits = text_secret_hits(clean_text)
    if secret_hits:
        raise ValueError(f"{row['key']} 脱敏后仍命中凭据形态：{secret_hits}")
    record = {
        "key": row["key"],
        "group": row["group"],
        "label": row["label"],
        "chapter": row["chapter"],
        "source_path": str(path.relative_to(ROOT)),
        "source_sha256": actual_sha,
        "source_bytes": path.stat().st_size,
        "model_visible_body_sha256": sha256_bytes(json_bytes(payload["body"])),
        "parameters": {key: value for key, value in payload["body"].items() if key != "messages"},
        "message_components": source_component_map(row, payload),
        "redacted_field_count": len(redacted_paths),
        "redacted_fields": redacted_paths,
        "credential_pattern_hits_after_redaction": 0,
    }
    return record, clean_payload


def render_request_markdown(record: dict[str, Any], payload: dict[str, Any]) -> str:
    body = payload["body"]
    lines = [
        f"# {record['label']}｜完整请求体",
        "",
        "这份文件直接读取历史运行目录里的请求账，没有重构，也没有发送。Authorization 等运输凭据原本就不在请求账内。",
        "",
        "## 来源与参数",
        "",
        f"- 源文件：`{record['source_path']}`",
        f"- 源文件 SHA-256：`{record['source_sha256']}`",
        f"- 模型可见 body 规范化 SHA-256：`{record['model_visible_body_sha256']}`",
        f"- 接口：`{payload['api_base_url']}{payload['api_endpoint']}`",
        f"- 模型：`{body['model']}`",
        f"- 温度：`{body['temperature']}`",
        f"- 输出 token 护栏：`{body['max_tokens']}`",
        f"- 样本数：`{body['n']}`",
        f"- 思考档：`{body['reasoning_effort']}`",
        f"- 返回格式：`{json.dumps(body['response_format'], ensure_ascii=False, sort_keys=True)}`",
        f"- 凭据字段剔除数：{record['redacted_field_count']}",
        f"- 脱敏后凭据形态命中数：{record['credential_pattern_hits_after_redaction']}",
        "",
        "## 消息目录",
        "",
        "| 顺序 | role | 内容性质 | 字符 | 字节 | 内容 SHA-256 |",
        "|---:|---|---|---:|---:|---|",
    ]
    for item in record["message_components"]:
        lines.append(
            f"| {item['index']} | {item['role']} | {item['kind']} | {item['chars']} | {item['bytes']} | `{item['sha256']}` |"
        )
    lines.extend(["", "## 模型可见完整 body", "", "```json"])
    lines.append(json.dumps(body, ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## 逐条消息正文", ""])
    for index, message in enumerate(body["messages"]):
        component = record["message_components"][index]
        lines.extend(
            [
                f"### 消息 {index}｜{message['role']}｜{component['kind']}",
                "",
                f"字符 {component['chars']}｜字节 {component['bytes']}｜SHA-256 `{component['sha256']}`",
                "",
                "````text",
                message["content"],
                "````",
                "",
            ]
        )
    lines.extend(["来源：Codex", ""])
    return "\n".join(lines)


def render_index(records: list[dict[str, Any]]) -> str:
    lines = [
        "# 第66道｜请求体全量打印索引",
        "",
        "本件共导出 8 份历史真实请求：现役 v1.2 默认链五靶章 5 份，第59道试点A第3章 1 份，第60道试点B第3章双臂 2 份。模型 API 调用数为 0。",
        "",
        "| 文件 | 来源请求 SHA-256 | 消息角色 | 模型可见字符 | 凭据命中 |",
        "|---|---|---|---:|---:|",
    ]
    for record in records:
        roles = " → ".join(item["role"] for item in record["message_components"])
        chars = sum(item["chars"] for item in record["message_components"])
        filename = f"{record['key']}_完整请求体.md"
        lines.append(
            f"| `{filename}` | `{record['source_sha256']}` | {roles} | {chars} | {record['credential_pattern_hits_after_redaction']} |"
        )
    lines.extend(
        [
            "",
            "口径：这里的“完整请求体”指历史账中实际送入 `/chat/completions` 的 body 及请求账保存的接口元数据。Authorization 请求头按安全规则从未落盘，也不是模型可见输入。",
            "",
            "来源：Codex",
            "",
        ]
    )
    return "\n".join(lines)


def build(out_dir: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    rendered: dict[str, str] = {}
    for row in request_sources():
        record, clean_payload = request_record(row)
        records.append(record)
        rendered[f"{record['key']}_完整请求体.md"] = render_request_markdown(record, clean_payload)

    manifest = {
        "schema_version": "z66-request-export-v1",
        "task": "第66道请求体全量打印诊断件",
        "model_api_calls": 0,
        "network_requests": 0,
        "source_request_count": len(records),
        "source_sha_status": "pass",
        "credential_pattern_hits_after_redaction": sum(
            row["credential_pattern_hits_after_redaction"] for row in records
        ),
        "records": records,
    }
    rendered["00_请求体索引.md"] = render_index(records)

    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in sorted(rendered.items()):
        (out_dir / filename).write_text(content, encoding="utf-8")
    manifest_path = out_dir / "request_export_manifest.json"
    manifest_path.write_bytes(json_bytes(manifest))
    generated_paths = [out_dir / filename for filename in sorted(rendered)] + [manifest_path]
    output_hashes = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in generated_paths
    }
    receipt = {
        "schema_version": "z66-request-export-receipt-v1",
        "model_api_calls": 0,
        "network_requests": 0,
        "source_request_count": len(records),
        "source_sha_status": "pass",
        "all_required_fields_present": True,
        "credential_pattern_hits_after_redaction": manifest[
            "credential_pattern_hits_after_redaction"
        ],
        "output_hashes": output_hashes,
    }
    (out_dir / "mechanical_receipt.json").write_bytes(json_bytes(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        rows = []
        for source in request_sources():
            record, _ = request_record(source)
            rows.append(
                {
                    "key": record["key"],
                    "source_sha256": record["source_sha256"],
                    "messages": len(record["message_components"]),
                }
            )
        print(json.dumps({"status": "pass", "requests": rows}, ensure_ascii=False, sort_keys=True))
        return 0
    receipt = build(args.out)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
