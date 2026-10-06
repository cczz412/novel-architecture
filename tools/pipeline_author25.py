# 执行身份：Codex
"""Build views solely from current-run records; bounded natural-language lookup."""
import json
import re
from pipeline_source25 import read_json
from pipeline_records25 import SECTIONS, evidence

FIELD_LABELS = {
    '人物卡': ('人物', '身份', '职业', '本名', '年龄', '别名'),
    '别名表': ('别名', '称呼', '姓名'),
    '家庭关系卡': ('家庭', '家人', '亲属', '成员'),
    '关系表': ('关系', '婚姻', '亲属'),
    '计划状态表': ('计划', '安排', '承诺', '义务', '状态', '期限'),
    '未来安排表': ('未来', '安排', '作息'),
    '经济条目': ('经济', '收入', '支出', '余额', '家境'),
    '时间表': ('时间', '作息', '年限', '经历', '年份', '月份'),
    '回忆块': ('回忆', '往事', '时间线', '时间层'),
    '物件表': ('物件', '物品', '所有权', '持有', '位置'),
    '性格能力表': ('性格', '能力', '态度'),
    '场景在场表': ('场景', '在场', '地点', '场所', '位置'),
    '用餐在场表': ('用餐', '吃饭', '饭桌', '宴'),
    '写法视角表': ('写法', '视角', '心理', '描写'),
}



def build_views(materials, current):
    views = {name: [] for name in ('人物卡', '别名表', '关系表', '时间表', '回忆块', '安排义务表',
             '物件表', '性格能力表', '计划状态表', '未来安排表', '经济条目', '场景在场表',
             '用餐在场表', '写法视角表', '家庭关系卡', '事实检索', '正文检索')}
    blocked = []
    for material in materials:
        part = current[material['chapter']]
        failed_roles = [role for role in ('B', 'J2', 'A') if part.get(role + '_status') != 'complete']
        if failed_roles:
            blocked.append({'chapter': material['chapter'], 'upstream_roles': failed_roles})
            continue
        sections = part.get('J2', {})
        mapping = dict(zip(SECTIONS, ('人物卡', '别名表', '关系表', '时间表', '回忆块', '安排义务表', '物件表', '性格能力表')))
        for section, name in mapping.items():
            for row in sections.get(section, []):
                item = {**row, 'chapter': material['chapter'], 'evidence': evidence(row['ev'], material)}
                item['paragraph_ids'] = [e['paragraph_id'] for e in item['evidence']]
                views[name].append(item)
                if section == 'people' and row.get('aspect') == '经济':
                    views['经济条目'].append(item)
                if section == 'time' and row.get('aspect') in ('未来安排', '作息'):
                    views['未来安排表'].append(item)
        for row in part.get('plans', []):
            item = {**row, 'entity': row['subject'], 'value': row['content'],
                    'paragraph_ids': [e['paragraph_id'] for e in row['evidence']]}
            views['计划状态表'].append(item)
            if row['status'] in ('未执行', '执行中'):
                views['未来安排表'].append(item)
        for row in part.get('facts', []):
            views['事实检索'].append({**row, 'paragraph_ids': [e['paragraph_id'] for e in row['evidence']]})
        for row in material['paragraphs']:
            views['正文检索'].append({'text': row['text'], 'paragraph_ids': [row['full_id']],
                                      'chapter': material['chapter']})
        c = part.get('C', {})
        for row in c.get('paragraphs', []):
            full = next(p['full_id'] for p in material['paragraphs'] if p['paragraph_id'] == row['p'])
            views['写法视角表'].append({**row, 'paragraph_ids': [full], 'chapter': material['chapter']})
        for row in c.get('scenes', []):
            presence = [{'entity': p['entity'], 'evidence': evidence(p['ev'], material)} for p in row.get('present', [])]
            item = {**row, 'present': presence, 'chapter': material['chapter']}
            views['场景在场表'].append(item)
            location_text = ' '.join(cell['text'] for cell in row.get('location', []))
            if re.search(r'用餐|吃饭|饭桌|宴', ' '.join(row.get('tags', [])) + location_text):
                views['用餐在场表'].append(item)
    people = {r['entity'] for r in views['人物卡']}
    edges = [r for r in views['关系表'] if r.get('relation_type') == '亲属'
             and r.get('entity') in people and r.get('target') in people]
    adjacency = {name: set() for name in people}
    for edge in edges:
        adjacency[edge['entity']].add(edge['target'])
        adjacency[edge['target']].add(edge['entity'])
    visited = set()
    for person in sorted(people):
        if person in visited or not adjacency[person]:
            continue
        members, todo = set(), [person]
        while todo:
            name = todo.pop()
            if name in members:
                continue
            members.add(name)
            todo.extend(adjacency[name] - members)
        visited.update(members)
        component = [r for r in edges if r['entity'] in members and r['target'] in members]
        views['家庭关系卡'].append({'members': sorted(members), 'relations': component,
                    'paragraph_ids': sorted({p for r in component for p in r['paragraph_ids']})})
    # 文本呈现顺序不是推断出来的事件先后。
    registry = sorted({str(r.get('entity', '')) for name in ('人物卡', '物件表') for r in views[name] if r.get('entity')}, key=lambda x: (-len(x), x))
    return {'execution_identity': 'Codex', 'views': views, 'entities': registry,
            'status': 'blocked_upstream' if blocked else 'complete',
            'blocked_chapters': blocked, 'complete': not blocked,
            'time_order_policy': '保留原文呈现次序，只有明确关系才说明事件先后',
            'unknown_text': '原文未交代'}


def grams(text):
    out = set()
    for segment in re.findall(r'[\u4e00-\u9fff]+', text):
        for size in (2, 3, 4):
            out.update(segment[i:i + size] for i in range(len(segment) - size + 1))
    return out


def query(store, question, limit=12):
    if isinstance(store, (str, bytes)):
        store = read_json(store)
    if not isinstance(question, str) or not question.strip():
        raise ValueError('请给自然中文问题')
    if store.get('status') == 'blocked_upstream':
        return {'execution_identity': 'Codex', 'question': question, 'status': 'blocked_upstream',
                'answer': '上游材料尚未保存通过，作者资料暂不能查询。',
                'blocked_chapters': store.get('blocked_chapters', []), 'paragraph_ids': [],
                'bounded_rows': 0, 'default_character_card': False}
    limit = min(12, max(1, int(limit)))
    views = store['views']
    entities = [e for e in store.get('entities', []) if e in question]
    entities = [e for e in entities if not any(e != other and e in other for other in entities)]
    aliases = [r for r in views['别名表'] if r['alias'] in question and not any(r['alias'] in e for e in entities)]
    alias_entities = {r['entity'] for r in aliases}
    requested = {name for name, fields in FIELD_LABELS.items()
                 if name in question or any(label in question for label in fields)}
    qgrams = grams(question)
    candidates = []
    for name, rows in views.items():
        if name in ('事实检索', '正文检索'):
            continue
        for row in rows:
            body = json.dumps(row, ensure_ascii=False)
            primary = row.get('entity', row.get('subject'))
            direct = primary in entities or primary in alias_entities
            member = any(e in row.get('members', []) for e in entities + list(alias_entities))
            related = any(e in body for e in entities + list(alias_entities))
            if entities or alias_entities:
                if not (direct or member or related):
                    continue
            elif name not in requested:
                continue
            score = 25 * (name in requested) + 15 * (direct or member) + 4 * related + len(qgrams & grams(body))
            candidates.append((score, name, row))
    # 表内候选优先；正文检索只作后面的补充。
    candidates.sort(key=lambda item: -item[0])
    fallback = []
    for name in ('事实检索', '正文检索'):
        for row in views[name]:
            body = json.dumps(row, ensure_ascii=False)
            related = any(e in body for e in entities + list(alias_entities))
            overlap = len(qgrams & grams(body))
            if (related or not entities and not alias_entities) and overlap:
                fallback.append((overlap + 5 * related, name, row))
    fallback.sort(key=lambda item: -item[0])
    rows, seen = [], set()
    for score, name, row in candidates + fallback:
        signature = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        rows.append({'view': name, 'score': score, 'data': row})
        if len(rows) >= limit:
            break
    return {'execution_identity': 'Codex', 'question': question,
            'view': rows[0]['view'] if rows else '有界检索',
            'answer': rows if rows else '原文未交代',
            'paragraph_ids': sorted({p for r in rows for p in r['data'].get('paragraph_ids', [])}),
            'default_character_card': False, 'bounded_rows': len(rows)}
