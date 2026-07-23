#!/usr/bin/env python3
"""机械检查中性事件 JSON。

能检查结构、编号、anchor_id、重复和若干句式风险；不能证明小说语义正确。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VAGUE_PATTERNS = [
    r"确定了计划",
    r"发生了变化",
    r"进行了处理",
    r"想了想",
    r"有所行动",
    r"将心思转移",
]
PRONOUN_START = re.compile(r"^(他|她|其|对方|这件事|那里|随后|之后|接着)")


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--anchors', required=True)
    ap.add_argument('--chapter', required=True, type=int)
    args = ap.parse_args()

    errors: list[str] = []
    output = json.loads(Path(args.output).read_text(encoding='utf-8'))
    anchors = json.loads(Path(args.anchors).read_text(encoding='utf-8'))
    valid_anchor_ids = {x['anchor_id'] for x in anchors}

    if set(output) != {'schema_version', 'chapter', 'events'}:
        fail(f'顶层字段必须且只能是 schema_version/chapter/events，实际为 {sorted(output)}', errors)
    if output.get('schema_version') != 'z-event-v1':
        fail('schema_version 必须为 z-event-v1', errors)
    if output.get('chapter') != args.chapter:
        fail(f'chapter 必须为 {args.chapter}', errors)
    events = output.get('events')
    if not isinstance(events, list):
        fail('events 必须是数组', errors)
        events = []

    seen_events: set[str] = set()
    for idx, ev in enumerate(events, 1):
        expected_id = f'EV-C{args.chapter:04d}-{idx:02d}'
        if set(ev) != {'event_id', 'event', 'anchors'}:
            fail(f'{expected_id}: 字段必须且只能是 event_id/event/anchors', errors)
        if ev.get('event_id') != expected_id:
            fail(f'第{idx}条 event_id 应为 {expected_id}，实际为 {ev.get("event_id")}', errors)
        sentence = ev.get('event')
        if not isinstance(sentence, str) or not sentence.strip():
            fail(f'{expected_id}: event 必须是非空字符串', errors)
            continue
        sentence = sentence.strip()
        if len(sentence) < 12:
            fail(f'{expected_id}: event 过短，疑似事实头而非完整陈述', errors)
        if PRONOUN_START.search(sentence):
            fail(f'{expected_id}: event 以代词或衔接词开头，缺独立主体', errors)
        for pat in VAGUE_PATTERNS:
            if re.search(pat, sentence):
                fail(f'{expected_id}: 命中空泛表达 {pat}', errors)
        if sentence in seen_events:
            fail(f'{expected_id}: event 与前文重复', errors)
        seen_events.add(sentence)

        ev_anchors = ev.get('anchors')
        if not isinstance(ev_anchors, list) or not ev_anchors:
            fail(f'{expected_id}: anchors 必须是非空数组', errors)
            continue
        ids: list[str] = []
        for a in ev_anchors:
            if not isinstance(a, dict) or set(a) != {'anchor_id'}:
                fail(f'{expected_id}: 每个 anchor 只能包含 anchor_id', errors)
                continue
            aid = a.get('anchor_id')
            ids.append(aid)
            if aid not in valid_anchor_ids:
                fail(f'{expected_id}: 无效 anchor_id {aid}', errors)
        if len(ids) != len(set(ids)):
            fail(f'{expected_id}: anchors 有重复 ID', errors)
        numeric = [int(x[1:]) for x in ids if isinstance(x, str) and re.fullmatch(r'E\d{4}', x)]
        if numeric != sorted(numeric):
            fail(f'{expected_id}: anchors 未按原文顺序排列', errors)

    if errors:
        print('FAIL')
        for e in errors:
            print('-', e)
        return 1
    print(f'PASS: {len(events)} 条事件，结构与 anchor_id 机械检查通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
