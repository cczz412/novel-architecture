"""第96道 r02 的零调用、分阶段、双跑生成器。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from tools.zbatch_modules.extraction_coverage import (
    CoverageDiagnosticError,
    locate_catalog_spans,
)

from .core import (
    Z96CoreError,
    nearest_rank_percentile,
    score_recall,
    sha256_bytes,
    stable_json_bytes,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "experiments.Z96_anchor_layer_evidence_closure_r02_20260724"
AUTHORITY_TIME = "2026-07-24T13:25:00+08:00"
AUTHORIZED_RUN_DIRECTORY = "runs/Z96_刀B_Aplus锚层与证据闭包_r02_20260724"

X04_LEDGER = "reports/九项第三道_主张级核锚并单设计_20260723/x04_recompute/x04_claim_anchor_recompute.json"
X04_BODY = "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723/inputs/cases/X04-C0046/chapter_body.txt"
X04_CATALOG = "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723/inputs/cases/X04-C0046/evidence_catalog.json"
X04_SAMPLE = "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723/samples/X04-C0046__pro_primary_tencent/candidate/neutral_events.json"

RETRY03_ROOT = "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry03"
RETRY03_EVENTS = {
    3: f"{RETRY03_ROOT}/main/01_extract/events/ch0003.json",
    13: f"{RETRY03_ROOT}/main/01_extract/events/ch0013.json",
    19: f"{RETRY03_ROOT}/main/01_extract/events/ch0019.json",
}
RETRY03_CATALOGS = {
    3: f"{RETRY03_ROOT}/inputs/evidence_catalogs/ch0003.json",
    13: f"{RETRY03_ROOT}/inputs/evidence_catalogs/ch0013.json",
    19: f"{RETRY03_ROOT}/inputs/evidence_catalogs/ch0019.json",
}
RETRY03_BODIES = {
    3: f"{RETRY03_ROOT}/inputs/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt",
    13: f"{RETRY03_ROOT}/inputs/chapters/0013_第13章_值夜者.txt",
    19: f"{RETRY03_ROOT}/inputs/chapters/0019_第19章_封印物（第二更求推荐票）.txt",
}

Z89_ROOT = "runs/Z89_X01_DeepSeekV4Pro强模型对照_第3章_v1.0_20260723"
Z89_EVENTS = f"{Z89_ROOT}/main/01_extract/events/ch0003.json"
Z89_CATALOG = f"{Z89_ROOT}/inputs/evidence_catalogs/ch0003.json"
Z89_BODY = f"{Z89_ROOT}/inputs/chapters/0003_第3章_梅丽莎（第一更求推荐票）.txt"
Z89_ADJUDICATION = f"{Z89_ROOT}/review/adjudication_completed.json"

RETRY13_ROOT = "runs/Z83_X01_v3程序侧治法_三章复验_v1.0_20260722_transport_retry13"

EXPECTED_SHA256 = {
    X04_LEDGER: "7085dc67c4e0e3762ab43fd9dbc9aad8f9eacc0bcad7dd086c55136daf116324",
    X04_BODY: "4e168668007a8ec58db29b3511facfd3bafb9a6eb327078bc7564efdf563e96e",
    X04_CATALOG: "1c16106ddc66d0a2818ac73e593c2473808dff162852e1e4449baa17f29f4d15",
    X04_SAMPLE: "865c5240a8b33a5603e07d763fb6d1b84964b7d8b722543b1d27d89ae4636bb7",
    RETRY03_EVENTS[3]: "295c7f19dc46bd3c56e984ec701d40dcb34a68eef0a20ec3474cfb5f723d150a",
    RETRY03_EVENTS[13]: "aeefcee35c56e52f82dc7382d1073902311c68947d4d8c518cfbf23816808898",
    RETRY03_EVENTS[19]: "2f7b9713149183a73d4b1b17a620cba3dabe146ff5935d8a43f1e15bd8243d30",
    RETRY03_CATALOGS[3]: "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    RETRY03_CATALOGS[13]: "47d5a5f13b227e4c1470530a1962060f7800f05f30e9e73b815a17604bd9457e",
    RETRY03_CATALOGS[19]: "dd7b2215801668b3896ccf5c3c651752fa9293b4da0916465f9f3b6fcfd6ba7e",
    RETRY03_BODIES[3]: "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    RETRY03_BODIES[13]: "418efe90277893207d2623d14c9093a30a68f38f44dd51ebcee6315813ddd8c0",
    RETRY03_BODIES[19]: "127af1d2061e3e4cccca7f893ae98e511c2902a7ae06aecc9fa783eb22ca5caa",
    Z89_EVENTS: "97f39e145c7774e5204983d1639ccde1f4be13f42fc6eb6a6306de6b42e5948d",
    Z89_CATALOG: "2cc50e9a0c8b5fb807641e09c74f1748cbe423bf0fa700dbbbaa84ba20e58132",
    Z89_BODY: "96f5e17cbec15433b5d00bef18912eb39710ad67962e3716bca37203d4c06288",
    Z89_ADJUDICATION: "ddb35e13502fd21545b2cadf65cc38f7acd1b986be1f8d1b8ff9ba217a3f4d4e",
}

CALIBRATION_USAGE_SHA256 = {
    f"{RETRY03_ROOT}/main/usage.jsonl": "ffec6350aa88c1bdd1d25da4c3d639f96c4584c3ae45da63f34e4e06b33b29e1",
    f"{Z89_ROOT}/main/usage.jsonl": "e7ebbdcb8b236ee24d9d700a39d90a3fba7834723ae7ec18a0d6d8cbc820baf8",
    f"{RETRY13_ROOT}/repair/usage.jsonl": "eacedcbfce6b5d40838161d5b6c412c761371f66a85ece10dcf0be897d7db2e1",
    f"{RETRY13_ROOT}/final_review/inspector/ch0003/run/checkpoint/03_usage.json": "891eaaf6021c74da46c99023632b8f767bfc33899b5a780131f2ef648826c1d5",
    f"{RETRY13_ROOT}/final_review/inspector/ch0013/run/checkpoint/03_usage.json": "737f876d54ec766fdc2e8b15394d157f341a3fd642e937a1875ec06db1da5bdf",
    f"{RETRY13_ROOT}/final_review/inspector/ch0019/run/checkpoint/03_usage.json": "de5416c4d78b3c7bfdb686cb950fc3b592fde0c20832fe4c0690e742a80f051e",
}

_STATIC_PROTECTED_PATHS = (
    RETRY03_ROOT,
    Z89_ROOT,
    "runs/Z91_双臂跨书基线_步二v2双臂_v1.3_20260723",
    "reports/Z92_anchor_coverage_hard_gate_exp_20260723",
    "reports/九项第三道_主张级核锚并单设计_20260723",
    "governance",
    "config/gold",
    "config/defaults/zbatch_v1.2_full_chain.COMMITTED.json",
    "config/defaults/zbatch_v1.2_full_chain.json",
    "config/contracts/classify_rules_v1.2_semantic_identity_v1.json",
    "runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json",
    "outbox",
    "experiments/Z96_anchor_layer_evidence_closure_20260724",
    "experiments/Z96_anchor_layer_evidence_closure_r02_20260724",
    "tests/test_z96_r02_anchor_evidence_candidate.py",
    "reports/Z96_刀B_Aplus锚层与证据闭包_20260724",
)
_SEALED_PREFIXES = ("Z83", "Z89", "Z91", "Z92", "Z94")
_DISCOVERED_SEALED_PATHS = tuple(
    sorted(
        {
            path.relative_to(REPO_ROOT).as_posix()
            for parent_name in ("runs", "reports")
            for prefix in _SEALED_PREFIXES
            for path in (REPO_ROOT / parent_name).glob(f"{prefix}*")
            if path.is_dir()
        }
    )
)
PROTECTED_PATHS = tuple(
    dict.fromkeys(_STATIC_PROTECTED_PATHS + _DISCOVERED_SEALED_PATHS)
)


class Z96PipelineError(RuntimeError):
    """r02 输入、隔离、硬闸或保护面不成立。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(stable_json_bytes(value))
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class BootstrapReader:
    """高权限引导器：只按预登记 SHA 读源，按阶段顺序记账。"""

    def __init__(self) -> None:
        self.sequence = 0
        self.rows: list[dict[str, Any]] = []
        self.milestones: list[dict[str, Any]] = []

    def milestone(self, name: str, **fields: Any) -> None:
        self.sequence += 1
        self.milestones.append({"sequence": self.sequence, "name": name, **fields})

    def bytes(
        self,
        relative: str,
        *,
        expected_sha256: str,
        phase: str,
        answer_derived: bool,
    ) -> bytes:
        path = REPO_ROOT / relative
        if path.is_symlink():
            raise Z96PipelineError(f"引导器拒绝符号链接：{relative}")
        actual = sha256_file(path)
        if actual != expected_sha256:
            raise Z96PipelineError(
                f"冻结来源 SHA 漂移：{relative} expected={expected_sha256} actual={actual}"
            )
        data = path.read_bytes()
        self.sequence += 1
        self.rows.append(
            {
                "sequence": self.sequence,
                "path": relative,
                "phase": phase,
                "answer_derived": answer_derived,
                "bytes": len(data),
                "sha256": actual,
            }
        )
        return data

    def json(
        self,
        relative: str,
        *,
        expected_sha256: str,
        phase: str,
        answer_derived: bool,
    ) -> Any:
        return json.loads(
            self.bytes(
                relative,
                expected_sha256=expected_sha256,
                phase=phase,
                answer_derived=answer_derived,
            ).decode("utf-8")
        )

    def text(
        self,
        relative: str,
        *,
        expected_sha256: str,
        phase: str,
    ) -> str:
        return self.bytes(
            relative,
            expected_sha256=expected_sha256,
            phase=phase,
            answer_derived=False,
        ).decode("utf-8")


def _catalog_entries(catalog: Any, body: str, chapter: int) -> list[dict[str, Any]]:
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    if not isinstance(entries, list) or not entries:
        raise Z96PipelineError("冻结锚目录缺 entries")
    normalized: list[dict[str, Any]] = []
    raw_for_alignment: list[dict[str, Any]] = []
    seen: set[str] = set()
    for order, row in enumerate(entries):
        if not isinstance(row, dict):
            raise Z96PipelineError("锚目录行不是对象")
        anchor_id = str(row.get("anchor_id") or "")
        quote = str(row.get("quote") or "")
        if not re_full_anchor(anchor_id) or not quote or anchor_id in seen:
            raise Z96PipelineError("锚目录含非法、空短引或重复锚")
        seen.add(anchor_id)
        raw_for_alignment.append(dict(row))
        normalized.append(
            {
                "anchor_id": anchor_id,
                "chapter": chapter,
                "quote": quote,
                "order": order,
            }
        )
    try:
        locate_catalog_spans(body, raw_for_alignment)
    except CoverageDiagnosticError as exc:
        raise Z96PipelineError(str(exc)) from exc
    return normalized


def re_full_anchor(value: str) -> bool:
    return len(value) == 5 and value.startswith("E") and value[1:].isdigit()


def _validate_events(
    data: Any,
    *,
    dataset_id: str,
    chapter: int,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list) or not events:
        raise Z96PipelineError(f"{dataset_id} 样张缺 events")
    catalog_map = {row["anchor_id"]: row for row in catalog}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        event_id = str(event.get("event_id") or "")
        event_text = str(event.get("event") or "")
        if not event_id or not event_text or event_id in seen:
            raise Z96PipelineError(f"{dataset_id} 事件为空或重复")
        seen.add(event_id)
        anchors = event.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            raise Z96PipelineError(f"{dataset_id}:{event_id} 缺锚")
        cited: list[str] = []
        for anchor in anchors:
            anchor_id = str(anchor.get("anchor_id") or "")
            if anchor_id not in catalog_map:
                raise Z96PipelineError(f"{dataset_id}:{event_id} 含目录外锚")
            if anchor.get("quote") != catalog_map[anchor_id]["quote"]:
                raise Z96PipelineError(f"{dataset_id}:{event_id} 锚短引漂移")
            if int(anchor.get("chapter")) != chapter:
                raise Z96PipelineError(f"{dataset_id}:{event_id} 章号漂移")
            cited.append(anchor_id)
        if len(cited) != len(set(cited)):
            raise Z96PipelineError(f"{dataset_id}:{event_id} 锚重复")
        result.append(
            {
                "case_id": f"{dataset_id}:{event_id}",
                "event_id": event_id,
                "event_text": event_text,
                "cited_anchor_ids": cited,
            }
        )
    return result


def _dataset(
    reader: BootstrapReader,
    *,
    dataset_id: str,
    chapter: int,
    body_path: str,
    catalog_path: str,
    events_path: str,
) -> dict[str, Any]:
    body = reader.text(
        body_path,
        expected_sha256=EXPECTED_SHA256[body_path],
        phase="source_only_before_candidate",
    )
    catalog_data = reader.json(
        catalog_path,
        expected_sha256=EXPECTED_SHA256[catalog_path],
        phase="source_only_before_candidate",
        answer_derived=False,
    )
    events_data = reader.json(
        events_path,
        expected_sha256=EXPECTED_SHA256[events_path],
        phase="source_only_before_candidate",
        answer_derived=False,
    )
    catalog = _catalog_entries(catalog_data, body, chapter)
    return {
        "dataset_id": dataset_id,
        "chapter": chapter,
        "source": {
            "body_path": body_path,
            "body_sha256": EXPECTED_SHA256[body_path],
            "catalog_path": catalog_path,
            "catalog_sha256": EXPECTED_SHA256[catalog_path],
            "events_path": events_path,
            "events_sha256": EXPECTED_SHA256[events_path],
        },
        "catalog_entries": catalog,
        "cases": _validate_events(
            events_data,
            dataset_id=dataset_id,
            chapter=chapter,
            catalog=catalog,
        ),
    }


def _build_generation_cases(reader: BootstrapReader) -> dict[str, Any]:
    datasets = [
        _dataset(
            reader,
            dataset_id="X04",
            chapter=46,
            body_path=X04_BODY,
            catalog_path=X04_CATALOG,
            events_path=X04_SAMPLE,
        ),
        *[
            _dataset(
                reader,
                dataset_id=f"RETRY03-C{chapter:04d}",
                chapter=chapter,
                body_path=RETRY03_BODIES[chapter],
                catalog_path=RETRY03_CATALOGS[chapter],
                events_path=RETRY03_EVENTS[chapter],
            )
            for chapter in (3, 13, 19)
        ],
        _dataset(
            reader,
            dataset_id="Z89",
            chapter=3,
            body_path=Z89_BODY,
            catalog_path=Z89_CATALOG,
            events_path=Z89_EVENTS,
        ),
    ]
    return {
        "schema_version": "z96-r02-generation-cases-v1",
        "status": "PASS",
        "answer_sources_read": 0,
        "datasets": datasets,
    }


def _usage_lines(data: bytes) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in data.decode("utf-8").splitlines()
        if line.strip()
    ]


def _calibration_sample(
    *,
    sample_id: str,
    source_group: str,
    request_path: str,
    request_data: bytes,
    request_expected_sha: str,
    usage_source_path: str,
    usage_source_sha: str,
    prompt_tokens: int,
) -> dict[str, Any]:
    actual = hashlib.sha256(request_data).hexdigest()
    if actual != request_expected_sha:
        raise Z96PipelineError(
            f"token 校准请求 SHA 不匹配：{request_path} expected={request_expected_sha} actual={actual}"
        )
    request = json.loads(request_data.decode("utf-8"))
    messages = request.get("body", {}).get("messages")
    if not isinstance(messages, list) or not messages:
        raise Z96PipelineError(f"token 校准请求缺 messages：{request_path}")
    return {
        "sample_id": sample_id,
        "source_group": source_group,
        "request_path": request_path,
        "request_sha256": actual,
        "usage_source_path": usage_source_path,
        "usage_source_sha256": usage_source_sha,
        "prompt_tokens": prompt_tokens,
        "messages": messages,
    }


def _read_calibration_file(
    reader: BootstrapReader,
    relative: str,
    *,
    expected_sha: str,
) -> bytes:
    return reader.bytes(
        relative,
        expected_sha256=expected_sha,
        phase="token_calibration_before_candidate",
        answer_derived=False,
    )


def _build_calibration_bundle(reader: BootstrapReader) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    tokenizer_modules = (
        "tiktoken",
        "tokenizers",
        "transformers",
        "sentencepiece",
        "mlx_lm",
    )
    tokenizer_probe = {
        "checked_modules": [
            {
                "module": module,
                "available": importlib.util.find_spec(module) is not None,
            }
            for module in tokenizer_modules
        ],
        "provider_exact_v4_tokenizer_available": False,
        "decision": "no_auditable_exact_v4_tokenizer_use_sealed_usage_bound",
        "boundary": (
            "通用分词库即使存在也不能单独证明其词表与供应商 DeepSeek V4 "
            "线上计费 tokenizer 完全一致；本轮只接受可证明的精确 tokenizer。"
        ),
    }

    retry03_usage_path = f"{RETRY03_ROOT}/main/usage.jsonl"
    retry03_usage_sha = CALIBRATION_USAGE_SHA256[retry03_usage_path]
    retry03_usage = _usage_lines(
        _read_calibration_file(
            reader,
            retry03_usage_path,
            expected_sha=retry03_usage_sha,
        )
    )
    if len(retry03_usage) != 3:
        raise Z96PipelineError("retry03 token usage 不是3行")
    for chapter, row in zip((3, 13, 19), retry03_usage, strict=True):
        request_path = (
            f"{RETRY03_ROOT}/main/requests/neutral_extract/"
            f"z83_main_ch{chapter:04d}_request.json"
        )
        request_sha = str(row["request_sha256"])
        request_data = _read_calibration_file(
            reader,
            request_path,
            expected_sha=request_sha,
        )
        samples.append(
            _calibration_sample(
                sample_id=f"retry03-ch{chapter:04d}",
                source_group="retry03_main",
                request_path=request_path,
                request_data=request_data,
                request_expected_sha=request_sha,
                usage_source_path=retry03_usage_path,
                usage_source_sha=retry03_usage_sha,
                prompt_tokens=int(row["usage"]["prompt_tokens"]),
            )
        )

    z89_usage_path = f"{Z89_ROOT}/main/usage.jsonl"
    z89_usage_sha = CALIBRATION_USAGE_SHA256[z89_usage_path]
    z89_usage = _usage_lines(
        _read_calibration_file(reader, z89_usage_path, expected_sha=z89_usage_sha)
    )
    if len(z89_usage) != 1:
        raise Z96PipelineError("Z89 token usage 不是1行")
    z89_request_path = f"{Z89_ROOT}/main/requests/z89_ch0003_request.json"
    z89_request_sha = str(z89_usage[0]["request_artifact_sha256"])
    z89_request_data = _read_calibration_file(
        reader,
        z89_request_path,
        expected_sha=z89_request_sha,
    )
    samples.append(
        _calibration_sample(
            sample_id="z89-ch0003",
            source_group="z89_pro",
            request_path=z89_request_path,
            request_data=z89_request_data,
            request_expected_sha=z89_request_sha,
            usage_source_path=z89_usage_path,
            usage_source_sha=z89_usage_sha,
            prompt_tokens=int(z89_usage[0]["usage"]["prompt_tokens"]),
        )
    )

    repair_usage_path = f"{RETRY13_ROOT}/repair/usage.jsonl"
    repair_usage_sha = CALIBRATION_USAGE_SHA256[repair_usage_path]
    repair_usage = _usage_lines(
        _read_calibration_file(
            reader,
            repair_usage_path,
            expected_sha=repair_usage_sha,
        )
    )
    if len(repair_usage) != 32:
        raise Z96PipelineError("retry13 repair token usage 不是32行")
    for row in repair_usage:
        logical_id = str(row["logical_request_id"])
        request_path = (
            f"{RETRY13_ROOT}/repair/requests/single_object/"
            f"z83r13-{logical_id}_request.json"
        )
        request_sha = str(row["request_artifact_sha256"])
        request_data = _read_calibration_file(
            reader,
            request_path,
            expected_sha=request_sha,
        )
        samples.append(
            _calibration_sample(
                sample_id=f"retry13-repair-{logical_id}",
                source_group="retry13_repair",
                request_path=request_path,
                request_data=request_data,
                request_expected_sha=request_sha,
                usage_source_path=repair_usage_path,
                usage_source_sha=repair_usage_sha,
                prompt_tokens=int(row["usage"]["prompt_tokens"]),
            )
        )

    for chapter in (3, 13, 19):
        base = f"{RETRY13_ROOT}/final_review/inspector/ch{chapter:04d}/run"
        usage_path = f"{base}/checkpoint/03_usage.json"
        usage_sha = CALIBRATION_USAGE_SHA256[usage_path]
        usage_data = json.loads(
            _read_calibration_file(
                reader,
                usage_path,
                expected_sha=usage_sha,
            ).decode("utf-8")
        )
        logical_id = str(usage_data["logical_request_id"])
        request_path = f"{base}/requests/semantic_route/{logical_id}_request.json"
        request_sha = str(usage_data["request_artifact_sha256"])
        request_data = _read_calibration_file(
            reader,
            request_path,
            expected_sha=request_sha,
        )
        samples.append(
            _calibration_sample(
                sample_id=f"retry13-inspector-ch{chapter:04d}",
                source_group="retry13_inspector",
                request_path=request_path,
                request_data=request_data,
                request_expected_sha=request_sha,
                usage_source_path=usage_path,
                usage_source_sha=usage_sha,
                prompt_tokens=int(usage_data["usage"]["prompt_tokens"]),
            )
        )

    if len(samples) != 39:
        raise Z96PipelineError(f"token 校准样本不是39：{len(samples)}")
    return {
        "schema_version": "z96-r02-token-calibration-bundle-v1",
        "status": "PASS",
        "tokenizer_probe": tokenizer_probe,
        "samples": samples,
    }


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _sandbox_profile(outbox: Path) -> str:
    escaped = str(outbox.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    return "\n".join(
        [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f'(allow file-write* (subpath "{escaped}"))',
            '(allow file-write* (literal "/dev/null"))',
            "",
        ]
    )


def _run_stage(
    pass_root: Path,
    *,
    stage: str,
    inputs: dict[str, Path],
) -> tuple[Path, Path]:
    stage_root = pass_root / "stages" / stage
    inbox = stage_root / "inbox"
    outbox = stage_root / "outbox"
    inbox.mkdir(parents=True, exist_ok=False)
    for name, source in sorted(inputs.items()):
        _copy_file(source, inbox / name)
    profile = _sandbox_profile(outbox)
    profile_path = stage_root / "sandbox_profile.sb"
    profile_path.write_text(profile, encoding="utf-8")
    command = [
        "/usr/bin/sandbox-exec",
        "-f",
        str(profile_path),
        str(REPO_ROOT / ".venv/bin/python"),
        "-m",
        f"{PACKAGE}.stage_runtime",
        "--stage",
        stage,
        "--inbox",
        str(inbox),
        "--outbox",
        str(outbox),
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    write_json(
        stage_root / "subprocess_receipt.json",
        {
            "schema_version": "z96-r02-stage-subprocess-receipt-v1",
            "stage": stage,
            "sandbox_exec": True,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "network_allowed": False,
        },
    )
    if completed.returncode != 0:
        raise Z96PipelineError(
            f"阶段 {stage} 失败：{completed.stderr or completed.stdout}"
        )
    receipt = read_json(outbox / "stage_receipt.json")
    if receipt.get("stage") != stage:
        raise Z96PipelineError(f"阶段 {stage} 回执身份不符")
    output_path = outbox / receipt["output"]["name"]
    if sha256_file(output_path) != receipt["output"]["sha256"]:
        raise Z96PipelineError(f"阶段 {stage} 输出 SHA 与回执不符")
    return output_path, outbox / "stage_receipt.json"


def _copy_answer_sources_after_candidate(
    reader: BootstrapReader,
    target: Path,
    *,
    candidate_path: Path,
) -> dict[str, Path]:
    candidate_sha = sha256_file(candidate_path)
    reader.milestone(
        "candidate_frozen_before_answer_reads",
        candidate_sha256=candidate_sha,
    )
    x04_data = reader.bytes(
        X04_LEDGER,
        expected_sha256=EXPECTED_SHA256[X04_LEDGER],
        phase="answer_only_after_candidate",
        answer_derived=True,
    )
    z89_data = reader.bytes(
        Z89_ADJUDICATION,
        expected_sha256=EXPECTED_SHA256[Z89_ADJUDICATION],
        phase="answer_only_after_candidate",
        answer_derived=True,
    )
    target.mkdir(parents=True, exist_ok=False)
    x04_path = target / "x04_human_ledger.json"
    z89_path = target / "z89_adjudication.json"
    x04_path.write_bytes(x04_data)
    z89_path.write_bytes(z89_data)
    if sha256_file(candidate_path) != candidate_sha:
        raise Z96PipelineError("复制评分答案后冻结候选发生漂移")
    reader.milestone(
        "answer_sources_copied_candidate_unchanged",
        candidate_sha256=candidate_sha,
    )
    return {
        "x04_human_ledger.json": x04_path,
        "z89_adjudication.json": z89_path,
    }


def _build_canaries() -> dict[str, Any]:
    def candidate(case_id: str, selected: list[str], order: list[str]) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "candidate_anchor_ids": selected,
            "catalog_order": order,
        }

    rows = [
        {
            "case_id": "CANARY-A-01-HALF",
            "result": score_recall(
                candidate("CANARY-A-01-HALF", ["E0001"], ["E0001", "E0002"]),
                {"required_anchor_ids": ["E0001", "E0002"]},
            ),
            "expected": "REJECT",
        },
        {
            "case_id": "CANARY-A-02-ONE-INTERIOR",
            "result": score_recall(
                candidate(
                    "CANARY-A-02-ONE-INTERIOR",
                    ["E0001", "E0003"],
                    ["E0001", "E0002", "E0003"],
                ),
                {"required_anchor_ids": ["E0001", "E0002", "E0003"]},
            ),
            "expected": "REJECT",
        },
        {
            "case_id": "CANARY-A-02-MULTI-INTERIOR",
            "result": score_recall(
                candidate(
                    "CANARY-A-02-MULTI-INTERIOR",
                    ["E0001", "E0005"],
                    ["E0001", "E0002", "E0003", "E0004", "E0005"],
                ),
                {
                    "required_anchor_ids": [
                        "E0001",
                        "E0002",
                        "E0003",
                        "E0004",
                        "E0005",
                    ]
                },
            ),
            "expected": "REJECT",
        },
        {
            "case_id": "CANARY-A-02-ID-ORDER-MISMATCH",
            "result": score_recall(
                candidate(
                    "CANARY-A-02-ID-ORDER-MISMATCH",
                    ["E0009", "E0008"],
                    ["E0009", "E0001", "E0008"],
                ),
                {"required_anchor_ids": ["E0009", "E0001", "E0008"]},
            ),
            "expected": "REJECT",
        },
        {
            "case_id": "CANARY-COMPLETE",
            "result": score_recall(
                candidate(
                    "CANARY-COMPLETE",
                    ["E0001", "E0002", "E0003"],
                    ["E0001", "E0002", "E0003"],
                ),
                {"required_anchor_ids": ["E0001", "E0002", "E0003"]},
            ),
            "expected": "PASS",
        },
    ]
    checks = []
    for row in rows:
        checks.append(
            row["result"]["status"] == row["expected"]
            and (
                row["case_id"] in {"CANARY-A-01-HALF", "CANARY-COMPLETE"}
                or bool(row["result"]["endpoint_span_pattern"])
            )
        )
    return {
        "schema_version": "z96-r02-canary-receipt-v1",
        "status": "PASS" if all(checks) else "REJECT",
        "rows": rows,
        "checks_passed": sum(checks),
        "checks_total": len(checks),
    }


def _artifact_rows(root: Path, *, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude_names or set()
    rows = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix()
        if path.name in excluded or relative.endswith("/sandbox_profile.sb"):
            continue
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def _tree_fingerprint(relative_paths: Iterable[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in sorted(set(relative_paths)):
        path = REPO_ROOT / relative
        if path.is_file():
            rows.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        elif path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                child_relative = child.relative_to(REPO_ROOT).as_posix()
                rows.append(
                    {
                        "path": child_relative,
                        "bytes": child.stat().st_size,
                        "sha256": sha256_file(child),
                    }
                )
        else:
            raise Z96PipelineError(f"保护路径不存在：{relative}")
    return {
        "file_count": len(rows),
        "summary_sha256": sha256_bytes(stable_json_bytes(rows)),
        "rows": rows,
    }


def _assert_output_path_allowed(run_dir: Path) -> None:
    output = run_dir.resolve()
    authorized = (REPO_ROOT / AUTHORIZED_RUN_DIRECTORY).resolve()
    if output != authorized:
        raise Z96PipelineError(
            "运行目录不在本令精确白名单："
            f"expected={authorized} actual={output}"
        )
    for relative in PROTECTED_PATHS:
        protected = (REPO_ROOT / relative).resolve()
        if output == protected or output.is_relative_to(protected):
            raise Z96PipelineError(f"输出目录落入保护路径：{relative}")
    if output.exists():
        raise Z96PipelineError(f"运行目录已存在，拒绝覆盖：{output}")


def _pass_summary(
    *,
    pass_root: Path,
    candidate_path: Path,
    score_path: Path,
    render_audit_path: Path,
    token_contract_path: Path,
    claims_path: Path,
    expectations_path: Path,
    answers_path: Path,
    bootstrap: BootstrapReader,
) -> dict[str, Any]:
    candidates = read_json(candidate_path)
    score = read_json(score_path)
    render_audit_data = read_json(render_audit_path)
    token_contract = read_json(token_contract_path)
    token_values = [
        int(row["token_upper_bound"]["token_upper_bound"])
        for row in candidates["cases"]
    ]
    median = nearest_rank_percentile(token_values, 0.5)
    p95 = nearest_rank_percentile(token_values, 0.95)
    canaries = _build_canaries()
    write_json(pass_root / "canary_receipt.json", canaries)
    claim_sha = sha256_file(claims_path)
    expectation_sha = sha256_file(expectations_path)
    answer_sha = sha256_file(answers_path)
    candidate_bytes = candidate_path.read_bytes()
    score_only_canary_absent = b"SCORE-ONLY-CANARY-Z96-R02-7F3D1A" not in candidate_bytes
    answer_reads = [row for row in bootstrap.rows if row["answer_derived"]]
    milestone = next(
        row
        for row in bootstrap.milestones
        if row["name"] == "candidate_frozen_before_answer_reads"
    )
    answers_after_candidate = bool(answer_reads) and all(
        row["sequence"] > milestone["sequence"] for row in answer_reads
    )
    three_shas_distinct = len({claim_sha, expectation_sha, answer_sha}) == 3
    checks = {
        "model_api_calls_zero": True,
        "network_attempts_zero": True,
        "candidate_before_answer_reads": answers_after_candidate,
        "candidate_has_no_score_only_canary": score_only_canary_absent,
        "three_frozen_material_shas_distinct": three_shas_distinct,
        "token_calibration_39_of_39": (
            token_contract["calibration"]["samples"] == 39
            and token_contract["calibration"]["covered_samples"] == 39
        ),
        "tokenizer_route_is_audited": (
            token_contract["tokenizer_probe"]["decision"]
            == "no_auditable_exact_v4_tokenizer_use_sealed_usage_bound"
            and token_contract["tokenizer_probe"][
                "provider_exact_v4_tokenizer_available"
            ]
            is False
        ),
        "token_upper_bound_median_lte_2500": median <= 2500,
        "token_upper_bound_p95_lte_4000": p95 <= 4000,
        "independent_missing_span_recall_100_percent": (
            score["independent_missing_span"]["recall"] == 1.0
        ),
        "x04_occurrences_exactly_85": (
            score["x04_disposition"]["occurrence_denominator"] == 85
            and len(score["x04_disposition"]["rows"]) == 85
            and score["x04_disposition"]["unresolved"] == 0
        ),
        "x04_status_only_pass_reject": all(
            row["status"] in {"PASS", "REJECT"}
            for row in score["x04_disposition"]["rows"]
        ),
        "render_audit_pass": render_audit_data["status"] == "PASS",
        "canaries_pass": canaries["status"] == "PASS",
    }
    summary = {
        "schema_version": "z96-r02-pass-summary-v1",
        "status": "PASS" if all(checks.values()) else "REJECT",
        "checks": checks,
        "counts": {
            "candidate_cases": len(candidates["cases"]),
            "score_cases": len(score["cases"]),
            "x04_missing_occurrences": len(score["x04_disposition"]["rows"]),
        },
        "token_upper_bound": {
            "route": token_contract["route"],
            "not_actual_token_count": True,
            "median": median,
            "p95_nearest_rank": p95,
            "maximum": max(token_values),
        },
        "independent_frozen_materials": {
            "atomic_claims_sha256": claim_sha,
            "scoring_answers_sha256": answer_sha,
            "render_expectations_sha256": expectation_sha,
            "all_distinct": three_shas_distinct,
        },
        "usage": {
            "model_api_logical_samples": 0,
            "model_api_network_attempts": 0,
            "model_api_usage_tokens": 0,
        },
        "quality_boundary": (
            "只证明独立召回覆盖冻结缺锚、渲染不增删和经验token上界过闸；"
            "新增候选锚的逐主张语义精度未被本轮人工全标，不冒充正式准确率。"
        ),
    }
    write_json(pass_root / "pass_summary.json", summary)
    write_json(
        pass_root / "bootstrap_read_ledger.json",
        {
            "schema_version": "z96-r02-bootstrap-read-ledger-v1",
            "status": "PASS" if answers_after_candidate else "REJECT",
            "rows": bootstrap.rows,
            "milestones": bootstrap.milestones,
        },
    )
    manifest_rows = _artifact_rows(
        pass_root,
        exclude_names={"pass_manifest.json"},
    )
    write_json(
        pass_root / "pass_manifest.json",
        {
            "schema_version": "z96-r02-pass-manifest-v1",
            "files": manifest_rows,
            "manifest_excludes_itself": True,
        },
    )
    if summary["status"] != "PASS":
        raise Z96PipelineError("r02 pass 硬闸未全过")
    return summary


def _run_pass(pass_root: Path) -> dict[str, Any]:
    pass_root.mkdir(parents=True, exist_ok=False)
    bootstrap = BootstrapReader()

    generation = _build_generation_cases(bootstrap)
    bootstrap_dir = pass_root / "bootstrap"
    generation_path = bootstrap_dir / "generation_cases.json"
    write_json(generation_path, generation)

    calibration = _build_calibration_bundle(bootstrap)
    calibration_path = bootstrap_dir / "calibration_bundle.json"
    write_json(calibration_path, calibration)

    token_contract_path, _ = _run_stage(
        pass_root,
        stage="token_calibration",
        inputs={"calibration_bundle.json": calibration_path},
    )
    claims_path, _ = _run_stage(
        pass_root,
        stage="freeze_claims",
        inputs={"generation_cases.json": generation_path},
    )
    expectations_path, _ = _run_stage(
        pass_root,
        stage="freeze_render_expectations",
        inputs={"generation_cases.json": generation_path},
    )
    candidate_path, _ = _run_stage(
        pass_root,
        stage="candidate",
        inputs={
            "generation_cases.json": generation_path,
            "atomic_claims.json": claims_path,
            "token_bound_contract.json": token_contract_path,
        },
    )
    bootstrap.milestone(
        "candidate_stage_completed",
        candidate_sha256=sha256_file(candidate_path),
    )
    render_path, _ = _run_stage(
        pass_root,
        stage="render",
        inputs={
            "atomic_claims.json": claims_path,
            "frozen_candidates.json": candidate_path,
        },
    )

    answer_inputs = _copy_answer_sources_after_candidate(
        bootstrap,
        pass_root / "answer_bootstrap",
        candidate_path=candidate_path,
    )
    answers_path, _ = _run_stage(
        pass_root,
        stage="freeze_scores",
        inputs=answer_inputs,
    )
    score_path, _ = _run_stage(
        pass_root,
        stage="score",
        inputs={
            "frozen_candidates.json": candidate_path,
            "scoring_answers.json": answers_path,
        },
    )
    render_audit_path, _ = _run_stage(
        pass_root,
        stage="render_audit",
        inputs={
            "frozen_render.json": render_path,
            "render_expectations.json": expectations_path,
        },
    )
    return _pass_summary(
        pass_root=pass_root,
        candidate_path=candidate_path,
        score_path=score_path,
        render_audit_path=render_audit_path,
        token_contract_path=token_contract_path,
        claims_path=claims_path,
        expectations_path=expectations_path,
        answers_path=answers_path,
        bootstrap=bootstrap,
    )


def _normalized_business_rows(pass_root: Path) -> list[dict[str, Any]]:
    excluded_names = {
        "sandbox_profile.sb",
        "pass_manifest.json",
        "subprocess_receipt.json",
    }
    rows = _artifact_rows(pass_root, exclude_names=excluded_names)
    return rows


def _post_output_protection_receipt(
    protection_before: dict[str, Any],
) -> dict[str, Any]:
    try:
        protection_after = _tree_fingerprint(PROTECTED_PATHS)
    except (OSError, Z96PipelineError) as exc:
        return {
            "schema_version": "z96-r02-post-output-protection-receipt-v1",
            "status": "REJECT",
            "checked_after_run_outputs_completed": True,
            "protected_paths": list(PROTECTED_PATHS),
            "before_summary_sha256": protection_before["summary_sha256"],
            "before_file_count": protection_before["file_count"],
            "after_fingerprint_error": str(exc),
            "unchanged": False,
        }
    unchanged = (
        protection_before["summary_sha256"] == protection_after["summary_sha256"]
        and protection_before["file_count"] == protection_after["file_count"]
    )
    return {
        "schema_version": "z96-r02-post-output-protection-receipt-v1",
        "status": "PASS" if unchanged else "REJECT",
        "checked_after_run_outputs_completed": True,
        "protected_paths": list(PROTECTED_PATHS),
        "before_summary_sha256": protection_before["summary_sha256"],
        "after_summary_sha256": protection_after["summary_sha256"],
        "file_count_before": protection_before["file_count"],
        "file_count_after": protection_after["file_count"],
        "unchanged": unchanged,
    }


def _execute_build(
    run_dir: Path,
    protection_before: dict[str, Any],
) -> dict[str, Any]:
    pass1_summary = _run_pass(run_dir / "pass1")
    pass2_summary = _run_pass(run_dir / "pass2")
    pass1_rows = _normalized_business_rows(run_dir / "pass1")
    pass2_rows = _normalized_business_rows(run_dir / "pass2")
    path_match = [row["path"] for row in pass1_rows] == [
        row["path"] for row in pass2_rows
    ]
    byte_match = path_match and all(
        left["sha256"] == right["sha256"] and left["bytes"] == right["bytes"]
        for left, right in zip(pass1_rows, pass2_rows, strict=True)
    )
    double_run = {
        "schema_version": "z96-r02-double-run-receipt-v1",
        "status": "PASS" if byte_match else "REJECT",
        "pass1_business_files": len(pass1_rows),
        "pass2_business_files": len(pass2_rows),
        "paths_identical": path_match,
        "bytes_identical": byte_match,
        "pass1_rows": pass1_rows,
        "pass2_rows": pass2_rows,
    }
    write_json(run_dir / "double_run_receipt.json", double_run)
    if not byte_match:
        raise Z96PipelineError("r02 双生成逐文件字节不一致")

    protection_receipt = _post_output_protection_receipt(protection_before)
    write_json(run_dir / "post_output_protection_receipt.json", protection_receipt)
    if protection_receipt["status"] != "PASS":
        raise Z96PipelineError("r02 正式输出后保护面指纹漂移")

    final_summary = {
        "schema_version": "z96-r02-final-summary-v1",
        "status": (
            "PASS"
            if pass1_summary["status"] == pass2_summary["status"] == "PASS"
            and double_run["status"] == "PASS"
            and protection_receipt["status"] == "PASS"
            else "REJECT"
        ),
        "authority_time": AUTHORITY_TIME,
        "first_run_artifacts_reused": False,
        "first_run_conclusions_reused": False,
        "model_api_calls": 0,
        "network_attempts": 0,
        "pass1": pass1_summary,
        "pass2": pass2_summary,
        "double_run": {
            "status": double_run["status"],
            "business_files": len(pass1_rows),
        },
        "post_output_protection": {
            "status": protection_receipt["status"],
            "unchanged": protection_receipt["unchanged"],
        },
        "release_boundary": (
            "候选银标；不接运行器、不固化、不升默认、不写outbox。"
        ),
    }
    write_json(run_dir / "final_summary.json", final_summary)
    return {
        "final_summary": final_summary,
        "double_run": double_run,
        "protection": protection_receipt,
    }


def build(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    _assert_output_path_allowed(run_dir)
    protection_before = _tree_fingerprint(PROTECTED_PATHS)
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        run_dir / "run_identity.json",
        {
            "schema_version": "z96-r02-run-identity-v1",
            "run_id": "Z96-r02",
            "authority_time": AUTHORITY_TIME,
            "authorized_run_directory": AUTHORIZED_RUN_DIRECTORY,
            "model_api_calls_allowed": 0,
        },
    )
    write_json(run_dir / "protection_before.json", protection_before)
    try:
        return _execute_build(run_dir, protection_before)
    except Exception as exc:
        protection_path = run_dir / "post_output_protection_receipt.json"
        if protection_path.exists():
            protection_receipt = read_json(protection_path)
        else:
            protection_receipt = _post_output_protection_receipt(
                protection_before
            )
            write_json(protection_path, protection_receipt)
        write_json(
            run_dir / "hard_stop.json",
            {
                "schema_version": "z96-r02-hard-stop-v1",
                "status": "REJECT",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "model_api_calls": 0,
                "network_attempts": 0,
                "in_place_rerun_allowed": False,
                "post_output_protection_status": protection_receipt["status"],
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.run_dir)
    except (OSError, KeyError, TypeError, ValueError, Z96CoreError) as exc:
        raise Z96PipelineError(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
