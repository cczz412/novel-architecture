# 执行身份：Codex
"""Evidence validation and current-run data assembly."""
import copy
import hashlib
import json
import re

SECTIONS = ('people', 'aliases', 'relations', 'time', 'memories', 'arrangements', 'objects', 'traits')
STATUSES = ('未执行', '执行中', '兑现', '落空', '放弃')
TAGS = ('叙述带过', '动作展开', '对话', '心理', '场景')


def key_for(*parts):
    value = json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()[:24]


def evidence(rows, material):
    texts = {r['paragraph_id']: r['text'] for r in material['paragraphs']}
    if not isinstance(rows, list) or not rows:
        raise ValueError('证据缺失')
    out = []
    for row in rows:
        p, q = row.get('p'), row.get('q')
        if p not in texts or not isinstance(q, str) or not q.strip() or q not in texts[p]:
            raise ValueError('引语或段号无法逐字连接')
        full = next(r['full_id'] for r in material['paragraphs'] if r['paragraph_id'] == p)
        out.append({'paragraph_id': full, 'quote': q})
    return out


def validate(role, payload, material, facts=None, previous=None):
    facts, previous = facts or [], previous or []
    if not isinstance(payload, dict):
        raise ValueError('输出须为对象')
    errors = []
    result = copy.deepcopy(payload)
    groups = [role] if role in ('A', 'B') else list(SECTIONS) if role == 'J2' else ['paragraphs', 'scenes']
    seen = set()
    for group in groups:
        field = 'rows' if role in ('A', 'B') else group
        rows = result.get(field)
        if not isinstance(rows, list):
            raise ValueError('栏目缺失：' + field)
        for index, row in enumerate(rows):
            ident = group + ':' + str(index)
            try:
                if not isinstance(row, dict):
                    raise ValueError('条目须为对象')
                if role == 'C' and group == 'paragraphs':
                    texts = {r['paragraph_id']: r['text'] for r in material['paragraphs']}
                    p = row.get('p')
                    if p not in texts or p in seen or row.get('main_tag') not in TAGS:
                        raise ValueError('段级标注无效或重复')
                    if row.get('secondary_tag') not in (*TAGS, None, ''):
                        raise ValueError('副标签无效')
                    if row.get('secondary_tag') == row.get('main_tag'):
                        raise ValueError('主副标签重复')
                    if not row.get('quote') or row['quote'] not in texts[p]:
                        raise ValueError('段级引语不连续')
                    seen.add(p)
                elif role == 'C':
                    valid = {r['paragraph_id'] for r in material['paragraphs']}
                    if not row.get('paragraph_ids') or set(row['paragraph_ids']) - valid:
                        raise ValueError('场景范围无效')
                    for name in ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere'):
                        if not isinstance(row.get(name), list):
                            raise ValueError('场景格缺失')
                        for cell in row[name]:
                            evidence(cell.get('ev'), material)
                    for person in row.get('present', []):
                        evidence(person.get('ev'), material)
                else:
                    old_plan = next((r for r in previous if r['key'] == row.get('key')), None) if role == 'A' else None
                    unchanged = bool(old_plan and all(row.get(k) == old_plan.get(k) for k in ('subject', 'content', 'status', 'source', 'deadline', 'condition')))
                    if not (unchanged and row.get('ev') == []):
                        evidence(row.get('ev'), material)
                    if role == 'B' and (not row.get('text') or not row.get('subject') or not isinstance(row.get('mentions'), list)):
                        raise ValueError('事实字段缺失')
                    if role == 'A':
                        keys = {f['local_key'] for f in facts}
                        old = {r['key'] for r in previous}
                        if row.get('key') is not None and row['key'] not in old:
                            raise ValueError('旧计划键不可连接')
                        if not row.get('subject') or not row.get('content') or row.get('status') not in STATUSES:
                            raise ValueError('计划字段无效')
                        refs = [row.get('source'), row.get('fulfilled'), row.get('condition_ref')] + row.get('basis', [])
                        if (not row.get('basis') and not unchanged) or any(r is not None and r not in keys for r in refs):
                            raise ValueError('计划依据不完整或错指')
                        source_fact = next((f for f in facts if f['local_key'] == row.get('source')), None)
                        if source_fact is None or source_fact.get('subject') != row['subject']:
                            raise ValueError('计划来源主体与持有人不一致')
                        if row['status'] == '兑现' and not row.get('fulfilled'):
                            raise ValueError('兑现缺完成依据')
                    if role == 'J2' and group == 'relations' and (not row.get('target') or row.get('relation_type') not in ('亲属', '合作', '冲突', '其他', '未知')):
                        raise ValueError('关系缺对象或明确类型')
                    if role == 'J2' and group == 'memories':
                        order = {p['paragraph_id']: n for n, p in enumerate(material['paragraphs'])}
                        if row.get('start') not in order or row.get('end') not in order or order[row['start']] > order[row['end']] or not row.get('anchor'):
                            raise ValueError('回忆块范围或锚无效')
                    elif role == 'J2':
                        if not row.get('entity'):
                            raise ValueError('主体缺失')
                        if group == 'aliases':
                            if not row.get('alias') or not row.get('scope'):
                                raise ValueError('别名缺名称或适用范围')
                        elif not row.get('value') or not row.get('aspect'):
                            raise ValueError('事实资料缺内容或类别')
                row['_id'] = ident
            except (ValueError, TypeError, KeyError) as exc:
                errors.append({'id': ident, 'error': str(exc)})
    if role == 'C' and seen != {r['paragraph_id'] for r in material['paragraphs']}:
        errors.append({'id': 'C', 'error': '正文段覆盖不完整'})
    if errors:
        raise ValueError(json.dumps(errors, ensure_ascii=False))
    return result


def flatten(role, value):
    if role in ('A', 'B'):
        return value['rows']
    return [row for section in (SECTIONS if role == 'J2' else ('paragraphs', 'scenes')) for row in value[section]]


def check_speaker_claims(verdict, candidate, material):
    claims = verdict.get('speaker_claims')
    if not isinstance(claims, list):
        raise ValueError('复核缺说话归属检查栏')
    texts = {p['paragraph_id']: p['text'] for p in material['paragraphs']}
    proved = set()
    for claim in claims:
        evidence([{'p': claim.get('p'), 'q': claim.get('q')}], material)
        entity = claim.get('entity')
        if not isinstance(entity, str) or not entity:
            raise ValueError('说话主体缺失')
        narration = re.sub(r'“[^”]*”|「[^」]*」|"[^"\n]*"', '', texts[claim['p']])
        pattern = re.escape(entity) + r'(?:轻声|低声|大声|笑着|接着|又|还|便|就|才|却)?(?:说|道|喊|问|答|叫)'
        claim_plain = re.sub(r'“[^”]*”|「[^」]*」|"[^"\n]*"', '', claim['q'])
        if not re.search(pattern, narration) or not re.search(pattern, claim_plain):
            raise ValueError('复核理由中的说话主体没有署名证据')
        proved.add(entity)
    names = set()
    for row in candidate:
        for field in ('subject', 'entity'):
            if isinstance(row.get(field), str):
                names.add(row[field])
        names.update(x for x in row.get('mentions', []) if isinstance(x, str))
    for name in names:
        if re.search(re.escape(name) + r'(?:说|说道|喊|问|答|叫)', verdict.get('reason', '')) and name not in proved:
            raise ValueError('复核理由的说话归属没有逐项证据')


def deduplicate(role, value):
    out = copy.deepcopy(value)
    fields = ['rows'] if role in ('A', 'B') else list(SECTIONS) if role == 'J2' else ['paragraphs', 'scenes']
    removed = []
    for field in fields:
        seen, kept = set(), []
        for row in out[field]:
            signature = json.dumps({k: v for k, v in row.items() if k != '_id'}, ensure_ascii=False, sort_keys=True)
            if signature in seen:
                removed.append({'id': row.get('_id'), 'reason': '相同内容与来源重复', 'row': row})
            else:
                seen.add(signature)
                kept.append(row)
        out[field] = kept
    return out, removed


def review_apply(role, candidate, review, material, facts=None, previous=None):
    rows = flatten(role, candidate)
    wanted = {r['_id'] for r in rows}
    verdicts = review.get('verdicts')
    if not isinstance(verdicts, list) or len(verdicts) != len(wanted) or {r.get('id') for r in verdicts} != wanted:
        raise ValueError('复核未逐项覆盖或重复')
    for verdict in verdicts:
        check_speaker_claims(verdict, rows, material)
    by_id = {r['id']: r for r in verdicts}
    out = copy.deepcopy(candidate)
    removed = []
    fields = ['rows'] if role in ('A', 'B') else list(SECTIONS) if role == 'J2' else ['paragraphs', 'scenes']
    for field in fields:
        kept = []
        for row in out[field]:
            verdict = by_id[row['_id']]
            if not isinstance(verdict.get('accept'), bool) or not verdict.get('reason'):
                raise ValueError('复核裁定缺少布尔值或理由')
            if not verdict['accept']:
                removed.append({'id': row['_id'], 'reason': verdict['reason'], 'row': row})
                continue
            patch = verdict.get('patch')
            kept.append(patch if patch is not None else row)
        out[field] = kept
    # C被拒行不能用默认全知补齐；保留未完成状态，由调用方披露。
    checked = validate(role, out, material, facts, previous) if role != 'C' or not removed else out
    checked, duplicates = deduplicate(role, checked)
    return checked, removed + duplicates


def facts_output(value, material):
    output = []
    for index, row in enumerate(value['rows'], 1):
        ev = evidence(row['ev'], material)
        key = 'local:' + material['book_id'] + ':ch' + material['chapter'] + ':r' + str(index).zfill(3)
        output.append({'change_id': 'new:' + key, 'book_id': material['book_id'],
                       'chapter': material['chapter'], 'operation': '新增', 'old_record_keys': [],
                       'local_key': key, 'text': row['text'], 'subject': row['subject'], 'kind': row.get('kind'),
                       'mentions': row['mentions'], 'layer': row.get('layer', '未知'),
                       'reason': '按逐字证据与复核裁定保留', 'evidence': ev})
    return output


def plans_output(value, material, previous):
    result = []
    for row in value['rows']:
        stable = row['key'] or 'plan:' + key_for(material['book_id'], material['chapter'], row['subject'], row['content'], row['source'])
        result.append({**row, 'key': stable, 'chapter': material['chapter'],
                       'evidence': evidence(row['ev'], material) if row['ev'] else next(r['evidence'] for r in previous if r['key'] == row['key'])})
    return result


def assemble(materials, current):
    pred = {'execution_identity': 'Codex', 'batch_id': 'current_run',
            'identity': 'OFFLINE_SAMPLE_DELTA_NOT_FORMAL_LEDGER',
            'basis': 'EXTRACTION_R6_INTENT_V2_1_PR374_INPUT_R06',
            'A': [], 'B': [], 'C': [], 'coverage': [], 'unresolved': [],
            'review_audit': {k: [] for k in ('old_plan_rows', 'fact_chapters', 'source_chapters', 'plan_history', 'open_plan_keys', 'review_flags')}}
    for material in materials:
        chapter = material['chapter']
        part = current[chapter]
        facts = part.get('facts', [])
        pred['B'].extend(facts)
        pred['review_audit']['fact_chapters'].append({'book_id': material['book_id'], 'chapter': chapter, 'kept_old_keys': [], 'revised_old_keys': [], 'excluded_nonstory_keys': [], 'flagged_old_keys': []})
        audit_rows = []
        for p in material['paragraphs']:
            refs = [f['local_key'] for f in facts if p['full_id'] in {e['paragraph_id'] for e in f['evidence']}]
            audit_rows.append({'paragraph_id': p['full_id'], 'fact_record_keys': refs, 'disposition': '本次补修' if refs else '未决', 'note': '由当前事实证据连接' if refs else '没有通过保存的事实行，不自动推定无需抽取'})
        pred['review_audit']['source_chapters'].append({'book_id': material['book_id'], 'chapter': chapter, 'paragraphs': audit_rows})
        for row in part.get('plans', []):
            pred['A'].append({'change_id': row['key'] + ':ch' + chapter, 'book_id': material['book_id'],
                'as_of_chapter': chapter, 'old_ledger_keys': [], 'decision': '修订' if any(h['plan_key'] == row['key'] for h in pred['review_audit']['plan_history']) else '新增',
                'subject_text': row['subject'], 'plan': {'content': row['content'], 'scope': 'in_book_character',
                    'status': row['status'], 'source_fact_ref': None, 'fulfilled_fact_ref': None,
                    'deadline': {'text': row['deadline'], 'story_time': None} if row.get('deadline') else None,
                    'condition': row.get('condition'), 'condition_fact_ref': None},
                'candidate_refs': {'source_record_key': row['source'], 'fulfilled_record_key': row.get('fulfilled'),
                                   'condition_record_key': row.get('condition_ref')},
                'reason': row['reason'], 'evidence': row['evidence']})
            history = next((h for h in pred['review_audit']['plan_history'] if h['plan_key'] == row['key']), None)
            if history is None:
                history = {'plan_key': row['key'], 'book_id': material['book_id'], 'old_ledger_keys': [], 'A_change_ids': [], 'introduced_chapter': chapter, 'states': []}
                pred['review_audit']['plan_history'].append(history)
            history['A_change_ids'].append(row['key'] + ':ch' + chapter)
            history['states'].append({'chapter': chapter, 'status': row['status'], 'source_record_key': row['source'], 'fulfilled_record_key': row.get('fulfilled'), 'condition_record_key': row.get('condition_ref'), 'change_basis_record_keys': row['basis'], 'note': row['reason']})
        c = part.get('C')
        if c:
            paragraphs = [{**{k: v for k, v in row.items() if k not in ('p', '_id')},
                           'paragraph_id': row['p'], 'review_status': '已标注'} for row in c['paragraphs']]
            scenes = []
            for index, row in enumerate(c['scenes'], 1):
                scene = {'scene_id': 'scene:' + chapter + ':' + str(index), 'paragraph_ids': row['paragraph_ids'],
                         'present': row.get('present', []), 'tags': row.get('tags', []), 'layer': row.get('layer', '未知')}
                for field in ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere'):
                    scene[field] = [{'text': cell['text'], 'evidence': evidence(cell['ev'], material)} for cell in row[field]]
                scenes.append(scene)
            pred['C'].append({'book_id': material['book_id'], 'chapter': chapter, 'paragraphs': paragraphs, 'scenes': scenes})
        pred['coverage'].append({'book_id': material['book_id'], 'chapter': chapter,
                                 'paragraphs_read': len(material['paragraphs']), 'fact_count': len(facts)})
    pred['review_audit']['open_plan_keys'] = [h['plan_key'] for h in pred['review_audit']['plan_history'] if h['states'][-1]['status'] in ('未执行', '执行中')]
    return pred
