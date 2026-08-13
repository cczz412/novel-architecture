#!/usr/bin/env python3
"""Reuse frozen same-case/same-fact M1 decisions and record the 17 new judgments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
RUN = REPO / "runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_MATCHED_LORA_DEMO_R01"
QUEUE = RUN / "scoring/pre_auto/BLIND_QUEUE.jsonl"
RAW = RUN / "scoring/RAW_OUTPUTS_3X24.jsonl"
OLD = REPO / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/m1_r01/semantic_scoring_r01/M1_RECOVERED_PREDICTION_DECISIONS_1014.jsonl"
OUTPUT = RUN / "scoring/SEMANTIC_ADJUDICATIONS.jsonl"


MANUAL = {
    ("MICRO24B-S01", "黎舟更换了巡逻艇的断裂系缆。"): (None, "将浮标系缆错写成巡逻艇的系缆。"),
    ("MICRO24B-S02", "穆青正在修复一个瓷瓶。"): (None, "没有保留粘合碎片和修复尚未结束两个关键边界。"),
    ("MICRO24B-S03", "阿澈决定改乘渡船去南岸。"): (None, "别名可识别，但丢失明早这一时间条件。"),
    ("MICRO24B-S03", "安澈决定改乘渡船去南岸。"): (None, "主体正确，但丢失明早这一时间条件。"),
    ("MICRO24B-S04", "秦柔承诺在今晚十二点前亲自向伤员家属告知手术结果。"): ("MICRO24B-S04-F01", "与金标语义等价。"),
    ("MICRO24B-S12", "顾棠误以为阿洛把装有头冠的木箱搬去了后门。"): ("MICRO24B-S12-F01", "与金标语义等价。"),
    ("MICRO24B-S12", "道具师顾棠误以为学徒阿洛把头冠木箱搬去了后门。"): ("MICRO24B-S12-F01", "与金标语义等价。"),
    ("MICRO24B-S13", "检疫官许琛发现货箱中有活体甲虫。"): ("MICRO24B-S13-F01", "与金标语义等价。"),
    ("MICRO24B-S15", "住客蒋禾认为隔壁房客偷偷烧纸造成了烟味。"): ("MICRO24B-S15-F03", "保留了蒋禾的归因认定；误信类型另在 status 层计分。"),
    ("MICRO24B-S15", "住客蒋禾认定是隔壁房客偷偷烧纸造成的。"): ("MICRO24B-S15-F03", "与金标事实核心语义等价。"),
    ("MICRO24B-S18", "领航员季遥推测三次绿色闪光来自无人机。"): ("MICRO24B-S18-F01", "与金标语义等价。"),
    ("MICRO24B-S18", "地面观察员陶麦误以为三次绿色闪光是失联队员韩旻发出的信号。"): ("MICRO24B-S18-F02", "与金标语义等价。"),
    ("MICRO24B-S21", "南湖变电站凌晨两点自动跳闸。"): ("MICRO24B-S21-F01", "与金标语义等价。"),
    ("MICRO24B-S21", "调度员江策表示，若负荷回落至百分之八十以下，备用线路将重新并网。"): ("MICRO24B-S21-F03", "与金标条件事实语义等价。"),
    ("MICRO24B-S22", "医官柳澄计划用银针检验剩余药液。"): ("MICRO24B-S22-F01", "与金标事实核心语义等价。"),
    ("MICRO24B-S22", "侍女春绫误以为蓝釉药瓶里的药是毒物。"): ("MICRO24B-S22-F03", "与金标误信事实语义等价。"),
    ("MICRO24B-S22", "侍女春绫误以为蓝釉药瓶中的药是毒物。"): ("MICRO24B-S22-F03", "与金标误信事实语义等价。"),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    raw_sha = hashlib.sha256(RAW.read_bytes()).hexdigest()
    old = {}
    for row in read_jsonl(OLD):
        if row.get("split") != "dev24" or not isinstance(row.get("prediction", {}).get("fact"), str):
            continue
        key = (row["case_id"], row["prediction"]["fact"])
        value = (row.get("counts_as_tp") is True, row.get("matched_gold_fact_id"))
        if key in old and old[key] != value:
            raise RuntimeError(f"OLD_DECISION_CONFLICT:{key}")
        old[key] = value
    output = []
    reused = manual = 0
    for row in read_jsonl(QUEUE):
        key = (row["case_id"], row["prediction_fact"])
        if key in old:
            passed, fact_id = old[key]
            reason = "复用冻结 M1 同题同事实字符串的独立语义裁决。"
            source = "REUSED_FROZEN_M1_SAME_CASE_SAME_FACT"
            reused += 1
        elif key in MANUAL:
            fact_id, reason = MANUAL[key]
            passed = fact_id is not None
            source = "WO01_MATCHED_LORA_NEW_SAME_CASE_REVIEW"
            manual += 1
        else:
            raise RuntimeError(f"UNADJUDICATED_FACT:{key}")
        output.append(
            {
                **row,
                "category": "SEMANTIC_EQUIVALENT" if passed else "NOT_MATCH",
                "matched_gold_fact_id": fact_id,
                "counts_as_tp": passed,
                "reason": reason,
                "source": source,
                "reviewer": "Codex",
            }
        )
    with OUTPUT.open("x", encoding="utf-8") as handle:
        for row in output:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS_ALL_BLIND_CANDIDATES_ADJUDICATED", "rows": len(output), "reused": reused, "new_review": manual, "raw_sha256": raw_sha}, ensure_ascii=False))


if __name__ == "__main__":
    main()
