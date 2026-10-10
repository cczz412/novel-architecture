# 执行身份：Codex
"""跨模型只判；逐字依据过闸才回传，生成与反馈共用一次重写。"""
import copy
import hashlib
import json
import re
from pathlib import Path

from pr_layers_headroom_r03 import parse
from pr_pipeline_r02 import SYSTEM, dump
from pr_normalize_v2_r03 import normalize

JUDGE = '''你是独立语义复核员，只判，不改写。逐个review_ids恰好一次，输出
{"reviews":[{"id":指定编号,"decision":"通过/明确错误/不确定","field":具体字段,"reason":具体依据,"p":输入段号或null,"q":连续逐字短引或null}]}。
通过也要实际比原文；明确错误必须指出原文依据，不能凭表达风格要求同义改写。
人物计划核是否当下认真提出的可执行行动、主体、窄目标、期限与条件、D-2现场结束、D-3认真可发生的假设回答、来源与真正履约事实。回述、被拒、愿望、内层故事不能误立。
事实核每个原文原因、情绪、反应、否定、条件、情态、数值、说话/心想归属是否仍在；直引须逐字；正确旧句要保留；元语言、无据补词、纯画面归错层算问题。
审稿者关于真假、是不是已发生、能不能据此证明的说明，放理由而不能混进事实正文；即使说明谨慎，也要核原段是否真的说过。原段人物自己的否定、判断、猜测仍按归属保留。
材料核主副写法、感知者而非说话人、当前场景而非回忆、五格类别与逐字摘取，不能把动作当器物、台词内容当声音、个人情绪当环境氛围。
场景编号scenes[i].scope只核当前现场与段范围；scenes[i].格名[j]只核这一格的单条材料，每个编号只返回一次。
编号coverage指本步责任范围是否还有漏掉的合格事实/计划/材料；只能以提供原文指出缺失，不能借常识。拿不准说明具体疑点，不返回改写后的正文或账本。
'''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def identifiers(candidate):
    ids = [f'{k}[{i}]' for k, rows in candidate.items() if isinstance(rows, list)
           and k in ('plans', 'updates', 'old_rows', 'keep', 'exclude', 'flag', 'replace', 'add', 'paragraphs')
           for i in range(len(rows))]
    for i, scene in enumerate(candidate.get('scenes', [])):
        ids.append(f'scenes[{i}].scope')
        for field in ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere'):
            ids.extend(f'scenes[{i}].{field}[{j}]' for j in range(len(scene.get(field, []))))
    return ids + ['coverage']


def judge(client, model, policy, schema, material, candidate, folder, label, layer, ids=None):
    ids = ids or identifiers(candidate)
    stamp = digest(dict(model=model, policy=policy, schema=schema, material=material,
                        candidate=candidate, ids=ids, judge=JUDGE))
    done = folder / (label + '_review.json')
    if done.exists():
        record = json.loads(done.read_text())
        if record['input_sha256'] != stamp:
            raise ValueError('复核检查点配置变化：' + label)
        return record['reviews']
    original = [dict(role='system', content=SYSTEM), dict(role='user', content=JUDGE + '\n' + json.dumps(
        dict(rule_schema=schema, materials=material, candidate=candidate, review_ids=ids), ensure_ascii=False))]
    current = original
    sources = {p['paragraph_id']: p['text'] for p in material.get('paragraphs', []) + material.get('context_paragraphs', []) + material.get('read_only_chapter_context', [])}
    rows = []
    format_errors = []
    for attempt in range(2):
        path = folder / (label + f'_response_{attempt}.json')
        meta = folder / (label + '_input.json')
        if path.exists():
            if json.loads(meta.read_text())['input_sha256'] != stamp:
                raise ValueError('已保存复核响应配置变化：' + label)
            response = json.loads(path.read_text())
        else:
            dump(meta, dict(execution_identity='Codex', input_sha256=stamp, layer=layer+'复核', model=model))
            response = client.call(model, current, policy, max_tokens=8000)
            dump(path, response)
        try:
            rows = parse(response)['reviews']
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError('复核须为对象数组')
            seen = [r.get('id') for r in rows]
            if any(not isinstance(k, str) for k in seen) or set(seen) != set(ids) or len(seen) != len(ids):
                raise ValueError('复核编号缺失、越界或重复')
            for r in rows:
                if r.get('decision') not in ('通过', '明确错误', '不确定') or not isinstance(r.get('reason'), str) or not r['reason']:
                    raise ValueError('复核决定或具体理由缺失')
                if r['decision'] == '明确错误':
                    try:
                        stub, _ = normalize(dict(add=[dict(evidence=[dict(p=r.get('p'), q=r.get('q'))])]),
                                            dict(material, paragraphs=[dict(paragraph_id=p, text=t) for p, t in sources.items()],
                                                 owned_paragraph_ids=list(sources), facts=[]))
                        p = stub['add'][0]['evidence'][0]['p']
                        if isinstance(p, str) and p.startswith('p'):
                            p = material['book_id'] + ':ch' + material['chapter'] + ':' + p
                        q = r.get('q')
                        if p not in sources or not isinstance(q, str) or not q or q not in sources[p]:
                            raise ValueError('缺少逐字原段依据')
                        r['p'] = p
                    except (ValueError, TypeError, KeyError, AttributeError):
                        r['decision'] = '不确定'
                        r['reason'] = '复核疑点的逐字原段依据未过检查：' + r['reason']
            break
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            format_errors.append(str(exc))
            rows = [dict(id=k, decision='不确定', field='复核格式', reason='复核格式未通过：'+str(exc)) for k in ids]
            current = original + [dict(role='assistant', content=response['choices'][0]['message'].get('content') or '{}'),
                                  dict(role='user', content='只修复核结构：'+str(exc)+'；逐个指定编号返回，禁止代写候选。只允许这一次格式重写。')]
    dump(done, dict(execution_identity='Codex', input_sha256=stamp, model=model, reviews=rows, format_errors=format_errors))
    return rows


def isolate(candidate, reviews):
    """有明确错误的最终候选不得直接进入有效输出；不确定保留并留具体疑点。"""
    result = copy.deepcopy(candidate)
    by_array = {}
    scene_fields = {}
    bad_scopes = set()
    for row in reviews:
        nested = re.fullmatch(r'scenes\[(\d+)\]\.(\w+)(?:\[(\d+)\])?', row['id'])
        if row['decision'] == '明确错误' and nested:
            scene, field, item = nested.groups()
            if field == 'scope':
                bad_scopes.add(int(scene))
            elif item is not None:
                scene_fields.setdefault((int(scene), field), set()).add(int(item))
            continue
        match = re.fullmatch(r'(\w+)\[(\d+)\]', row['id'])
        if row['decision'] == '明确错误' and match:
            by_array.setdefault(match[1], set()).add(int(match[2]))
    for (scene, field), indices in scene_fields.items():
        values = result['scenes'][scene].get(field, [])
        result['scenes'][scene][field] = [r for i, r in enumerate(values) if i not in indices]
    if bad_scopes:
        result['scenes'] = [r for i, r in enumerate(result['scenes']) if i not in bad_scopes]
    for kind, indices in by_array.items():
        values = result.get(kind, [])
        if kind in ('keep', 'exclude', 'replace'):
            flagged = result.setdefault('flag', [])
            for i in sorted(indices):
                k = values[i].get('key') if isinstance(values[i], dict) else values[i]
                if isinstance(k, str) and k not in flagged:
                    flagged.append(k)
        if kind == 'paragraphs':
            for i in indices:
                values[i]['main'] = None
                values[i]['viewpoint'] = None
        elif kind == 'old_rows':
            for i in indices:
                values[i]['meaning'] = '未决'
        else:
            result[kind] = [r for i, r in enumerate(values) if i not in indices]
    return result
