"""阶段级温度与采样合同。

本模块只负责把“某个 API 阶段该怎么采样”变成显式、可验票的对象。
它不发请求，也不从旧 provider 的全局 temperature 偷默认值。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .errors import ZBatchError


CALLABLE_STATUSES = frozenset({"baseline_reference", "approved_transport_reference"})
CANDIDATE_STATUS = "candidate_unverified"
SAFE_STAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ZBatchError(f"{label} 必须是 JSON 对象")
    return value


@dataclass(frozen=True)
class StageSamplingContract:
    """一个模型阶段的完整采样参数；任何字段都不走隐式回退。"""

    stage: str
    temperature: float
    max_tokens: int
    n: int
    reasoning_effort: str | None
    response_format: Mapping[str, Any]
    status: str
    note: str = ""

    @classmethod
    def from_mapping(cls, stage: str, raw: Mapping[str, Any]) -> "StageSamplingContract":
        if not isinstance(stage, str) or not SAFE_STAGE_NAME.fullmatch(stage):
            raise ZBatchError(f"阶段名不安全：{stage}")
        missing = [name for name in ("temperature", "max_tokens", "n", "response_format", "status") if name not in raw]
        if missing:
            raise ZBatchError(f"阶段 {stage} 缺合同字段：{missing}")
        temperature_raw = raw["temperature"]
        max_tokens_raw = raw["max_tokens"]
        n_raw = raw["n"]
        if isinstance(temperature_raw, bool) or not isinstance(temperature_raw, (int, float)):
            raise ZBatchError(f"阶段 {stage} 的温度必须是数字")
        if isinstance(max_tokens_raw, bool) or not isinstance(max_tokens_raw, int):
            raise ZBatchError(f"阶段 {stage} 的 max_tokens 必须是整数")
        if isinstance(n_raw, bool) or not isinstance(n_raw, int):
            raise ZBatchError(f"阶段 {stage} 的 n 必须是整数 1")
        temperature = float(temperature_raw)
        max_tokens = max_tokens_raw
        n = n_raw
        if not 0.0 <= temperature <= 2.0:
            raise ZBatchError(f"阶段 {stage} 的温度超出 0～2：{temperature}")
        if max_tokens <= 0:
            raise ZBatchError(f"阶段 {stage} 的 max_tokens 必须大于 0")
        if n != 1:
            raise ZBatchError(f"阶段 {stage} 采样合同只允许 n=1，收到：{n}")
        response_format = _require_mapping(raw["response_format"], f"阶段 {stage} response_format")
        if response_format.get("type") != "json_object":
            raise ZBatchError(f"阶段 {stage} 只允许 response_format=json_object")
        status = str(raw["status"]).strip()
        if status not in CALLABLE_STATUSES | {CANDIDATE_STATUS}:
            raise ZBatchError(f"阶段 {stage} 的合同状态不受支持：{status}")
        effort_value = raw.get("reasoning_effort")
        effort = None if effort_value is None else str(effort_value).strip()
        if effort is not None and not effort:
            effort = None
        return cls(
            stage=stage,
            temperature=temperature,
            max_tokens=max_tokens,
            n=n,
            reasoning_effort=effort,
            response_format=MappingProxyType(dict(response_format)),
            status=status,
            note=str(raw.get("note") or ""),
        )

    def assert_callable(self, *, allow_unverified_candidate: bool = False) -> None:
        if self.status == CANDIDATE_STATUS and not allow_unverified_candidate:
            raise ZBatchError(f"阶段 {self.stage} 只有未验证候选参数，默认拒绝调用")
        if self.status not in CALLABLE_STATUSES and self.status != CANDIDATE_STATUS:
            raise ZBatchError(f"阶段 {self.stage} 当前不可调用：{self.status}")


@dataclass(frozen=True)
class StageContractBundle:
    """一个明确命名的参数档案，以及只读的候选/机械登记区。"""

    contract_version: str
    profile: str
    profile_status: str
    route: Mapping[str, Any]
    stages: Mapping[str, StageSamplingContract]
    candidates: Mapping[str, StageSamplingContract]
    mechanical_modules: Mapping[str, Mapping[str, Any]]

    def stage(self, name: str) -> StageSamplingContract:
        try:
            return self.stages[name]
        except KeyError as exc:
            raise ZBatchError(f"当前档案没有阶段合同：{name}") from exc


def _parse_stage_map(raw: Mapping[str, Any], label: str) -> Mapping[str, StageSamplingContract]:
    result: dict[str, StageSamplingContract] = {}
    for stage, item in raw.items():
        result[str(stage)] = StageSamplingContract.from_mapping(
            str(stage), _require_mapping(item, f"{label}.{stage}")
        )
    if not result:
        raise ZBatchError(f"{label} 不能为空")
    return MappingProxyType(result)


def load_contract_bundle(path: Path, *, profile: str) -> StageContractBundle:
    """从 JSON 载入一个显式档案；没有档案名就拒绝猜默认。"""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ZBatchError(f"阶段合同文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ZBatchError(f"阶段合同不是合法 JSON：{path}") from exc
    root = _require_mapping(raw, "阶段合同根")
    version = str(root.get("contract_version") or "").strip()
    if not version:
        raise ZBatchError("阶段合同缺 contract_version")
    route = _require_mapping(root.get("route"), "route")
    profiles = _require_mapping(root.get("profiles"), "profiles")
    if profile not in profiles:
        raise ZBatchError(f"阶段合同档案不存在：{profile}")
    profile_raw = _require_mapping(profiles[profile], f"profiles.{profile}")
    profile_status = str(profile_raw.get("status") or "").strip()
    if profile_status not in {"baseline_reference", "approved_transport_reference"}:
        raise ZBatchError(f"档案 {profile} 状态不可用：{profile_status}")
    stages = _parse_stage_map(_require_mapping(profile_raw.get("stages"), f"profiles.{profile}.stages"), f"profiles.{profile}.stages")
    for contract in stages.values():
        if contract.status != profile_status:
            raise ZBatchError(
                f"档案 {profile} 与阶段 {contract.stage} 状态不一致：{profile_status}/{contract.status}"
            )

    candidate_raw = _require_mapping(root.get("candidate_registry"), "candidate_registry")
    candidates = _parse_stage_map(candidate_raw, "candidate_registry")
    for contract in candidates.values():
        if contract.status != CANDIDATE_STATUS:
            raise ZBatchError(f"候选登记 {contract.stage} 必须标 candidate_unverified")

    mechanical_raw = _require_mapping(root.get("mechanical_modules"), "mechanical_modules")
    mechanical: dict[str, Mapping[str, Any]] = {}
    for name, item in mechanical_raw.items():
        entry = _require_mapping(item, f"mechanical_modules.{name}")
        if entry.get("temperature", "missing") is not None:
            raise ZBatchError(f"纯机械模块 {name} 必须声明 temperature=null")
        mechanical[str(name)] = MappingProxyType(dict(entry))

    return StageContractBundle(
        contract_version=version,
        profile=profile,
        profile_status=profile_status,
        route=MappingProxyType(dict(route)),
        stages=stages,
        candidates=candidates,
        mechanical_modules=MappingProxyType(mechanical),
    )
