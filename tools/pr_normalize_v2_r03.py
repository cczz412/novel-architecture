# 执行身份：Codex
"""只有唯一输入段、逐字证据、责任范围同时通过才转换数字或短号。"""
import copy
import re


def normalize(document, data):
    result = copy.deepcopy(document)
    source = data.get('paragraphs', []) + data.get('context_paragraphs', [])
    lookup = {p['paragraph_id']: p['text'] for p in source}
    owned = set(data.get('owned_paragraph_ids', lookup))
    fact_scope = owned | {p for f in data.get('facts', []) for p in f.get('paragraph_ids', [])}
    conversions = []

    def resolve(value, quote, allowed, path):
        if isinstance(value, bool):
            return value
        numeric = value if isinstance(value,int) else int(value) if isinstance(value,str) and value.isdigit() else int(value[1:]) if isinstance(value,str) and re.fullmatch(r'p[0-9]+',value) else None
        if numeric is None:
            return value
        if isinstance(value,str) and (value in lookup or data['book_id']+':ch'+data['chapter']+':'+value in lookup):
            return value
        candidates = [p for p in lookup if re.search(r':p0*' + str(numeric) + r'$', p)]
        if len(candidates) != 1 or not isinstance(quote, str) or not quote or quote not in lookup[candidates[0]] or candidates[0] not in allowed:
            raise ValueError('整数段号不能确定转换：'+path+'；编号='+str(value)+'；唯一对应='+str(len(candidates))+'；需逐字引文和责任范围')
        conversions.append(dict(path=path, original_value=value, original_type=type(value).__name__, input_paragraph_id=candidates[0], verbatim=True, in_scope=True))
        return candidates[0]

    for kind in ('replace', 'add'):
        for i, row in enumerate(result.get(kind, [])):
            for j, e in enumerate(row.get('evidence', [])):
                e['p'] = resolve(e.get('p'), e.get('q'), fact_scope, f'{kind}[{i}].evidence[{j}].p')
    for i, row in enumerate(result.get('paragraphs', [])):
        row['id'] = resolve(row.get('id'), row.get('quote'), owned, f'paragraphs[{i}].id')
    for i, scene in enumerate(result.get('scenes', [])):
        for field in ('location','light_weather','objects_visuals','sounds_smells','atmosphere'):
            for j, value in enumerate(scene.get(field, [])):
                value['p'] = resolve(value.get('p'), value.get('q'), owned, f'scenes[{i}].{field}[{j}].p')
        # 数组编号无逐字引文，必须有同场景格证据或段标注的逐字引文才能转换。
        for j, pid in enumerate(scene.get('paragraph_ids', [])):
            if (isinstance(pid,int) and not isinstance(pid,bool)) or (isinstance(pid,str) and pid.isdigit()):
                q = next((p.get('quote') for p in result.get('paragraphs', []) if isinstance(p.get('id'), str) and re.search(r':p0*'+str(int(pid))+r'$', p['id'])), None)
                scene['paragraph_ids'][j] = resolve(pid, q, owned, f'scenes[{i}].paragraph_ids[{j}]')
    return result, conversions
