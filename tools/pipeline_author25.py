# 执行身份：Codex
"""Build views solely from current-run records; bounded natural-language lookup."""
import json
import re
from pipeline_source25 import read_json
from pipeline_records25 import SECTIONS, evidence
from pipeline_context52 import person_pool, narration, speech_table

# 执行身份：Codex；A 只作候选，展示标记不参与模型请求。
A_YELLOW_NOTICE = 'A 层计划为候选，召回有限，默认不可用，请逐条确认；确认后仍可撤回。'

J2_VIEWS=('人物卡','别名表','关系表','时间表','回忆块','安排义务表','物件表','性格能力表','经济条目','家庭关系卡','说话人')
UNKNOWN_TEXT={'原文未交代':'原文未交代','该层未完成':'本章该层未完成，暂无结果','待核':'有待核条目 {n} 条'}

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
    '说话人': ('谁说','说话人','哪位说'),
    '待核资料': ('待核','确认'),
}



def build_views(materials, current):
    # 保留旧离线驱动单独加载此函数的接口。执行身份：Codex。
    A_YELLOW_NOTICE = 'A 层计划为候选，召回有限，默认不可用，请逐条确认；确认后仍可撤回。'
    views = {name: [] for name in ('人物卡', '别名表', '关系表', '时间表', '回忆块', '安排义务表',
             '物件表', '性格能力表', '计划状态表', '未来安排表', '经济条目', '场景在场表',
             '用餐在场表', '写法视角表', '家庭关系卡', '事实检索', '正文检索', '待核资料','说话人')}
    blocked = []
    chapters=[m['chapter'] for m in materials]
    paragraph_text={p['full_id']:p['text'] for m in materials for p in m['paragraphs']}
    layer_status={ch:{r:current[ch].get(r+'_status')=='complete' if r!='C' else bool(current[ch].get('C',{}).get('paragraphs')) for r in ('A','B','J2','C')} for ch in chapters}
    # 执行身份：Codex；章状态独立于计划条目，空章也有可见说明。
    a_chapter_status = {}
    for ch in chapters:
        part = current[ch]
        reasons = [r['reason'] for r in part.get('A_failure_reasons', [])]
        if not reasons and not layer_status[ch]['A']:
            reasons = [r.get('reason') or 'A 判断未完成' for r in part.get('A_pending', [])]
            reasons += ['复核拒收：' + str(r.get('reason') or '未说明原因') for r in part.get('A_rejected', [])]
        if layer_status[ch]['A'] and part.get('A_empty_reason') == 'no_plans_after_full_judgement':
            label = '本章已判完，无计划'
        elif layer_status[ch]['A']:
            label = '本章已判完，有计划'
        else:
            label = '未完成：' + '；'.join(dict.fromkeys(reasons or ['上游材料未完成']))
        a_chapter_status[ch] = {'status': part.get('A_status'), 'label': label,
                                'empty_reason': part.get('A_empty_reason'), 'reasons': reasons}
    for material in materials:
        part = current[material['chapter']]
        time_hints={};time_anchor=None
        for paragraph in material['paragraphs']:
            match=re.match(r'^(早上|上午|中午|下午|午后|晚上|清晨|午饭后|晚饭后)',paragraph['text'])
            if match:time_anchor={'text':match.group(1),'paragraph_id':paragraph['full_id']}
            if time_anchor:time_hints[paragraph['full_id']]=time_anchor
        for pending in part.get('J2_pending', []):
            row = pending['row']
            ev = evidence(row['ev'], material)
            views['待核资料'].append({**row, 'chapter': material['chapter'], 'source_layer':'J2', 'confirmation_status': '待核',
                'confirmation_reason': pending['reason'], 'evidence': ev, 'paragraph_ids': [e['paragraph_id'] for e in ev]})
        for row in part.get('B',{}).get('unresolved',[]):
            if not re.search(r'未明示|未确证|未直接署名|缺字',row.get('value','')):continue
            ev=evidence(row['ev'],material)
            views['待核资料'].append({**row,'chapter':material['chapter'],'source_layer':'B','confirmation_status':'待核',
                'confirmation_reason':row['value'],'evidence':ev,'paragraph_ids':[e['paragraph_id'] for e in ev]})
        failed_roles = [role for role in ('B', 'J2', 'A') if part.get(role + '_status') != 'complete']
        if failed_roles:
            blocked.append({'chapter': material['chapter'], 'upstream_roles': failed_roles,
                            'pending_count':len(part.get('J2_pending',[]))+len(part.get('A_pending',[])),
                            'status':'partial','message':'该章未完成，资料可能缺失'})
        sections = part.get('J2', {})
        j2_missing=not layer_status[material['chapter']]['J2']
        mapping = dict(zip(SECTIONS, ('人物卡', '别名表', '关系表', '时间表', '回忆块', '安排义务表', '物件表', '性格能力表')))
        for section, name in mapping.items():
            for row in sections.get(section, []):
                item = {**row, 'chapter': material['chapter'], 'evidence': evidence(row['ev'], material),
                        'confirmation_status': row.get('confirmation_status', '已确认'), 'chapter_incomplete': bool(failed_roles)}
                item['paragraph_ids'] = [e['paragraph_id'] for e in item['evidence']]
                if section=='people' and re.search(r'^(?:未知|无名|未定)|据上下文|推断',str(row.get('entity',''))):
                    views['待核资料'].append({**item,'source_layer':'J2','confirmation_status':'待核','confirmation_reason':'人物身份尚未确认，保留原条目待核'})
                    continue
                views[name].append(item)
                if section == 'people' and row.get('aspect') == '经济':
                    views['经济条目'].append(item)
                if section == 'time' and row.get('aspect') in ('未来安排', '作息'):
                    views['未来安排表'].append(item)
        for row in part.get('plans', []):
            evidence_chapters=sorted({e['paragraph_id'].split(':ch')[-1].split(':')[0] for e in row['evidence']})
            origin=evidence_chapters[0] if evidence_chapters else material['chapter']
            # 后章的沿用记录不能填补缺失的前章计划输入。
            if origin < material['chapter'] and not layer_status.get(origin,{}).get('A',False):
                continue
            item = {**row, 'entity': row['subject'], 'value': row['content'],
                    'chapter':material['chapter'],'paragraph_ids': [e['paragraph_id'] for e in row['evidence']]}
            direct=any(row['subject'] and row['subject'] in narration(paragraph_text.get(e['paragraph_id'],e['quote'])) for e in row['evidence'])
            item['subject_j2_chapters']=[] if direct else [origin]
            older_missing=[ch for ch in chapters if ch<material['chapter'] and not layer_status[ch]['A']]
            newer_missing=[ch for ch in chapters if ch>material['chapter'] and not layer_status[ch]['A']]
            item['scope_labels']=['部分：ch'+ch+' A 未完成' for ch in older_missing]
            if newer_missing:
                item.update(recorded_status=item['status'],status='待更新',as_of_chapter=material['chapter'])
                item['scope_labels'].append('截至 ch'+material['chapter']+'，'+','.join('ch'+ch for ch in newer_missing)+' 未更新')
            if any(not layer_status.get(ch,{}).get('J2',False) for ch in item['subject_j2_chapters']):
                item.update(fallback=True,confirmation_status='未经人物账本确认',fallback_label='未经人物账本确认')
                item.update(entity='未知主体（人物账本未完成）',subject='未知主体（人物账本未完成）',original_subject_unconfirmed=row['subject'])
            item.update(source_layer='A', card_color='yellow', card_label='A 黄卡',
                        default_usable=False, author_retractable=True,
                        confirmation_status='待核', confirmation_notice=A_YELLOW_NOTICE)
            views['计划状态表'].append(item)
            if row['status'] in ('未执行', '执行中'):
                views['未来安排表'].append(item)
        binding_rows=part.get('entity_resolution',{}).get('rows',[])
        # 已存称谓映射在完整与缺层两种情况下都可查询，不重新生成关系。
        for binding in binding_rows:
            if binding.get('status')!='已确认' or not binding.get('referent') or binding['term']==binding['referent']:
                continue
            if any(r.get('alias')==binding['term'] and r.get('entity')==binding['referent'] and r.get('chapter')==material['chapter'] for r in views['别名表']):
                continue
            views['别名表'].append({'alias':binding['term'],'entity':binding['referent'],'chapter':material['chapter'],
                'paragraph_ids':[e['paragraph_id'] for e in binding['evidence']], 'evidence':binding['evidence'],
                'source_layer':'entity_resolution','binding_id':binding.get('binding_id'),
                'confirmation_status':'未经人物账本确认' if j2_missing else '已确认',
                'fallback':j2_missing,'fallback_label':'未经人物账本确认' if j2_missing else None})
        for row in part.get('facts', []):
            bindings=[b for b in binding_rows if b['fact_key']==row['local_key']]
            resolved={b['term']:b['referent'] for b in bindings if b['status']=='已确认' and b.get('referent')}
            if re.search(r'的[和与、]',row['text']):
                views['待核资料'].append({'chapter':material['chapter'],'source_layer':'B','value':row['text'],
                    'confirmation_status':'待核','confirmation_reason':'原句可能缺词，保留原句待核',
                    'evidence':row['evidence'],'paragraph_ids':[e['paragraph_id'] for e in row['evidence']]})
            views['事实检索'].append({**row, 'subject':resolved.get(row.get('subject'),row.get('subject')),
                'mentions':list(dict.fromkeys(resolved.get(n,n) for n in row.get('mentions',[]))),
                'original_subject':row.get('subject'),'original_mentions':row.get('mentions',[]),
                'entity_bindings':bindings,'paragraph_ids':[e['paragraph_id'] for e in row['evidence']],
                'retrieval_time_hints':[time_hints[e['paragraph_id']] for e in row['evidence'] if e['paragraph_id'] in time_hints]})
            unresolved=[b['term'] for b in bindings if b.get('status')!='已确认' and re.search(r'自家|亲|娘|爹|嫂|哥|弟|姐|妹|两口|俩口',b['term'])]
            if unresolved:
                views['事实检索'][-1].update(unresolved_references=unresolved,
                    reference_warning='称谓尚未归一；这条是原句线索，不能按句面认定人物或亲属关系。',
                    reference_status='待核',fallback=j2_missing,
                    fallback_label='未经人物账本确认' if j2_missing else None)
            if row.get('kind')=='言语':
                inferred=bool(re.search(r'无名|未知|据上下文|推断',str(row.get('subject'))+row['text']))
                views['说话人'].append({**row,'entity':row.get('speaker') or row['subject'],'chapter':material['chapter'],
                    'paragraph_ids':[e['paragraph_id'] for e in row['evidence']],
                    'inference_label':'据上下文推断，待核' if inferred else None,
                    'fallback':j2_missing,'fallback_label':'未经人物账本确认' if j2_missing else None})
        if j2_missing:
            facts=part.get('facts',[]);pool=person_pool(material,facts,sections)
            present={r['entity'] for r in views['人物卡'] if r.get('chapter')==material['chapter']}
            for name in pool:
                if name in present:continue
                refs=[f for f in facts if name==f.get('subject') or name in f.get('mentions',[])]
                for fact in refs:
                    views['人物卡'].append({'entity':name,'value':fact['text'],'aspect':'事实兜底','chapter':material['chapter'],
                     'evidence':fact['evidence'],'paragraph_ids':[e['paragraph_id'] for e in fact['evidence']],
                     'confirmation_status':'未经人物账本确认','fallback_label':'未经人物账本确认','fallback':True})
        for row in material['paragraphs']:
            views['正文检索'].append({'text': row['text'], 'paragraph_ids': [row['full_id']],
                                      'chapter': material['chapter']})
        c = part.get('C', {})
        # 带引语的动作事实同样可能含说话人，不能只查询B的“言语”标签。
        signatures={r['p']:r for r in speech_table(material,part.get('facts',[]),sections)}
        for paragraph in material['paragraphs']:
            signed=signatures.get(paragraph['paragraph_id'],{})
            if not signed.get('speaker'):continue
            if any(paragraph['full_id'] in r.get('paragraph_ids',[]) for r in views['说话人']):continue
            direct=all(e['method'] in ('直接署名','引语后署名') for e in signed.get('evidence',[]))
            views['说话人'].append({'entity':'、'.join(signed['speaker']),'text':paragraph['text'],
                'chapter':material['chapter'],'paragraph_ids':[paragraph['full_id']],
                'method':[e['method'] for e in signed.get('evidence',[])],'fallback':j2_missing,
                'inference_label':None if direct else '据上下文推断，待核',
                'fallback_label':'未经人物账本确认' if j2_missing else None,
                'confirmation_status':'未经人物账本确认' if j2_missing else '程序署名证据'})
        for row in c.get('paragraphs', []):
            full = next(p['full_id'] for p in material['paragraphs'] if p['paragraph_id'] == row['p'])
            item={**row, 'paragraph_ids':[full],'chapter':material['chapter']}
            viewpoint = row.get('viewpoint')
            direct = (c.get('C_mode') in ('text_v110', 'viewpoint_evidence_v123')
                      or c.get('method') in ('text_c_v110', 'text_c_viewpoint_evidence_v123')
                      or viewpoint in (None, '', '全知', '第一人称', '未定')
                      or isinstance(viewpoint, str) and viewpoint in narration(paragraph_text[full]))
            item['viewpoint_j2_chapters'] = [] if direct else [material['chapter']]
            if j2_missing and item['viewpoint_j2_chapters']:
                item.update(original_viewpoint_unconfirmed=viewpoint, viewpoint='未定（人物账本未完成）',
                            viewpoint_status='待核', fallback=True, fallback_label='未经人物账本确认')
            views['写法视角表'].append(item)
        for row in c.get('scenes', []):
            presence = [{'entity': p['entity'], 'evidence': evidence(p['ev'], material)} for p in row.get('present', [])]
            item = {**row, 'present': presence, 'chapter': material['chapter']}
            item['retrieval_time_hints']=[time_hints[p['full_id']] for p in material['paragraphs'] if p['paragraph_id'] in row.get('paragraph_ids',[]) and p['full_id'] in time_hints]
            views['场景在场表'].append(item)
            location_text = ' '.join(cell['text'] for cell in row.get('location', []))
            if re.search(r'用餐|吃饭|饭桌|宴', ' '.join(row.get('tags', [])) + location_text):
                views['用餐在场表'].append(item)
    # 同一计划跨章只展示最新记录；旧章在新章缺失时保留待更新标注。
    latest_plans={r['key']:r for r in views['计划状态表']}
    views['计划状态表']=list(latest_plans.values())
    nonplans=[r for r in views['未来安排表'] if not r.get('key')]
    views['未来安排表']=nonplans+[r for r in latest_plans.values() if r['status'] in ('未执行','执行中','待更新')]
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
    # 执行身份：Codex；仅供作者显示，按原文段号核对覆盖和待核，不改 C 结果。
    c_chapter_status = {}
    for material in materials:
        ch = material['chapter']
        part = current[ch]
        ids = {p['paragraph_id'] for p in material['paragraphs']}
        aliases = {p['full_id']: p['paragraph_id'] for p in material['paragraphs']}
        aliases.update({pid: pid for pid in ids})
        rows = [r for r in views['写法视角表'] if r['chapter'] == ch]
        missing_ids = ids - {r['p'] for r in rows}
        pending_ids, unknown_ids, reasons = set(), set(), {}
        def add_reason(reason, pid):
            reasons.setdefault(reason, set()).add(pid)
        for pending in part.get('C_pending', []):
            raw = pending.get('paragraph_id') or pending.get('row', {}).get('p')
            pid = aliases.get(raw)
            if pid is None:
                unknown = str(raw or '未提供段号')
                unknown_ids.add(unknown)
                add_reason('原因未知（待核段号对不上原文）', unknown)
            else:
                pending_ids.add(pid)
                add_reason(pending.get('reason') or '原因未知', pid)
        for row in rows:
            if row.get('viewpoint_status') == '待核' or row.get('confirmation_status') == '待核':
                pending_ids.add(row['p'])
                add_reason(row.get('viewpoint_pending_reason') or row.get('confirmation_reason')
                           or row.get('fallback_label') or '视角待作者确认', row['p'])
        explained = set().union(*reasons.values()) if reasons else set()
        for pid in missing_ids - explained:
            add_reason('正文段缺标注', pid)
        pending_ids.update(missing_ids)
        complete = not (missing_ids or pending_ids or unknown_ids)
        groups = [{'reason': reason, 'count': len(pids), 'paragraph_ids': sorted(pids)}
                  for reason, pids in sorted(reasons.items())]
        label = ('不完整、原因未知' if unknown_ids else '不完整') + f'：缺 {len(missing_ids)} 段，待核 {len(pending_ids) + len(unknown_ids)} 段'
        if unknown_ids:
            label += f'；另有 {len(unknown_ids)} 个待核段号无法对应原文'
        if groups:
            label += '；' + '；'.join(g['reason'] + ' ' + str(g['count']) + ' 段（' + '、'.join(g['paragraph_ids']) + '）' for g in groups)
        c_chapter_status[ch] = {'status': '完整' if complete else '不完整',
                               'missing_count': len(missing_ids), 'missing_paragraph_ids': sorted(missing_ids),
                               'pending_count': len(pending_ids) + len(unknown_ids), 'pending_paragraph_ids': sorted(pending_ids),
                               'unmatched_pending_count': len(unknown_ids), 'reason_groups': groups,
                               'label': '完整' if complete else label}
        # 空章沿用原来的未完成显示；非空章按段核对，待核也不能称完整。
        if ids or unknown_ids:
            layer_status[ch]['C'] = complete
    view_status={}
    for name,rows in views.items():
        deps=['J2'] if name in J2_VIEWS else ['A','J2'] if name in ('计划状态表','未来安排表') else ['C','J2'] if name in ('写法视角表','场景在场表','用餐在场表') else ['B'] if name=='事实检索' else []
        j2_label='J2（未知主体回填）' if name in ('计划状态表','未来安排表') else 'J2（视角）' if name=='写法视角表' else 'J2（在场人物）' if name in ('场景在场表','用餐在场表') else 'J2'
        viewpoint_deps = {ch for row in rows for ch in row.get('viewpoint_j2_chapters', [])} if name == '写法视角表' else set(chapters)
        missing=[{'chapter':ch,'layer':j2_label if dep=='J2' else dep} for ch in chapters for dep in deps
                 if not layer_status[ch][dep] and (dep != 'J2' or ch in viewpoint_deps)]
        completed=[ch for ch in chapters if not any(m['chapter'] == ch for m in missing)]
        view_status[name]={'status':'完整' if not missing else '部分' if completed else '未完成','missing':missing,
             'complete_chapters':completed,'pending_count':sum(r.get('chapter') in chapters for r in views['待核资料']) if 'J2'in deps else 0,
             'fallback_count':sum(bool(r.get('fallback')) for r in rows)}
        labels=[]
        if name in ('计划状态表','未来安排表'):
            for ch in chapters:
                if layer_status[ch]['A']:continue
                older=[c for c in chapters if c<ch and layer_status[c]['A']]
                labels.append('截至 ch'+older[-1]+'，ch'+ch+' 未更新' if older else '部分：ch'+ch+' A 未完成')
        if name == '计划状态表':
            labels.extend('ch' + ch + ' ' + item['label'] for ch, item in a_chapter_status.items()
                          if item['empty_reason'] or not layer_status[ch]['A'])
            labels.insert(0, A_YELLOW_NOTICE)
            view_status[name].update(card_color='yellow', default_usable=False,
                                     author_retractable=True, notice=A_YELLOW_NOTICE,
                                     chapter_status=a_chapter_status)
        if name == '写法视角表':
            summary = [c_chapter_status[ch] for ch in chapters]
            view_status[name].update(
                missing_count=sum(item['missing_count'] for item in summary),
                pending_count=sum(item['pending_count'] for item in summary),
                unmatched_pending_count=sum(item['unmatched_pending_count'] for item in summary),
                chapter_status=c_chapter_status)
            labels.extend('ch' + ch + ' ' + item['label'] for ch, item in c_chapter_status.items()
                          if item['status'] != '完整')
        view_status[name]['label']='；'.join(labels)
    return {'execution_identity': 'Codex', 'views': views, 'entities': registry,'view_status':view_status,
            'layer_status':layer_status,'chapters':chapters,
            'status': 'partial' if blocked else 'complete',
            'blocked_chapters': blocked, 'complete': not blocked,
            'partial_records_available': any(views.values()),
            'time_order_policy': '保留原文呈现次序，只有明确关系才说明事件先后',
            'unknown_text': '原文未交代'}


def grams(text):
    out = set()
    for segment in re.findall(r'[\u4e00-\u9fff]+', text):
        for size in (2, 3, 4):
            out.update(segment[i:i + size] for i in range(len(segment) - size + 1))
    return out


def query_views(question):
    """先区分要查什么；普通问题不因一个重合词同时读取所有表。"""
    if re.search(r'有.*(?:被拒|待核).*章|待核.*(?:条目|资料)|确认.*分开',question):return {'待核资料','说话人'}
    explicit={name for name in FIELD_LABELS if name in question}
    if explicit:return explicit
    if re.search(r'谁(?:说|问|提醒|喊)|说的|问的',question):return {'说话人'}
    if re.search(r'「[^」]{1,8}」.*(?:是谁|指谁)|各指谁|称谓|称呼',question):return {'别名表','关系表'}
    if '视角' in question:return {'写法视角表'}
    if re.search(r'在哪|哪里|场景',question):return {'场景在场表'}
    if re.search(r'打算|计划|做成|抓到|还在|现在怎样|后来|还要发生|洗了吗|家务安排',question):return {'计划状态表'}
    return {name for name,fields in FIELD_LABELS.items() if any(label in question for label in fields)} or {'事实检索'}


def query(store, question, limit=12, chapters=None):
    if isinstance(store, (str, bytes)):
        store = read_json(store)
    if not isinstance(question, str) or not question.strip():
        raise ValueError('请给自然中文问题')
    selected_chapters=chapters or re.findall(r'ch(\d{2})',question) or store.get('chapters',[])
    pending_rows=[r for r in store['views'].get('待核资料',[]) if not selected_chapters or r.get('chapter') in selected_chapters]
    blocked=[r for r in store.get('blocked_chapters',[]) if r['chapter'] in selected_chapters]
    meta={'chapter_status':'partial' if blocked else 'complete',
          'blocked_chapters':blocked,
          'pending_count':len(pending_rows),
          'pending_channel':pending_rows[:min(12,max(1,int(limit)))],
          'completeness_message':'该章未完成，资料可能缺失' if blocked else None}
    if store.get('status') == 'blocked_upstream' and not store.get('partial_records_available') and not store.get('view_status'):
        return {'execution_identity': 'Codex', **meta, 'question': question, 'status': 'blocked_upstream',
                'answer': '上游材料尚未保存通过，作者资料暂不能查询。',
                'blocked_chapters': store.get('blocked_chapters', []), 'paragraph_ids': [],
                'bounded_rows': 0, 'default_character_card': False}
    limit = min(12, max(1, int(limit)))
    views = store['views']
    entities = [e for e in store.get('entities', []) if e in question]
    entities = [e for e in entities if not any(e != other and e in other for other in entities)]
    aliases = [r for r in views['别名表'] if r['alias'] in question and (not r.get('chapter') or r['chapter'] in selected_chapters) and not any(r['alias'] in e for e in entities)]
    alias_entities = {r['entity'] for r in aliases}
    requested = query_views(question)
    scope_status={}
    for name,vs in store.get('view_status',{}).items():
        missing=[m for m in vs['missing'] if m['chapter'] in selected_chapters]
        completed=set(selected_chapters)-{m['chapter'] for m in missing}
        scope_status[name]={'status':'完整' if not missing else '部分' if completed else '未完成','chapters':selected_chapters,'missing_chapters':sorted({m['chapter'] for m in missing})}
    meta.update(view_status=store.get('view_status',{}),scope_status=scope_status)
    lookup_question=re.sub(r'（[^）]*(?:partial|blocked|未完成|待核)[^）]*）','',question)
    qgrams = grams(lookup_question)
    quoted_terms=re.findall(r'「([^」]{1,8})」',question)
    candidates = []
    for name, rows in views.items():
        if name in ('事实检索', '正文检索', '待核资料'):
            continue
        if name not in requested:
            continue
        for row in rows:
            if selected_chapters and row.get('chapter') and row['chapter'] not in selected_chapters:continue
            body = ' '.join(str(row.get(k,'')) for k in ('entity','subject','original_subject_unconfirmed','alias','target','value','text','content','members','location','tags','quote'))
            primary = row.get('entity', row.get('subject'))
            direct = primary in entities or primary in alias_entities
            member = any(e in row.get('members', []) for e in entities + list(alias_entities))
            related = any(e in body for e in entities + list(alias_entities))
            overlap=len(qgrams & grams(body))
            if entities or alias_entities:
                if not (direct or member or related) and overlap<3:
                    continue
            elif name not in requested:
                continue
            score = 15 * (name in requested) + 3 * (direct or member) + 2 * related + 3*overlap
            if name=='场景在场表':
                times=re.findall(r'上午|中午|下午|晚上|清晨|午饭后|晚饭后',lookup_question)
                score+=50*any(t in str(row.get('retrieval_time_hints',[])) for t in times)
            quoted=re.findall(r'「([^」]{1,8})」',question)
            if name=='别名表' and quoted:
                if row.get('alias') not in quoted:continue
                score+=60
            if name=='场景在场表' and re.search(r'开头|后半',question):
                same=[s for s in rows if s.get('chapter')==row.get('chapter')]
                chosen=same[0] if '开头'in question else same[-1]
                score+=30*(row is chosen)
            candidates.append((score, name, row))
    # 表内候选优先；正文检索只作后面的补充。
    candidates.sort(key=lambda item: -item[0])
    fallback = []
    clauses=[s for s in re.split(r'[？?、；;]',lookup_question) if s.strip()]
    clause_choices=[]
    for name in ('事实检索', '正文检索'):
        for row in views[name]:
            if selected_chapters and row.get('chapter') and row['chapter'] not in selected_chapters:continue
            body = json.dumps(row, ensure_ascii=False)
            related = any(e in body for e in entities + list(alias_entities))
            overlap = len(qgrams & grams(body))
            term_match=any(term in body for term in quoted_terms)
            if '别名表' in requested and quoted_terms and not term_match:continue
            if (related or term_match or not entities and not alias_entities) and overlap:
                time_terms=re.findall(r'上午|中午|下午|晚上|清晨|午饭后|晚饭后',lookup_question)
                time_match=sum(t in body for t in time_terms)
                fallback.append((overlap + 5 * related+12*time_match, name, row))
            if name=='事实检索' and len(clauses)>1 and '别名表' not in requested:
                for i,clause in enumerate(clauses):
                    topic=clause
                    for entity in entities:topic=topic.replace(entity,'')
                    topic=re.sub(r'现在|还有|什么|打算|计划|还在|怎样|后来|了吗|是吗','',topic)
                    match=len(grams(topic)&grams(row.get('text','')))
                    if match:clause_choices.append((match,i,row))
    fallback.sort(key=lambda item: -item[0])
    rows, seen = [], set()
    supplements=[]
    for i in range(len(clauses)):
        best=sorted([r for r in clause_choices if r[1]==i],key=lambda r:-r[0])[:1]
        supplements.extend((100+score,'事实检索',row) for score,_,row in best)
    if requested=={'场景在场表'} and re.search(r'干什么|做什么',question) and candidates:
        scene=max(candidates,key=lambda r:r[0])[2]
        scene_ids={p.rsplit(':',1)[-1] for p in scene.get('paragraph_ids',[])}
        facts=[r for r in views['事实检索'] if r.get('chapter')==scene.get('chapter') and any(p.rsplit(':',1)[-1] in scene_ids for p in r.get('paragraph_ids',[]))]
        supplements.extend((90-n,'事实检索',row) for n,row in enumerate(facts[:3]))
    for score, name, row in sorted(candidates + supplements + [(s*3,n,r) for s,n,r in fallback],key=lambda r:-r[0]):
        signature = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        rows.append({'view': name, 'score': score, 'data': row})
        if len(rows) >= limit:
            break
    # 范围状态跟随本题实际读取字段；整张视图的缺层信息仍单独保留。
    plan_rows=[r['data'] for r in rows if r['view']=='计划状态表']
    if '计划状态表' in requested:
        facts=[r['data'] for r in rows if r['view']=='事实检索']
        topic=question
        for entity in entities:topic=topic.replace(entity,'')
        topical=grams(re.sub(r'现在|还有|什么|打算|计划|还在|怎样|后来|了吗|是吗','',topic))
        supported=[r for r in plan_rows if topical & grams(r.get('content',''))]
        if not supported and facts and facts[0].get('layer')=='回忆' and not re.search(r'算不算|未来|还要发生',question):
            requested={'事实检索'}
            rows=[r for r in rows if r['view'] not in ('计划状态表','未来安排表')]
            plan_rows=[]
    if '计划状态表' in requested and not plan_rows and rows:
        facts=[r['data'] for r in rows if r['view']=='事实检索']
        if facts and all(r.get('layer')=='回忆' for r in facts[:3]):requested={'事实检索'}
    plan_deps=set(ch for r in plan_rows[:1] for ch in r.get('subject_j2_chapters',[]))
    for name in ('计划状态表','未来安排表','场景在场表','用餐在场表'):
        missing=[]
        for m in store.get('view_status',{}).get(name,{}).get('missing',[]):
            if m['chapter'] not in selected_chapters:continue
            if m['layer'].startswith('J2'):
                if name in ('计划状态表','未来安排表') and m['chapter'] not in plan_deps:continue
                if name in ('场景在场表','用餐在场表') and not re.search(r'谁|哪些人|在场',question):continue
            missing.append(m)
        absent=sorted({m['chapter'] for m in missing})
        scope_status[name]={'status':'完整' if not absent else '部分' if set(selected_chapters)-set(absent) else '未完成',
                            'chapters':selected_chapters,'missing_chapters':absent}
    relevant=requested or {'事实检索'}
    missing=any(scope_status.get(n,{}).get('status','完整')!='完整' for n in relevant if n!='待核资料')
    # 缺 J2 但有明确的 A 状态时，主体的未知由逐条标注说明。
    if relevant=={'计划状态表'}:
        missing=any(not store.get('layer_status',{}).get(ch,{}).get('A',True) for ch in selected_chapters)
    if relevant=={'说话人'}:
        missing=any(not store.get('layer_status',{}).get(ch,{}).get('B',True) for ch in selected_chapters)
    if relevant!={'说话人'} and re.search(r'跟谁|和谁|对谁',question) and any(
        b.get('status')!='已确认' for r in rows[:1] for b in r['data'].get('entity_bindings',[])):
        missing=missing or any(not store.get('layer_status',{}).get(ch,{}).get('J2',True) for ch in selected_chapters)
    pending_requested='待核资料' in requested
    inferred=bool(rows and rows[0]['data'].get('inference_label') and '说话人' in requested)
    top_ids=set(rows[0]['data'].get('paragraph_ids',[])) if rows else set()
    matching_pending=[]
    for r in pending_rows:
        if r.get('source_layer')!='B' or not top_ids & set(r.get('paragraph_ids',[])):continue
        reason=r.get('confirmation_reason') or ''
        if '说话人' in reason and '说话人' not in requested:continue
        if re.search(r'是否.*同一',reason) and not re.search(r'同一|一个人|一家|同个人',question):continue
        if re.search(r'缺词|缺字',reason) and relevant=={'计划状态表'}:continue
        matching_pending.append(r)
    unspoken=any('发出者未明示' in (r.get('confirmation_reason') or '') for r in matching_pending)
    if re.search(r'同一|一个人|一家|同个人',question):
        matching_pending=[r for r in pending_rows if re.search(r'是否.*同一',r.get('confirmation_reason') or '') and len(grams(r.get('confirmation_reason') or '') & qgrams)>=2]
        if matching_pending:missing=False
    meta_query=bool(re.search(r'(?:章|ch\d+).*(?:partial|blocked|未完成)',question))
    if meta_query:missing=bool(blocked)
    if pending_requested:
        matching_pending=[r for r in pending_rows if r.get('source_layer')=='J2']
        missing=False;inferred=False
    category='该层未完成' if missing else '原文未交代' if unspoken else '待核' if inferred or matching_pending else '无' if rows or pending_requested else '原文未交代'
    relevant_pending=matching_pending or ([rows[0]['data']] if inferred else [])
    prompt=UNKNOWN_TEXT['待核'].format(n=len(relevant_pending)) if category=='待核' else UNKNOWN_TEXT.get(category,'无需提示')
    if matching_pending:
        # 相关待核排在待核通道前面；不加入确认答案。
        meta['pending_channel']=(matching_pending+[r for r in pending_rows if r not in matching_pending])[:limit]
    meta['relevant_pending_count']=len(relevant_pending)
    meta['requested_views']=sorted(requested)
    if '计划状态表' in requested:
        meta['plan_chapter_status'] = {ch: item for ch, item in store.get('view_status', {}).get('计划状态表', {}).get('chapter_status', {}).items() if ch in selected_chapters}
        meta['plan_reading_note']=A_YELLOW_NOTICE + '计划状态以计划表及其截至时间为准；事实中的念头、未说出的话不自动当作未来待办。'
    meta['query_scope_labels']=['部分：ch'+ch+' A 未完成' for ch in selected_chapters if relevant=={'计划状态表'} and not store.get('layer_status',{}).get(ch,{}).get('A',True)]
    return {'execution_identity': 'Codex', **meta, 'question': question,'status':store.get('status','complete'),
            'prompt_category':category,'unknown_text':prompt,'fallback_count':sum(bool(r['data'].get('fallback')) for r in rows),
            'fallback_row_count':sum(bool(r['data'].get('fallback')) for r in rows),
            'fallback_answer_count':None,'fallback_answer_count_note':'需逐题语义核对后填写；标注行数不等于靠兜底答对的题数。',
            'view': rows[0]['view'] if rows else '有界检索',
            'answer': rows if rows else prompt,
            'paragraph_ids': sorted({p for r in rows for p in r['data'].get('paragraph_ids', [])}),
            'default_character_card': False, 'bounded_rows': len(rows)}
