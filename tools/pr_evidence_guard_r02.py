# 执行身份：Codex
"""只核对可确定的段号与逐字引文；不靠词表判故事含义。"""
import re


def inspect(candidate, data):
    source = {p['paragraph_id']: p['text'] for p in data['paragraphs'] + data.get('context_paragraphs', [])}
    errors = []
    def check(pid, quote, item):
        if pid not in source:
            errors.append(dict(item=item, type='引用段号不在本次输入', paragraph_id=pid))
        elif not isinstance(quote, str) or not quote or quote not in source[pid]:
            errors.append(dict(item=item, type='引文不是所指段连续逐字子串', paragraph_id=pid))
    for row in candidate['B']:
        item = row['local_key']
        pids = []
        if not row.get('evidence'):
            errors.append(dict(item=item,type='事实缺少原文证据'))
        for evidence in row.get('evidence', []):
            pid = evidence.get('paragraph_id')
            pids.append(pid)
            check(pid, evidence.get('quote'), item)
        for match in re.findall(r'“([^”]+)”|「([^」]+)」|『([^』]+)』|"([^"\n]+)"',row.get('text','')):
            quote = next(x for x in match if x)
            if not any(quote in source.get(pid,'') for pid in pids):
                errors.append(dict(item=item,type='事实正文直引不是关联原段逐字子串'))
    for material in candidate['C']:
        for row in material['paragraphs']:
            pid = data['book_id'] + ':ch' + data['chapter'] + ':' + row['paragraph_id']
            check(pid,row.get('quote'),pid)
        for scene in material['scenes']:
            for field in ('location','light_weather','objects_visuals','sounds_smells','atmosphere'):
                for value in scene[field]:
                    for evidence in value.get('evidence',[]):
                        check(evidence.get('paragraph_id'),evidence.get('quote'),scene['scene_id']+':'+field)
    return errors
