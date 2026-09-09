"""M3 抽取器：责任段（C2）→ 事实句候选（C3）。

只管三件事：prompt 构造、arkcli API 调用、JSON 解析。
切窗在 M2（segment.py），入账在 M4（store.py）；换模型/Prompt 只动本文件，合同不变。

传输走 arkcli（Agent Plan Small，凭证由 arkcli profile 托管，本代码不接触 Key）。
模型 ID 在 config.json；DISCRIM17 筛选出正式胜者后改配置即可。

合同：正式路径吃 C2 v1，吐 C3 v1，并原样继承 chapter revision ref。
旧 CLI 尚未改造的 v0 内存段仍保留兼容，但只有 v1 路径会得到 revision-aware C3。
对外失败仍是 RuntimeError 子类；传输、截断与原始回包失败另带结构化回执元数据。

`call_json` 是本仓所有「要 JSON 输出的模型调用」的共用底层通道
（M7 体检也走它，传自己的 instructions）；抽取专用的指令和清洗留在 `call_model`。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

try:
    from . import text_mapping as mapping_runtime
except ImportError:  # direct local-file CLI
    import text_mapping as mapping_runtime

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

INSTRUCTIONS = (
    "你是小说事实抽取器。只依据【责任段】抽取其中已发生的客观事实句。\n"
    "- 每句独立完整、主语明确、能回责任段原文验证\n"
    "- 【前文背景】【后文背景】只读，只用于理解指代，不得从背景产出事实\n"
    "- 心理活动、比喻、猜测、未发生的计划不算事实\n"
    '- 只输出 JSON 对象：{"facts":[{"text":"事实句","quote":"责任段中的原文依据片段"}]}\n'
    '- 责任段没有可抽事实时输出 {"facts":[]}'
)

C2_V1_KEYS = frozenset(
    {
        "contract",
        "version",
        "chapter_revision_ref",
        "seg",
        "text",
        "start",
        "end",
        "halo_before",
        "halo_after",
    }
)
REVISION_REF_KEYS = frozenset({"chapter_id", "revision_no", "revision_text_sha256"})
_V1_IDENTITY_KEYS = frozenset({"contract", "version", "chapter_revision_ref"})
CALL_RESULT_KEYS = frozenset({"data", "usage", "model"})
FACT_ITEM_KEYS = frozenset({"text", "quote"})


class C2V1ContractError(RuntimeError):
    """C2 v1 输入或 revision 身份不能安全进入 M3。"""


class ExtractCallFailure(RuntimeError):
    """一次模型传输／原始回包失败；只携带可写入运行回执的元数据。"""

    def __init__(
        self,
        message: str,
        *,
        completion_state: str,
        code: str,
        finish_reason: str | None = None,
        raw_response_sha256: str | None = None,
        raw_response_bytes: int | None = None,
    ):
        super().__init__(message)
        self.completion_state = completion_state
        self.code = code
        self.finish_reason = finish_reason
        self.raw_response_sha256 = raw_response_sha256
        self.raw_response_bytes = raw_response_bytes

    def receipt_failure(self, *, failed_item_key: str | None) -> dict:
        return {
            "code": self.code,
            "failed_item_key": failed_item_key,
            "finish_reason": self.finish_reason,
            "raw_response_sha256": self.raw_response_sha256,
            "raw_response_bytes": self.raw_response_bytes,
        }


class TruncatedOutput(ExtractCallFailure):
    """模型输出疑似被 max_output_tokens 截断；本层不自动重试。"""

    def __init__(
        self,
        message: str,
        *,
        finish_reason: str | None = None,
        raw_response_sha256: str | None = None,
        raw_response_bytes: int | None = None,
    ):
        # 保留旧调用方可只传 message 的构造方式；状态和错误码由类型唯一决定。
        super().__init__(
            message,
            completion_state="INCOMPLETE_TRUNCATED",
            code="MODEL_OUTPUT_TRUNCATED",
            finish_reason=finish_reason,
            raw_response_sha256=raw_response_sha256,
            raw_response_bytes=raw_response_bytes,
        )


def _raw_response_identity(value: object) -> tuple[str | None, int | None]:
    if value is None:
        return None, None
    if isinstance(value, bytes):
        payload = value
    else:
        payload = str(value).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _finish_reason(response: object) -> str | None:
    if not isinstance(response, dict):
        return None
    value = response.get("finish_reason")
    if isinstance(value, str) and value and value == value.strip():
        return value
    return None


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


def _validate_revision_ref(value: object, *, label: str) -> dict:
    if not isinstance(value, dict):
        raise C2V1ContractError(f"{label}_BAD_REVISION_REF:not_object")
    missing = sorted(REVISION_REF_KEYS - value.keys())
    extra = sorted(value.keys() - REVISION_REF_KEYS)
    if missing:
        raise C2V1ContractError(f"{label}_BAD_REVISION_REF:missing={','.join(missing)}")
    if extra:
        raise C2V1ContractError(f"{label}_BAD_REVISION_REF:extra={','.join(extra)}")

    chapter_id = value["chapter_id"]
    revision_no = value["revision_no"]
    digest = value["revision_text_sha256"]
    if (
        not isinstance(chapter_id, str)
        or not chapter_id.startswith("c")
        or len(chapter_id) < 3
        or not chapter_id[1:].isdigit()
    ):
        raise C2V1ContractError(f"{label}_BAD_REVISION_REF:chapter_id")
    if isinstance(revision_no, bool) or not isinstance(revision_no, int) or revision_no < 1:
        raise C2V1ContractError(f"{label}_BAD_REVISION_REF:revision_no")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise C2V1ContractError(f"{label}_BAD_REVISION_REF:revision_text_sha256")
    return {
        "chapter_id": chapter_id,
        "revision_no": revision_no,
        "revision_text_sha256": digest,
    }


def validate_c2_v1_segment(seg: object, *, current_chapter_revision_ref: object) -> dict:
    """严格验 C2 v1，并确认它仍绑定调用方看到的 current revision。"""
    if not isinstance(seg, dict):
        raise C2V1ContractError("C2_V1_NOT_OBJECT")
    missing = sorted(C2_V1_KEYS - seg.keys())
    extra = sorted(seg.keys() - C2_V1_KEYS - {"text_map"})
    if missing:
        raise C2V1ContractError(f"C2_V1_MISSING_FIELDS:{','.join(missing)}")
    if extra:
        raise C2V1ContractError(f"C2_V1_EXTRA_FIELDS:{','.join(extra)}")
    if seg["contract"] != "C2_SEGMENT" or seg["version"] != "v1":
        raise C2V1ContractError("C2_V1_IDENTITY_MISMATCH")

    revision_ref = _validate_revision_ref(seg["chapter_revision_ref"], label="C2_V1")
    current_ref = _validate_revision_ref(
        current_chapter_revision_ref,
        label="CURRENT_CHAPTER",
    )
    if revision_ref != current_ref:
        raise C2V1ContractError("C2_REVISION_REF_STALE_OR_MISMATCH")

    seg_no = seg["seg"]
    start = seg["start"]
    end = seg["end"]
    if isinstance(seg_no, bool) or not isinstance(seg_no, int) or seg_no < 1:
        raise C2V1ContractError("C2_V1_BAD_FIELD:seg")
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        raise C2V1ContractError("C2_V1_BAD_FIELD:start")
    if isinstance(end, bool) or not isinstance(end, int) or end < 0:
        raise C2V1ContractError("C2_V1_BAD_FIELD:end")
    if not isinstance(seg["text"], str):
        raise C2V1ContractError("C2_V1_BAD_FIELD:text")
    if end != start + len(seg["text"]):
        raise C2V1ContractError("C2_V1_BAD_OFFSETS:end_must_equal_start_plus_text_length")
    if not isinstance(seg["halo_before"], str) or not isinstance(seg["halo_after"], str):
        raise C2V1ContractError("C2_V1_BAD_FIELD:halo")
    if "text_map" in seg:
        try:
            mapping_runtime.validate_segment(seg)
        except (ValueError, KeyError, TypeError) as exc:
            raise C2V1ContractError(f"C2_TEXT_MAP_INVALID:{exc}") from exc
    return revision_ref


def call_json(instructions: str, user_content: str, cfg: dict) -> dict:
    """底层通道：成功形状不变；失败抛可结构化的 ``ExtractCallFailure``。

    本函数只尝试一次。原始回包不写入异常，只登记 SHA、字节数与 finish reason。
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
    except subprocess.TimeoutExpired as exc:
        raw_sha, raw_bytes = _raw_response_identity(exc.stdout)
        raise ExtractCallFailure(
            f"arkcli 调用超时（>{timeout}s）",
            completion_state="FAILED_TIMEOUT",
            code="ARKCLI_TIMEOUT",
            raw_response_sha256=raw_sha,
            raw_response_bytes=raw_bytes,
        ) from exc
    raw_sha, raw_bytes = _raw_response_identity(proc.stdout)
    if proc.returncode != 0:
        raise ExtractCallFailure(
            f"arkcli 调用失败（exit {proc.returncode}）",
            completion_state="FAILED_TRANSPORT",
            code=f"ARKCLI_EXIT_{proc.returncode}",
            raw_response_sha256=raw_sha,
            raw_response_bytes=raw_bytes,
        )
    try:
        resp = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExtractCallFailure(
            "arkcli 原始回包不是合法 JSON",
            completion_state="FAILED_RAW_RESPONSE",
            code="ARKCLI_ENVELOPE_JSON_INVALID",
            raw_response_sha256=raw_sha,
            raw_response_bytes=raw_bytes,
        ) from exc
    if not isinstance(resp, dict):
        raise ExtractCallFailure(
            "arkcli 原始回包顶层不是对象",
            completion_state="FAILED_RAW_RESPONSE",
            code="ARKCLI_ENVELOPE_NOT_OBJECT",
            raw_response_sha256=raw_sha,
            raw_response_bytes=raw_bytes,
        )
    content = resp.get("content", "")
    if isinstance(content, str):
        # 有的模型即使要求 json_object 也会包 JSON 围栏；只剥围栏，不修内容。
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped
            stripped = stripped.rsplit("```", 1)[0]
            content = stripped.strip()
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        usage = resp.get("usage")
        out_tokens = (
            usage.get("completion_tokens", 0)
            if isinstance(usage, dict)
            else 0
        )
        limit = cfg.get("max_output_tokens", 2000)
        finish_reason = _finish_reason(resp)
        if isinstance(out_tokens, int) and out_tokens >= limit * 0.95:
            raise TruncatedOutput(
                f"输出疑似截断（output {out_tokens}/{limit} tokens，JSON 未闭合）",
                finish_reason=finish_reason,
                raw_response_sha256=raw_sha,
                raw_response_bytes=raw_bytes,
            ) from exc
        raise ExtractCallFailure(
            "模型 content 不是合法 JSON",
            completion_state="FAILED_RAW_RESPONSE",
            code="MODEL_CONTENT_JSON_INVALID",
            finish_reason=finish_reason,
            raw_response_sha256=raw_sha,
            raw_response_bytes=raw_bytes,
        ) from exc
    return {"data": obj, "usage": resp.get("usage", {}), "model": resp.get("model", "")}


def parse_fact_call_result(r: object) -> dict:
    """共用解析边界：把 call_json 形状严格核成 M3 候选内存态。

    与离线入口 ``extract_tool._validate_provider_result`` 同尺：不 strip、
    不补默认值、不丢坏项。任一字段或条目不合法，整段拒绝。
    """
    if not isinstance(r, dict):
        raise RuntimeError(f"抽取返回不是对象：{str(r)[:200]}")
    missing = sorted(CALL_RESULT_KEYS - r.keys())
    extra = sorted(r.keys() - CALL_RESULT_KEYS)
    if missing:
        raise RuntimeError(f"抽取返回缺少字段：{','.join(missing)}")
    if extra:
        raise RuntimeError(f"抽取返回多了字段：{','.join(extra)}")
    if not isinstance(r["usage"], dict) or not isinstance(r["model"], str):
        raise RuntimeError("抽取返回 usage/model 形状不合法")

    data = r["data"]
    if not isinstance(data, dict) or set(data) != {"facts"}:
        raise RuntimeError("模型输出 data 形状不合法")
    facts = data["facts"]
    if not isinstance(facts, list):
        raise RuntimeError("模型输出 facts 不是数组")

    parsed: list[dict] = []
    for index, item in enumerate(facts, start=1):
        if not isinstance(item, dict) or set(item) != FACT_ITEM_KEYS:
            raise RuntimeError(f"模型输出第 {index} 条事实形状不合法")
        text = item["text"]
        quote = item["quote"]
        if not isinstance(text, str) or not text or text != text.strip():
            raise RuntimeError(f"模型输出第 {index} 条 text 不合法")
        if not isinstance(quote, str) or quote != quote.strip():
            raise RuntimeError(f"模型输出第 {index} 条 quote 不合法")
        parsed.append({"text": text, "quote": quote})
    return {"facts": parsed, "usage": r["usage"], "model": r["model"]}


def call_model(user_content: str, cfg: dict, instructions: str = INSTRUCTIONS) -> dict:
    """抽取通道：默认抽取 INSTRUCTIONS，返回 {'facts': [...], 'usage': {...}}。失败抛 RuntimeError。"""
    return parse_fact_call_result(call_json(instructions, user_content, cfg))


def extract_segment(
    seg: dict,
    cfg: dict,
    *,
    current_chapter_revision_ref: dict | None = None,
    response_provider: Callable[[str, str, dict], dict] | None = None,
) -> list[dict]:
    """单个责任段 → C3 事实候选列表。

    C2 v1 输入必须同时给出调用方看到的 current revision ref；候选会
    完整继承这份 ref。response_provider 是零 API 测试缝：它收到同一份
    instructions/user_content/cfg，必须返回 call_json 形状，再走同一解析边界。

    传输、截断或原始回包失败只尝试一次并向上抛；工作区 owner 负责写结构化
    运行回执。不在本层自动重试，也不把部分候选冒充完整 C3。
    """
    revision_ref = None
    if _V1_IDENTITY_KEYS.intersection(seg):
        revision_ref = validate_c2_v1_segment(
            seg,
            current_chapter_revision_ref=current_chapter_revision_ref,
        )

    user_content = build_user_content(seg)
    if response_provider is not None:
        r = parse_fact_call_result(response_provider(INSTRUCTIONS, user_content, cfg))
    else:
        r = call_model(user_content, cfg)

    if revision_ref is None:
        return [{**fact, "seg": seg["seg"]} for fact in r["facts"]]
    candidates = [
        {
            "contract": "C3_FACT_CANDIDATE",
            "version": "v1",
            "chapter_revision_ref": dict(revision_ref),
            "text": fact["text"],
            "quote": fact["quote"],
            "seg": seg["seg"],
        }
        for fact in r["facts"]
    ]
    if "text_map" in seg:
        for candidate in candidates:
            try:
                candidate["text_map_evidence"] = mapping_runtime.build_evidence(seg, candidate["quote"])
            except (ValueError, KeyError, TypeError) as exc:
                raise C2V1ContractError(f"C3_TEXT_MAP_INVALID:{exc}") from exc
    return candidates


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
