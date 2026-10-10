# 执行身份：Codex
"""简化模型输入输出；程序只填写来源身份和明确去向，不默补事实。"""
import copy
import json
import re

from pr_pipeline_r02 import RULES, SYSTEM, dump, empty_result
from pr_ark_client_r02 import Client
from pr_shape_guard_r02 import TAGS

SCHEMA = '''本步处理本组事实与原文材料，不分类人物计划。只输出这七个数组：
{"keep":[],"exclude":[],"flag":[],"replace":[],"add":[],"paragraphs":[],"scenes":[]}。
keep、exclude、flag只列本组facts中的旧事实键：分别表示完整正确沿用、确认非故事内容排除、仍有疑问但正文保留。replace每项{key,text,reason,evidence:[{p,q}]}，key是本组旧键；add每项{text,reason,evidence:[{p,q}]}。一个旧键只出现一次。每个本组旧键必须明确归入上述四类之一；没问题的沿用，不借替换重写正确旧句。新事实只补本组责任段，read_only_context_facts只供查重，不能处置。
evidence中p是输入提供的段号，q是该段连续逐字短引。新句不编身份或版本，编号由程序分配。
paragraphs每项{id,main,secondary,viewpoint,quote,note}，仅包含owned_paragraph_ids内的段，每段一次；id可用输入完整段号或末尾短号。main只能取叙述带过、动作展开、对话、心理、场景，secondary为null或另一不同标签；viewpoint是感知者人物名、全知、切换或null。空副标签用null，不用无、空字符串、列表。quote是本段连续短引。
scenes每项{paragraph_ids,location:[],light_weather:[],objects_visuals:[],sounds_smells:[],atmosphere:[]}，段号仅本组责任段；每格每项{text,p,q}，p为来源段号，q为逐字短引。真实现场五格按原文摘取，没写为空，不填占位词；不能把动作、个人情绪或台词内容当环境格。
所有旧键、段号、正文都来自输入。跨段旧句保持完整，context_paragraphs只助消歧；不为上下文另增句或重复标C。不要输出A、书号、章号、变动编号、核对表或前章历史，这些由程序处理。理由简短具体，JSON完整结束。'''


def full_pid(pid, data):
    if not isinstance(pid, str):
        raise ValueError('段号必须是字符串')
    return data['book_id'] + ':ch' + data['chapter'] + ':' + pid if re.fullmatch(r'p\d+', pid) else pid


def compact_materials(data):
    value = copy.deepcopy(data)
    value['facts'] = [{k: f[k] for k in ('local_key', 'text', 'paragraph_ids')} for f in value['facts']]
    return value


def messages(data):
    return [dict(role='system', content=SYSTEM), dict(role='user', content=RULES + '\n' + SCHEMA +
            '\n输入材料：\n' + json.dumps(compact_materials(data), ensure_ascii=False, separators=(',', ':')))]


def decode(response, data=None):
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('输出未完整结束，不拼接截断正文')
    text = choice.get('message', {}).get('content') or ''
    text = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', text)
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError('顶层必须是对象')
    if data is not None:
        from pr_normalize_r03 import normalize
        obj, conversions = normalize(obj, data)
        obj['_deterministic_conversions'] = conversions
    for key in ('keep', 'exclude', 'flag', 'replace', 'add', 'paragraphs', 'scenes'):
        if not isinstance(obj.get(key), list):
            raise ValueError('字段' + key + '必须是数组')
    for key in ('keep', 'exclude', 'flag'):
        if any(not isinstance(v, str) for v in obj[key]):
            raise ValueError(key + '每项必须是旧键字符串')
    for key in ('replace', 'add', 'paragraphs', 'scenes'):
        if any(not isinstance(v, dict) for v in obj[key]):
            raise ValueError(key + '每项必须是对象')
    for key in ('replace', 'add'):
        for i, row in enumerate(obj[key]):
            if not isinstance(row.get('text'), str) or not isinstance(row.get('evidence'), list):
                raise ValueError(key + '[' + str(i) + ']须有正文和证据数组')
            if any(not isinstance(e, dict) or not isinstance(e.get('p'), str) or not isinstance(e.get('q'), str) for e in row['evidence']):
                raise ValueError(key + '[' + str(i) + ']证据须为{p:段号,q:逐字短引}对象')
    return obj


def convert(obj, data):
    candidate = empty_result()
    bid, chapter, group = data['book_id'], data['chapter'], data['group']
    issues = []
    expected = {f['local_key'] for f in data['facts']}
    seen = []
    for key in ('keep', 'exclude', 'flag'):
        seen.extend(obj[key])
    seen.extend(r.get('key') for r in obj['replace'])
    missing = sorted(expected - set(seen))
    extra = sorted(str(k) for k in set(seen) - expected)
    duplicate = sorted(str(k) for k in set(seen) if seen.count(k) > 1)
    if missing or extra or duplicate:
        issues.append(dict(type='旧句去向缺失、越界或重复', keys=missing + extra + duplicate))
    for operation, rows in (('替换', obj['replace']), ('新增', obj['add'])):
        for i, row in enumerate(rows):
            key = row.get('key') if operation == '替换' else data['new_key_prefix'] + str(i)
            if not key or operation == '替换' and key not in expected:
                raise ValueError('替换引用必须是本组明确旧键')
            candidate['B'].append(dict(change_id=f'PR:B:{bid}:{chapter}:g{group}:{operation}:{i}', book_id=bid,
                chapter=chapter, operation=operation, old_record_keys=[key] if operation == '替换' else [],
                local_key=key, text=row['text'], reason=row.get('reason', ''),
                evidence=[dict(paragraph_id=full_pid(e['p'], data), quote=e['q']) for e in row['evidence']]))
    candidate['review_audit']['fact_chapters'] = [dict(book_id=bid, chapter=chapter,
        kept_old_keys=obj['keep'], revised_old_keys=[r['key'] for r in obj['replace']],
        excluded_nonstory_keys=obj['exclude'], flagged_old_keys=obj['flag'])]
    paragraphs = []
    owned = set(data['owned_paragraph_ids'])
    seen_paragraphs = []
    for row in obj['paragraphs']:
        pid = full_pid(row.get('id'), data)
        if pid not in owned:
            raise ValueError('原文材料段号必须属于本组责任段')
        seen_paragraphs.append(pid)
        main, secondary = row.get('main'), row.get('secondary')
        if secondary == '' or secondary == main:
            secondary = None
        if main not in TAGS or secondary is not None and secondary not in TAGS:
            issues.append(dict(type='写法标签越界，保留候选待复核', paragraph_id=pid))
        paragraphs.append(dict(paragraph_id=pid.rsplit(':', 1)[-1], main_tag=main, secondary_tag=secondary,
            viewpoint=row.get('viewpoint'), quote=row.get('quote', ''), review_status='已标注', note=row.get('note', '')))
    if set(seen_paragraphs) != owned or len(seen_paragraphs) != len(set(seen_paragraphs)):
        issues.append(dict(type='责任段标注缺失或重复', paragraph_ids=sorted(owned - set(seen_paragraphs))))
    scenes = []
    for i, row in enumerate(obj['scenes']):
        pids = [full_pid(p, data) for p in row.get('paragraph_ids', [])]
        if not set(pids).issubset(owned):
            raise ValueError('场景段号必须属于本组责任段')
        scene = dict(scene_id=f'PR:scene:{bid}:{chapter}:g{group}:{i}', paragraph_ids=[p.rsplit(':', 1)[-1] for p in pids])
        for key in ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere'):
            values = row.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                raise ValueError('场景格' + key + '须为对象数组')
            scene[key] = []
            for value in values:
                if not isinstance(value.get('p'), str) or not isinstance(value.get('q'), str) or not isinstance(value.get('text'), str):
                    raise ValueError('场景格每项须含text,p,q字符串')
                scene[key].append(dict(text=value['text'], evidence=[dict(paragraph_id=full_pid(value['p'], data), quote=value['q'])]))
        scenes.append(scene)
    candidate['C'] = [dict(book_id=bid, chapter=chapter, paragraphs=paragraphs, scenes=scenes)]
    active = {f['local_key']: f.get('paragraph_ids', []) for f in data['facts'] if f['local_key'] in obj['keep'] + obj['flag']}
    active.update({f['local_key']: f.get('paragraph_ids', []) for f in data.get('read_only_context_facts', [])})
    active.update({r['local_key']: [e['paragraph_id'] for e in r['evidence']] for r in candidate['B']})
    candidate['review_audit']['source_chapters'] = [dict(book_id=bid, chapter=chapter, paragraphs=[dict(
        paragraph_id=pid.rsplit(':', 1)[-1], fact_record_keys=[key for key, pids in active.items() if pid in pids],
        disposition='已有句承接' if any(pid in pids for pids in active.values()) else '未决',
        note='' if any(pid in pids for pids in active.values()) else '本组未声明此段事实去向，待复核') for pid in data['owned_paragraph_ids']])]
    for i, issue in enumerate(issues):
        candidate['review_audit']['review_flags'].append(dict(flag_id=f'PR:compact:{bid}:{chapter}:g{group}:{i}',
            book_id=bid, chapter=chapter, category='格式引用缺口', fact_keys=issue.get('keys', []), plan_keys=[],
            paragraph_ids=issue.get('paragraph_ids', [issue['paragraph_id']] if issue.get('paragraph_id') else []),
            reason=issue['type'], conservative_text=None, original_gap_keys=[]))
    return candidate, issues


def bc_call(data, policy, model, output, guard):
    part = 'g' + str(data['group'])
    original_messages = messages(data)
    current = original_messages
    usages = []
    errors = []
    for attempt in range(2):
        response = Client().call(model, current, policy['parameters'], max_tokens=12000)
        dump(output / (part + ('_repair_response.json' if attempt else '_response.json')), response)
        usages.append(response.get('usage', {}))
        try:
            obj = decode(response)
            candidate, issues = convert(obj, data)
            dump(output / (part + '_checks.json'), dict(execution_identity='Codex', repair_limit=1,
                 structural_errors=errors, pending_issues=issues))
            dump(output / (part + '_result.json'), candidate)
            return candidate, usages
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(str(exc))
            dump(output / (part + '_checks.json'), dict(execution_identity='Codex', repair_limit=1,
                 structural_errors=errors, no_progress=len(errors) == 2 and errors[0] == errors[-1]))
            if attempt == 1:
                raise ValueError('一次格式重写后仍无法装配，停止该组：' + str(exc)) from None
            content = response.get('choices', [{}])[0].get('message', {}).get('content') or ''
            current = original_messages + ([dict(role='assistant', content=content)] if content else []) + [
                dict(role='user', content='具体格式错误：' + str(exc) + '。只重写本步骤完整七数组，已有正确故事内容保留。')]
