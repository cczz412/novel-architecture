"""M3 抽取器：责任段（C2）→ 事实句候选（C3）。

只管三件事：prompt 构造、arkcli API 调用、JSON 解析。
切窗在 M2（segment.py），入账在 M4（store.py）；换模型/Prompt 只动本文件，合同不变。

传输走 arkcli（Agent Plan Small，凭证由 arkcli profile 托管，本代码不接触 Key）。
模型 ID 在 config.json；DISCRIM17 筛选出正式胜者后改配置即可。

合同：吃 contracts/C2_SEGMENT.md，吐 contracts/C3_FACT_CANDIDATE.md（均 v0）。
对外失败口径统一为 RuntimeError（超时、坏 JSON 都包成它，方便编排层收集）。

`call_json` 是本仓所有「要 JSON 输出的模型调用」的共用底层通道
（M7 体检也走它，传自己的 instructions）；抽取专用的指令和清洗留在 `call_model`。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

INSTRUCTIONS = (
    "你是小说事实抽取器。只依据【责任段】抽取其中已发生的客观事实句。\n"
    "- 每句独立完整、主语明确、能回责任段原文验证\n"
    "- 【前文背景】【后文背景】只读，只用于理解指代，不得从背景产出事实\n"
    "- 心理活动、比喻、猜测、未发生的计划不算事实\n"
    '- 只输出 JSON 对象：{"facts":[{"text":"事实句","quote":"责任段中的原文依据片段"}]}\n'
    '- 责任段没有可抽事实时输出 {"facts":[]}'
)

# I-009 截断重试用：高密度段降密度指令（追加在 INSTRUCTIONS 后）
RETRY_CAP_FACTS = 25
RETRY_DENSITY_NOTE = (
    f"\n- 本段信息密度过高，上一次输出被截断：只输出前 {RETRY_CAP_FACTS} 条最重要的事实"
    "（优先人物状态/关系/设定/关键事件），其余舍弃，确保 JSON 完整闭合"
)


class TruncatedOutput(RuntimeError):
    """模型输出疑似被 max_output_tokens 截断（JSON 解析失败＋输出 token 逼近上限）。
    是 RuntimeError 子类：不专门接它的调用方仍按普通失败处理。"""


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def build_user_content(seg: dict) -> str:
    """C2 责任段 → 模型输入文本（前后 halo 标注为只读背景）。"""
    parts = []
    if seg.get("halo_before"):
        parts.append(f"【前文背景·只读】\n…{seg['halo_before']}")
    parts.append(f"【责任段】\n{seg['text']}")
    if seg.get("halo_after"):
        parts.append(f"【后文背景·只读】\n{seg['halo_after']}…")
    return "\n\n".join(parts)


def call_json(instructions: str, user_content: str, cfg: dict) -> dict:
    """底层通道：带指定 instructions 调 arkcli +chat 并要求 JSON 输出。

    返回 {'data': 模型输出解析成的对象, 'usage': …, 'model': …}。
    超时、arkcli 失败、坏 JSON 一律包成 RuntimeError。
    """
    cmd = [
        "arkcli", "+chat",
        "--model", cfg["model_id"],
        "--instructions", instructions,
        "--temperature", str(cfg.get("temperature", 0)),
        "--max-output-tokens", str(cfg.get("max_output_tokens", 2000)),
        "--thinking", "disabled",
        "--text-format", "json_object",
        "--no-progress",
        "--format", "json",
        user_content,
    ]
    timeout = cfg.get("call_timeout_seconds", 180)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"arkcli 调用超时（>{timeout}s）") from e
    if proc.returncode != 0:
        raise RuntimeError(f"arkcli 调用失败（exit {proc.returncode}）：{proc.stderr.strip()[:500]}")
    try:
        resp = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"arkcli 输出不是 JSON：{proc.stdout[:200]}") from e
    content = resp.get("content", "")
    if isinstance(content, str):
        # 有的模型（如 GLM）即使要求 json_object 也会包 ```json 围栏，剥掉再解析
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped
            stripped = stripped.rsplit("```", 1)[0]
            content = stripped.strip()
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        # I-009 截断判据：解析失败且输出 token ≥ 上限的 95%，判为截断而非坏输出
        usage = resp.get("usage") or {}
        out_tokens = usage.get("completion_tokens", 0)
        limit = cfg.get("max_output_tokens", 2000)
        if isinstance(out_tokens, int) and out_tokens >= limit * 0.95:
            raise TruncatedOutput(
                f"输出疑似截断（output {out_tokens}/{limit} tokens，JSON 未闭合）") from e
        raise RuntimeError(f"模型输出不是合法 JSON：{str(content)[:200]}") from e
    return {"data": obj, "usage": resp.get("usage", {}), "model": resp.get("model", "")}


def call_model(user_content: str, cfg: dict, instructions: str = INSTRUCTIONS) -> dict:
    """抽取通道：默认抽取 INSTRUCTIONS，返回 {'facts': [...], 'usage': {...}}。失败抛 RuntimeError。"""
    r = call_json(instructions, user_content, cfg)
    data = r["data"]
    if not isinstance(data, dict):
        raise RuntimeError(f"模型输出不是合法 JSON 对象：{str(data)[:200]}")
    cleaned = [
        {"text": f["text"].strip(), "quote": (f.get("quote") or "").strip()}
        for f in data.get("facts", [])
        if isinstance(f, dict) and (f.get("text") or "").strip()
    ]
    return {"facts": cleaned, "usage": r["usage"], "model": r["model"]}


def extract_segment(seg: dict, cfg: dict) -> list[dict]:
    """单个责任段 → C3 事实候选列表（每条带来源段序号 seg）。失败抛 RuntimeError。

    I-009：输出截断不弃段——自动降密度重试一次（只要前 N 条最重要事实）；
    重试仍失败才向上抛，由编排层记失败段。
    """
    user_content = build_user_content(seg)
    try:
        r = call_model(user_content, cfg)
    except TruncatedOutput:
        try:
            r = call_model(user_content, cfg, instructions=INSTRUCTIONS + RETRY_DENSITY_NOTE)
            r["truncation_retried"] = True
        except TruncatedOutput as e:
            raise RuntimeError(f"高密度段降密度重试后仍截断：{e}") from e
    return [{**f, "seg": seg["seg"]} for f in r["facts"]]


def load_candidates_file(path: str) -> list[dict]:
    """备用入口：外部 JSON 文件 → C3 候选列表。格式 [{"text": "事实句", "quote": "原文依据"}]。"""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"文件不存在或不是文件：{p}")
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise SystemExit(f"候选文件不是 UTF-8 文本：{p}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"候选文件不是合法 JSON：{p}（{e}）") from e
    if not isinstance(items, list):
        raise SystemExit('候选文件格式应为 JSON 数组：[{"text": "事实句", "quote": "原文依据"}]')
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise SystemExit(f"候选文件第 {i} 条不是对象（需要 {{\"text\":...}}），整份先别入账")
    return items
