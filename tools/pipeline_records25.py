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
    if role == 'A' and result.get('rows') == []:
        raise ValueError(json.dumps({'id': 'A', 'field': 'rows',
            'error': '计划候选或复核保存计划为空，阶段未完成；有原文依据才补计划，不能编造'}, ensure_ascii=False))
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
                        if source_fact is None or (source_fact.get('subject') != row['subject'] and row['subject'] not in row.get('_seed_holders', [])):
                            raise ValueError('计划来源主体与持有人不一致')
                        if row['status'] == '兑现' and not row.get('fulfilled'):
                            raise ValueError('兑现缺完成依据')
                    if role == 'J2' and group == 'relations':
                        missing = [name for name in ('value', 'aspect')
                                   if not isinstance(row.get(name), str) or not row[name].strip()]
                        if missing:
                            raise ValueError('关系缺内容(value)或类别(aspect)：' + '、'.join(missing))
                        if not row.get('target') or row.get('relation_type') not in ('亲属', '合作', '冲突', '其他', '未知'):
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
    if role == 'C':
        from pipeline_c_program25 import scene_fragment_issues
        errors.extend({'id':'C','error':'场景格半截，不能签发','detail':r}
                      for r in scene_fragment_issues(material,result.get('scenes',[])))
    if errors:
        raise ValueError(json.dumps(errors, ensure_ascii=False))
    return result


def flatten(role, value):
    if role in ('A', 'B'):
        return value['rows']
    return [row for section in (SECTIONS if role == 'J2' else ('paragraphs', 'scenes')) for row in value[section]]


def plan_seeds(material, facts):
    """只从本章已存事实及逐字证据宽列线索；不替模型裁定计划或状态。"""
    paragraphs = {p['full_id']: p for p in material['paragraphs']}
    signal = re.compile(r'计划|打算|准备|决定|安排|约定|承诺|答应|叮嘱|保证|必须|需要|'
                        r'今晚|晚上|明天|后天|下午|下周|下月|开学|以后|将要|要|得|轮到')
    seeds, seen = [], set()
    for fact in facts:
        subject, source = fact.get('subject'), fact.get('local_key')
        if (fact.get('book_id') != material['book_id'] or fact.get('chapter') != material['chapter']
                or not isinstance(subject, str) or not subject.strip()
                or subject in ('未知', '无名', '无名说话人') or not isinstance(source, str) or source in seen):
            continue
        ev = []
        for item in fact.get('evidence', []):
            paragraph, quote = paragraphs.get(item.get('paragraph_id')), item.get('quote')
            if paragraph and isinstance(quote, str) and quote.strip() and quote in paragraph['text']:
                ev.append({'p': paragraph['paragraph_id'], 'q': quote})
        if not ev or not signal.search(str(fact.get('text', '')) + ''.join(e['q'] for e in ev)):
            continue
        seen.add(source)
        seeds.append({'seed_id': 'seed:' + key_for(source, ev), 'subject': subject,
                      'source': source, 'basis': [source], 'content_hint': fact.get('text'), 'ev': ev})
    return seeds


def check_plan_seed_scope(value, seeds, previous):
    """新计划须连接程序种子的主体、来源和证据；原计划仍按既有历史合同核对。"""
    old_keys = {row['key'] for row in previous}
    errors = []
    for row in value['rows']:
        if row.get('key') in old_keys:
            continue
        from pipeline_plan52 import seed_holders
        matching = [s for s in seeds if s['source'] == row.get('source') and
                    row.get('subject') in seed_holders(s)]
        if matching and matching[0].get('input_method') == 'seed_followup_packets_v52':
            allowed=[e for seed in matching for e in seed['ev']+seed.get('followups',[])]
            if row.get('source') not in row.get('basis',[]) or not row.get('ev') or any(not any(
                e.get('p')==a['p'] and isinstance(e.get('q'),str) and e['q'] and e['q'] in a['q'] for a in allowed) for e in row.get('ev',[])):
                errors.append({'id':row.get('_id'),'error':'证据不在本包种子或后续'})
            continue
        if (not matching or row.get('source') not in row.get('basis', [])
                or not row.get('ev') or any(not any(e.get('p') == support['p']
                    and isinstance(e.get('q'), str) and e['q'] and e['q'] in support['q']
                    for seed in matching for support in seed['ev']) for e in row.get('ev', []))):
            errors.append({'id': row.get('_id'), 'field': 'source/basis/ev',
                           'error': '新计划须使用本章程序种子的同一主体、事实来源和逐字证据，不能补无依据计划'})
    if errors:
        raise ValueError(json.dumps(errors, ensure_ascii=False))
    return value


def bind_plan_seeds(value, seeds):
    """新协议由模型选种子，主体、来源和证据由程序接回；旧行仍走原严格校验。"""
    out = copy.deepcopy(value)
    index = {seed['seed_id']: seed for seed in seeds}
    for row in out.get('rows', []):
        ident = row.pop('seed_id', None)
        if ident is None:
            continue
        if ident not in index or row.get('key') is not None:
            raise ValueError('新计划种子编号未知或与旧计划混用')
        seed = index[ident]
        if seed.get('input_method') == 'seed_followup_packets_v52':
            from pipeline_plan52 import seed_holders
            holders=seed_holders(seed) if 'candidate_columns' in seed else set(seed.get('plan_holders',[seed['subject'],*seed.get('receivers',[])]))
            holder=row.pop('holder',seed['subject'])
            if holder not in holders:raise ValueError('持有人不在种子候选')
            support=seed['ev']+seed.get('followups',[])
            pids=row.pop('evidence_paragraphs',None)
            if pids is not None and (not pids or set(pids)-{e['p'] for e in support}):
                raise ValueError('证据段不在种子或后续')
            ev=[{'p':e['p'],'q':e['q']} for e in support if pids is None and e in seed['ev'] or pids is not None and e['p'] in pids]
            row.update(subject=holder,source=seed['source'],basis=copy.deepcopy(seed['basis']),ev=ev,_seed_holders=sorted(holders))
            row['_seed_paragraphs']=[e['p'] for e in seed['ev']]
            row['state_paragraphs']=[]
            row['condition_paragraphs']=[]
            from pipeline_plan52 import COND
            conditions=[m[0] for e in seed['ev'] for m in COND.finditer(e['q'])]
            if conditions:row['condition']='；'.join(dict.fromkeys(conditions))
            continue
        fixed = {k: copy.deepcopy(seed[k]) for k in ('subject', 'source', 'basis', 'ev')}
        if any(k in row and row[k] != v for k, v in fixed.items()):
            raise ValueError('模型不得另写与种子冲突的主体、来源或证据')
        row.update(fixed)
    return out


def b_scoring_projection(prediction):
    """旧评分合同仅看事实正文；新归属信息完整留附表，原事实仍供后续岗位读取。"""
    out = copy.deepcopy(prediction)
    metadata = copy.deepcopy(out.get('B_metadata', []))
    for row in out.get('B', []):
        extra = {k: row.pop(k) for k in ('subject', 'kind', 'mentions', 'layer', 'speaker', 'holder', 'subject_text') if k in row}
        if extra:
            metadata.append({'local_key': row['local_key'], **extra})
    if metadata:
        out['B_metadata'] = metadata
    return out


def j2_program_candidates(material, facts):
    """逐事实列候选，来源不改写；只给资料类线索，是否收录交短判断。"""
    from pipeline_output28 import sentences
    table = sentences(material)
    seeds = {row['source'] for row in plan_seeds(material, facts)}
    output = {field: [] for field in SECTIONS}
    provenance = []
    for fact in facts:
        if fact.get('book_id') != material['book_id'] or fact.get('chapter') != material['chapter']:
            raise ValueError('J2候选事实归章不符')
        ev, pointers = [], []
        for item in fact.get('evidence', []):
            pid = item.get('paragraph_id', '').rsplit(':', 1)[-1]
            quote = item.get('quote')
            support = evidence([{'p': pid, 'q': quote}], material)
            if not support:
                raise ValueError('J2候选缺来源')
            ev.append({'p': pid, 'q': quote})
            numbers = [number for number, sentence in enumerate(table[pid], 1)
                       if quote in sentence or sentence.strip() and sentence in quote]
            if not numbers:
                raise ValueError('J2候选证据不能连接句号指针')
            pointers.extend({'p': pid, 's': number} for number in numbers)
        if not ev or not fact.get('subject') or not fact.get('text'):
            raise ValueError('J2候选缺主体、正文或证据')
        text = fact['text']
        targets = [name for name in fact.get('mentions', []) if isinstance(name, str)
                   and name != fact['subject'] and name in text]
        naming = re.search(r'(?:又名|小名|绰号|昵称|称为|称作|名叫)[“「『"]?([^，。；！？：:“”「」『』"\s]{1,12})', text)
        field = ('aliases' if naming else
                 'memories' if fact.get('layer') == '回忆' else
                 'arrangements' if fact['local_key'] in seeds else
                 'relations' if targets and re.search(r'父亲|母亲|父子|母子|兄弟|姐妹|夫妻|亲属|合作|关系', text) else
                 'time' if re.search(r'\d+\s*(?:年|月|日|点|岁)|上午|中午|晚上|作息', text) else
                 'objects' if re.search(r'持有|放置|拿着|拿起|交给|交出|取走|收到', text) else
                 'traits' if fact.get('kind') == '心理' else 'people')
        row = {'entity': fact['subject'], 'aspect': '未知', 'value': fact['text'],
               'layer': fact.get('layer', '未知'), 'ev': ev}
        if field == 'aliases':
            row = {'entity': fact['subject'], 'alias': naming.group(1), 'speaker': None,
                   'scope': list(dict.fromkeys(item['p'] for item in ev)), 'ev': ev}
        elif field == 'relations':
            row.update(target=targets[0], relation_type='未知')
        elif field == 'memories':
            order = {p['paragraph_id']: n for n, p in enumerate(material['paragraphs'])}
            pids = sorted({item['p'] for item in ev}, key=order.get)
            row = {'start': pids[0], 'end': pids[-1], 'anchor': text, 'viewpoint': None, 'ev': ev}
        elif field == 'time':
            row['aspect'] = '未知'
        output[field].append(row)
        provenance.append({'section': field, 'section_index': len(output[field]) - 1,
                           'source': fact['local_key'], 'pointers': pointers})
    checked = validate('J2', output, material)
    for item in provenance:
        item['id'] = checked[item['section']][item['section_index']]['_id']
    return checked, provenance



J2_V50 = 'program_candidates_itemwise_v50'
J2_NEIGHBOR_SENTENCES = 3


def j2_chapter_speakers(material, rows, facts=()):
    """整章宽列候选；邻近与代词回指只是候选，只有直接署名可确认。"""
    from pipeline_output28 import sentences
    names = set()
    for row in list(rows) + list(facts):
        for k in ('subject', 'entity', 'target', 'speaker'):
            v = row.get(k)
            if isinstance(v, str) and v.strip() and v not in ('未知', '无名', '无名说话人'):
                names.add(v)
        names.update(x for x in row.get('mentions', []) if isinstance(x, str) and x.strip())
    texts = '\n'.join(p['text'] for p in material['paragraphs'])
    names = {n for n in names if n in texts or any(n == f.get('subject') or n in f.get('mentions', []) for f in facts)}
    table = sentences(material)
    units = [[p, n, t] for p, parts in table.items() for n, t in enumerate(parts, 1)
             if t.strip('“”「」『』"。！？\n \t')]
    # 直接署名沿用已验证的引号外检查，实体集合取整章而非当前拆包。
    direct = speaker_candidates(material, [{'entity': n} for n in names], direct_only=True, strict_j2=True)
    from pipeline_context52 import speech_table, has_speech_clause
    events=speech_table(material,facts,{'people':[{'entity':n} for n in names]})
    result = {'names': sorted(names), 'direct': direct, 'units': units, 'window': J2_NEIGHBOR_SENTENCES,
              'reported_speech_paragraphs':[r['p'] for r in events if r['speech_event'] and not r['dialogue']],
              'rejected_speech_keys':[[p,n] for p,n,t in units if has_speech_clause(t)
                                      and not any(c['p']==p and c['s']==n for c in direct)]}
    return result


def j2_signed_nearby(claims, pointers, positions, rejected_speech_keys=None):
    """执行身份：Codex；118：确认只取本句署名；邻句姓名继续留在待核候选。"""
    selected=[]
    for pointer in pointers:
        key=(pointer['p'],pointer['s'])
        for claim in claims:
            if (claim['p'],claim['s']) == key and claim not in selected:
                selected.append(claim)
    return selected


def j2_prepare_packet_v50(material, rows, facts=(), chapter_speakers=None):
    """逐条准备；坏条拒收、署名不明待核，其余条目仍可发送和保存。"""
    from pipeline_output28 import sentences
    table = sentences(material)
    # 执行身份：Codex；131：触发词只决定送不送复核，不决定确认。
    from pipeline_context52 import SPEECH, SPEECH_OBJECT, INNER, has_speech_clause, mentions, subject_before, clause_subject
    requirement_verbs = re.compile(r'叫|让(?!给)|吩咐|命令|逼|催|要求')
    # 执行身份：Codex；132：退门须有可重算的事情主语，缺姓名不算证据。
    def non_speech_structure(plain, quoted, requirements, named):
        if quoted or has_speech_clause(plain) or re.search(r'[:：]', plain):
            return None
        witnesses = []
        for verb in requirements:
            if verb.group() != '让':
                return None
            start = max(plain.rfind(c, 0, verb.start()) for c in '，,；;。！？!?') + 1
            stop = min((p for c in '，,；;。！？!?' if (p := plain.find(c, verb.end())) >= 0), default=len(plain))
            prefix, tail = plain[start:verb.start()], plain[verb.end():stop]
            # “某事让某人明白……”：事情名词占主语位，人物是使役宾语，
            # 心理结果沿用原定位器的 INNER；不能仅因出现“让”就退门。
            event = re.fullmatch(r'\s*(?:(?:也)?因为)?(.+(?:(?:这|那)(?:件)?事|的事))\s*', prefix)
            recipient = next((h for h in named if h[0] >= verb.end() and h[1] <= stop
                              and not plain[verb.end():h[0]].strip()
                              and INNER.match(plain[h[1]:stop].lstrip())), None)
            if event and recipient and not any(h[0] <= start and h[1] >= verb.start() for h in named):
                # 用既有主语定位确认事情名词占位；其前不能藏一位发令者。
                left, right = start + event.start(1), start + event.end(1)
                event_hit = (left, right, event.group(1), event.group(1))
                if clause_subject(plain[left:verb.start()], left, [event_hit]) != event_hit:
                    return None
                witnesses.append({'kind': 'event_subject', 'subject_span': [left, right],
                                  'verb_span': [verb.start(), verb.end()],
                                  'recipient_span': [recipient[0], recipient[1]]})
            elif witnesses and re.fullmatch(r'\s*(?:没|没有|未)', prefix) and re.fullmatch(r'.+的事\s*', tail):
                # 同句后续“没让……的事”是名词短语；须以前面的事情主语为凭。
                # 明示人名/代词或无“的事”的要求句都不能走这条。
                witnesses.append({'kind': 'nominal_event', 'span': [start, stop],
                                  'verb_span': [verb.start(), verb.end()]})
            else:
                return None
        return witnesses
    source_sentences = {}
    quote_pairs = {'“': '”', '「': '」', '『': '』', '‘': '’', '"': '"', "'": "'"}
    for p, parts in table.items():
        closing = []
        for n, text in enumerate(parts, 1):
            plain, quoted = [], False
            for char in text:
                if closing and char == closing[-1]:
                    closing.pop()
                    plain.append(' ')
                elif char in quote_pairs:
                    closing.append(quote_pairs[char])
                    plain.append(' ')
                    quoted = True
                else:
                    plain.append(' ' if closing else char)
                    quoted = quoted or bool(closing and char.strip())
            source_sentences[p, n] = (text, ''.join(plain), quoted)
    context = chapter_speakers or j2_chapter_speakers(material, rows, facts)
    positions = {(p, n): i for i, (p, n, _) in enumerate(context['units'])}
    items, rejected = [], []
    texts = '\n'.join(p['text'] for p in material['paragraphs'])
    for original in rows:
        row = copy.deepcopy(original)
        ident = row.get('_id', '未知条目')
        try:
            section = ident.split(':')[0]
            if section not in SECTIONS:
                raise ValueError('栏目无效')
            one = {f: [row] if f == section else [] for f in SECTIONS}
            checked = validate('J2', one, material)[section][0]
            checked['_id'] = ident
            row = checked
            for k in ('entity', 'target'):
                if row.get(k) and row[k] not in ('未知', '无名', '无名说话人') and row[k] not in context['names'] and row[k] not in texts:
                    raise ValueError('条目指向本章不存在的人物')
            pointers = [{'p': ev['p'], 's': n} for ev in row['ev']
                        for n, t in enumerate(table[ev['p']], 1)
                        if ev['q'] in t or t.strip() and t in ev['q']]
            # 执行身份：Codex；131：S号绑定人物与句号，不给整章所有人重复占位。
            # entity在候选表中存完整选择对象；现有发送与解码原样传递它。
            holder = row.get('entity')
            source_rows = [(x, source_sentences.get((x['p'], x['s']))) for x in pointers]
            direct = j2_signed_nearby(context['direct'], pointers, positions, context['rejected_speech_keys'])
            signed, options, non_speech = [], [], []
            source_non_speech = bool(source_rows)
            direct_quote, speech_seen, requirement_seen, colon_quote = False, False, False, False
            appellation = section == 'aliases' or (section == 'relations' and row.get('aspect') == '称谓关系候选')
            for pointer, source in source_rows:
                if source is None:
                    source_non_speech = False
                    continue
                text, plain, quoted = source
                direct_quote = direct_quote or quoted
                names = {name: name for name in context['names']}
                named = mentions(plain, names)
                local_names = {hit[2] for hit in mentions(text, names)}
                local_names.update(x['entity'] for x in direct if all(x[k] == pointer[k] for k in ('p', 's')))
                if holder in names:
                    local_names.add(holder)
                for name in sorted(local_names):
                    choice = {'entity': name, **pointer}
                    option = {'entity': choice}
                    if option not in options:
                        options.append(option)
                # 沿用v76进门条件；“叫＋名称”仍只是命名，不拿触发词当署名证据。
                requirements = [v for v in requirement_verbs.finditer(plain)
                                if not (v.group() == '叫' and any(
                                    not plain[v.end():hit[0]].strip()
                                    and re.match(r'\s*(?:[，,。！？!?；;]|$)', plain[hit[1]:])
                                    for hit in named if hit[0] >= v.end()))]
                # 退门选项也带句号。它是待核选择，不是已签名人物。
                non_speech_option = {'entity': {'entity': None, **pointer}}
                if non_speech_option not in options:
                    options.append(non_speech_option)
                witness = non_speech_structure(plain, quoted, requirements, named)
                source_non_speech = source_non_speech and witness is not None
                if witness:
                    non_speech.append({'choice': {'entity': None, **pointer}, 'structure': witness})
                requirement_seen = requirement_seen or bool(requirements)
                speech_seen = speech_seen or bool(SPEECH.search(plain))
                colon_quote = colon_quote or any(re.match(r'[^，,。！？!?；;：:]*[:：]', plain[v.end():])
                                                for v in list(SPEECH.finditer(plain)) + requirements)
                if quoted or appellation:
                    # 引语和称谓允许说话人不同于持有人；只取同句原文定位结果。
                    claims = [x for x in direct if all(x[k] == pointer[k] for k in ('p', 's'))]
                else:
                    # 摘句结束位置定位动作所在分句，复用现有主语定位。
                    # 不再要求主语和动作之间只能夹副词，允许中间还有另一个动作。
                    ends = [m.end() for ev in row['ev'] if ev['p'] == pointer['p']
                            for m in re.finditer(re.escape(ev['q']), text)]
                    end = max(ends) if ends else len(plain)
                    while end and plain[end - 1] in '。！？!?\n \t':
                        end -= 1
                    # 复用现有定位器的宾语标记；宾语不截断前面主语的延续。
                    subjects = [hit for hit in named if not re.search(SPEECH_OBJECT, plain[:hit[0]])]
                    subject = subject_before(plain, end, subjects)
                    # 言说后另有明示主语时，外层叙述者不能替内层动作作证。
                    for verb in SPEECH.finditer(plain[:end]):
                        # 外层本身是要求，后面的姓名是被要求的人，不和外层争署名。
                        if any(v.start() == verb.start() and v.end() == verb.end() for v in requirements):
                            continue
                        nested = clause_subject(plain[verb.end():end], verb.end(), named)
                        if nested and (subject is None or nested[2] != subject[2]):
                            # 现有定位同时给出外层与内层主体，不能把其中一个冒作确定证据。
                            subject = None
                            break
                    # 要求里又转给另一人发要求时，不能借外层替内层签名。
                    for previous, verb in zip(requirements, requirements[1:]):
                        nested = clause_subject(plain[previous.end():verb.start()], previous.end(), named)
                        if nested and (subject is None or nested[2] != subject[2]):
                            subject = None
                            break
                    claims = []
                    if subject and not re.match(r'\s*(?:的|被|遭)', plain[subject[1]:]):
                        claims.append({'entity': subject[2], **pointer})
                for claim in claims:
                    if claim not in signed:
                        signed.append(claim)
            implicit_gate = bool(not source_rows or direct_quote or colon_quote or speech_seen
                                 or any(ev['p'] in context.get('reported_speech_paragraphs', []) for ev in row['ev'])
                                 or any([x['p'], x['s']] in context['rejected_speech_keys'] for x in pointers))
            required = bool(holder in ('未知', '无名', '无名说话人') or row.get('requires_speaker')
                            or row.get('speaker') is not None or requirement_seen or implicit_gate)
            selected = row.get('speaker')
            # 保留进门前结果，跨生成/复核两轮传递；退门不得抹掉其他待核原因。
            if '_speaker_gate_before' not in row:
                row['_speaker_gate_before'] = {'status': row.get('confirmation_status', '已确认'),
                                               'reason': row.get('confirmation_reason')}
            content = ' '.join(str(row.get(k) or '') for k in ('value', 'aspect', 'alias', 'anchor'))
            content_names = mentions(content, {name: name for name in context['names']})
            content_demand = any(v.group() not in ('让', '叫') or subject_before(content, v.start(), content_names)
                                 for v in requirement_verbs.finditer(content))
            if not source_non_speech or has_speech_clause(content) or content_demand:
                non_speech = []
            # 进门只准备候选；已有speaker字符串不能替带句号的复核选择。
            row.update(confirmation_status='待核' if required else '已确认',
                       confirmation_reason='说话人未定/待核' if required else None, requires_speaker=required)
            if required:
                row['unverified_speaker'] = selected if selected is not None else row.get('unverified_speaker')
                row['speaker'] = None
            items.append({'id': ident, 'candidate': row, 'pointers': pointers,
                          'signed_evidence': signed, 'speaker_candidates': options,
                          'non_speech_evidence': non_speech})
        except (ValueError, TypeError, KeyError) as exc:
            rejected.append({'id': ident, 'reason': str(exc), 'row': original,
                             'paragraph_ids': [e.get('p') for e in original.get('ev', [])]})
    return {'method': J2_V50, 'items': items, 'chapter_speakers': context}, rejected


def j2_pre_dispatch_v50(packet, material, prior_rejections=(), revisions=()):
    """整章依据随包传递；程序重新核本包单条，不因拆包丢整章人物。"""
    if any(p.get('id') in set(prior_rejections) for p in revisions) or revisions:
        raise ValueError('拒收条目不能进入修订包；修订须独立处理')
    context = packet['chapter_speakers']
    # 防止把伪造的直接署名表带进子包，人物集合取固定整章上下文。
    recomputed = j2_chapter_speakers(material, [{'entity': n} for n in context['names']])
    if context['direct'] != recomputed['direct'] or context['units'] != recomputed['units'] or context.get('rejected_speech_keys') != recomputed['rejected_speech_keys']:
        raise ValueError('整章署名依据改变')
    fresh, rejected = j2_prepare_packet_v50(material, [x['candidate'] for x in packet['items']], chapter_speakers=context)
    if rejected:
        raise ValueError('发送包仍含未分流的不合规条目')
    if len({x['id'] for x in packet['items']}) != len(packet['items']):
        raise ValueError('候选编号重复')
    for old, new in zip(packet['items'], fresh['items']):
        for key in ('id', 'pointers', 'signed_evidence', 'speaker_candidates'):
            if old[key] != new[key]:
                raise ValueError('程序候选或整章证据被改写')
    return packet


def j2_partition_saved(candidate):
    """已复核条目分确认与待核；待核不进入确认资料或评分确认输入。"""
    confirmed = {f: [] for f in SECTIONS}
    pending = []
    for f in SECTIONS:
        for row in candidate[f]:
            if row.get('confirmation_status') == '待核':
                pending.append({'section': f, 'id': row['_id'], 'status': '待核',
                                'reason': row.get('confirmation_reason'), 'row': copy.deepcopy(row)})
            else:
                confirmed[f].append(copy.deepcopy(row))
    return confirmed, pending


def j2_save_partition(confirmed, pending, rejected):
    """保存前按编号消除旧待核残留；确认与拒收冲突不能静默覆盖。"""
    confirmed_ids={r['_id'] for r in flatten('J2',confirmed)}
    rejected=list({r['id']:r for r in rejected}.values())
    rejected_ids={r['id'] for r in rejected}
    if confirmed_ids & rejected_ids:raise ValueError('J2同一编号同时确认和拒收')
    pending=list({r['id']:r for r in pending if r['id'] not in confirmed_ids|rejected_ids}.values())
    pending_ids={r['id'] for r in pending}
    assert not confirmed_ids & pending_ids and not rejected_ids & pending_ids
    return confirmed,pending,rejected


def j2_enrich_candidates(material, candidate, facts):
    """最小别名与关系候选，仅列可逐字回查的称谓线索，不自动合并实体。"""
    out = copy.deepcopy(candidate)
    context = j2_chapter_speakers(material, flatten('J2', out), facts)
    for p in material['paragraphs']:
        text = p['text']
        for name in context['names']:
            for match in re.finditer(re.escape(name) + r'(?:的)?(媳妇|妻子|丈夫|父亲|母亲|儿子|女儿|[一二三四五六七八九十大]+(?:哥|姐|弟|妹|嫂|叔)|老[一二三四五六七八九十大小]+|小(?:哥|姐|弟|妹))', text):
                alias = match.group(0)
                quote = alias
                common = {'ev': [{'p': p['paragraph_id'], 'q': quote}]}
                out['aliases'].append({'entity': name, 'alias': alias, 'speaker': None,
                                      'scope': [p['paragraph_id']], 'confirmation_status': '待核',
                                      'requires_speaker': True, **common})
                out['relations'].append({'entity': name, 'target': alias, 'relation_type': '亲属',
                    'aspect': '称谓关系候选', 'value': alias, 'layer': '未知',
                    'confirmation_status': '待核', 'requires_speaker': True, **common})
    for f in SECTIONS:
        for n, row in enumerate(out[f]):
            row['_id'] = f + ':' + str(n)
    # 言语类事实仍要求署名；未知的aspect保留，不靠填分类制造内容进步。
    by_source = {fact['text']: fact for fact in facts}
    for row in flatten('J2', out):
        fact = by_source.get(row.get('value'))
        if fact and fact.get('kind') == '言语':
            row['requires_speaker'] = True
            row['speaker'] = fact.get('speaker')
    return out


def j2_prepare_packet(material, rows, facts=(), chapter_speakers=None, itemwise=False):
    """发送前固化候选、连续出处和可用署名；模型没有证据、修订输出栏。"""
    if itemwise:
        return j2_prepare_packet_v50(material, rows, facts, chapter_speakers)
    from pipeline_output28 import sentences
    table = sentences(material)
    speakers = speaker_candidates(material, rows, direct_only=True)
    units = [(pid, number) for pid, parts in table.items() for number, sentence in enumerate(parts, 1)
             if sentence.strip('“”「」『』"。！？\n \t')]
    positions = {point: n for n, point in enumerate(units)}
    items, blocked = [], []
    for row in rows:
        pointers = []
        evidence(row.get('ev'), material)
        for ev in row['ev']:
            numbers = [number for number, sentence in enumerate(table[ev['p']], 1)
                       if ev['q'] in sentence or sentence.strip() and sentence in ev['q']]
            if not numbers:
                raise ValueError('J2候选没有可用句号出处')
            pointers.extend({'p': ev['p'], 's': number} for number in numbers)
        signed = [claim for claim in speakers if any(
            (claim['p'], claim['s']) in positions and (pointer['p'], pointer['s']) in positions
            and abs(positions[(claim['p'], claim['s'])] - positions[(pointer['p'], pointer['s'])]) <= 1
            for pointer in pointers)]
        speaker = row.get('speaker')
        if speaker is not None and not any(claim['entity'] == speaker for claim in signed):
            blocked.append({'id': row['_id'], 'reason': '候选说话归属缺署名证据', 'row': copy.deepcopy(row)})
            continue
        items.append({'id': row['_id'], 'candidate': copy.deepcopy(row), 'pointers': pointers,
                      'signed_evidence': signed})
    return {'method': 'program_candidates_short_decisions_v47', 'items': items,
            'chapter_speakers': j2_chapter_speakers(material, rows)}, blocked


def j2_pre_dispatch(packet, material, prior_rejections=(), revisions=()):
    """拒收和修订是独立本地步骤；非法差量或署名在发送前硬拒。"""
    if packet.get('method') == J2_V50:
        return j2_pre_dispatch_v50(packet, material, prior_rejections, revisions)
    from pipeline_output28 import resolve_pointer, sentences
    if set(packet) not in ({'method', 'items'}, {'method', 'items', 'chapter_speakers'}) or packet.get('method') != 'program_candidates_short_decisions_v47':
        raise ValueError('短判断发送包只允许程序候选，不携带修订或自由证据')
    rejected = set(prior_rejections)
    if any(patch.get('id') in rejected for patch in revisions):
        raise ValueError('发送前拦截：拒收条目不能进入修订包')
    if revisions:
        raise ValueError('短判断包不携带修订；修订须独立处理后重新列候选')
    ids = set()
    rows = [item['candidate'] for item in packet['items']]
    context = packet.get('chapter_speakers')
    allowed = (j2_chapter_speakers(material, [{'entity': n} for n in context['names']])['direct']
               if context else speaker_candidates(material, rows, direct_only=True))
    table = sentences(material)
    units = [(pid, number) for pid, parts in table.items() for number, sentence in enumerate(parts, 1)
             if sentence.strip('“”「」『』"。！？\n \t')]
    positions = {point: n for n, point in enumerate(units)}
    for item in packet['items']:
        if set(item) != {'id', 'candidate', 'pointers', 'signed_evidence'}:
            raise ValueError('程序候选包字段无效')
        if item['id'] in ids or item['id'] != item['candidate']['_id']:
            raise ValueError('候选编号重复或错指')
        ids.add(item['id'])
        evidence(item['candidate']['ev'], material)
        expected = [{'p': ev['p'], 's': number} for ev in item['candidate']['ev']
                    for number, sentence in enumerate(table[ev['p']], 1)
                    if ev['q'] in sentence or sentence.strip() and sentence in ev['q']]
        if expected != item['pointers']:
            raise ValueError('发送前拦截：候选证据指针与原行不符')
        for pointer in item['pointers']:
            resolve_pointer(pointer, material)
        for claim in item['signed_evidence']:
            if claim not in allowed or not any(
                    (claim['p'], claim['s']) in positions and (pointer['p'], pointer['s']) in positions
                    and abs(positions[(claim['p'], claim['s'])] - positions[(pointer['p'], pointer['s'])]) <= 1
                    for pointer in item['pointers']):
                raise ValueError('发送前拦截：说话人没有程序署名证据')
        speaker = item['candidate'].get('speaker')
        if speaker is not None and not any(claim['entity'] == speaker for claim in item['signed_evidence']):
            raise ValueError('发送前拦截：候选说话归属缺署名证据')
    return packet


def j2_wire_payload(packet, material):
    """发送视图只带内容及证据指针；完整原行在程序包保留，不重复回传引语。"""
    from pipeline_output28 import sentences
    used = {pointer['p'] for item in packet['items'] for pointer in item['pointers']}
    used.update(claim['p'] for item in packet['items'] for claim in item['signed_evidence'])
    selected = {(pointer['p'], pointer['s']) for item in packet['items'] for pointer in item['pointers']}
    selected.update((claim['p'], claim['s']) for item in packet['items'] for claim in item['signed_evidence'])
    table = sentences(material)
    source_view = [[pid, [[number, sentence] for number, sentence in enumerate(parts, 1) if (pid, number) in selected]]
                   for pid, parts in table.items() if pid in used]
    fields = {section: sorted({k for item in packet['items'] if item['id'].split(':')[0] == section
                              for k in item['candidate'] if k not in ('ev', '_id')})
              for section in SECTIONS if any(item['id'].split(':')[0] == section for item in packet['items'])}
    signatures, items = [], []
    for item in packet['items']:
        indexes = []
        for claim in item['signed_evidence']:
            signature = [claim['entity'], claim['p'], claim['s']]
            if signature not in signatures:
                signatures.append(signature)
            indexes.append(signatures.index(signature))
        items.append([item['id'], [item['candidate'].get(k) for k in fields[item['id'].split(':')[0]]],
                      [[pointer['p'], pointer['s']] for pointer in item['pointers']], indexes])
    if packet['method'] == J2_V50:
        for item, wire in zip(packet['items'], items):
            wire.append({'S'+str(i): x['entity'] for i, x in enumerate(item['speaker_candidates'], 1)})
        return {'output_protocol': 'enum_paragraph_v57', 'enum_tables': {k: ENUMS57[k] for k in ('reason', 'accept')},
                'method': packet['method'], 'candidate_fields': fields,
                'item_fields': ['id', 'candidate', 'pointers', 'signed_evidence', 'speaker_candidates'],
                'items': items, 'signed_evidence': signatures, 'paragraphs': source_view}
    return {'output_protocol': 'enum_paragraph_v57', 'enum_tables': {k: ENUMS57[k] for k in ('reason', 'accept')},
                'method': packet['method'], 'candidate_fields': fields,
            'item_fields': ['id', 'candidate', 'pointers', 'signed_evidence'], 'items': items,
            'signed_evidence': signatures, 'paragraphs': source_view}


def j2_revision_step(candidate, rejected_ids, patches, material):
    """独立修订入口；完整差量留包，拒收资料不能修订后冒充已接受。"""
    out = copy.deepcopy(candidate)
    rows = {row['_id']: row for row in flatten('J2', out)}
    seen = set()
    for patch in patches:
        ident = patch.get('id')
        if ident in set(rejected_ids):
            raise ValueError('拒收条目不能进入独立修订步骤')
        changes = patch.get('changes')
        if (set(patch) != {'id', 'changes'} or ident not in rows or ident in seen
                or not isinstance(changes, dict) or not changes or '_id' in changes
                or set(changes) - set(rows[ident])):
            raise ValueError('独立修订编号或字段无效')
        seen.add(ident)
        rows[ident].update(copy.deepcopy(changes))
    validated = validate('J2', out, material)
    for field in SECTIONS:
        for old, row in zip(out[field], validated[field]):
            row['_id'] = old['_id']
    prepared, blocked = j2_prepare_packet(material, flatten('J2', validated))
    if blocked:
        raise ValueError('独立修订产生无署名候选，未提交')
    j2_pre_dispatch(prepared, material)
    return validated


def j2_short_decisions(value, packet, legacy=False):
    from pipeline_output28 import OutputOverflow
    if value.get('overflow') is True:
        raise OutputOverflow('J2短判断超过输出上界')
    return normalize_decisions57(value, packet, legacy=legacy)


def j2_apply_short(candidate, decisions, packet, material, normalized=False):
    j2_pre_dispatch(packet, material)
    checked = decisions if normalized else j2_short_decisions(decisions, packet)
    return j2_apply_checked57(candidate, checked, packet, material)


def j2_apply_checked57(candidate, checked, packet, material):
    """内部纯应用层；运行入口先验包，离线历史包也复用这一份判法。"""
    by_id = {v['id']: v for v in checked['verdicts']}
    out, rejected = {field: [] for field in SECTIONS}, []
    for field in SECTIONS:
        for row in candidate[field]:
            if row['_id'] not in by_id:
                continue
            verdict = by_id[row['_id']]
            if verdict.get('_pending') or row.get('_normalization_pending'):
                saved = copy.deepcopy(row)
                saved.update(confirmation_status='待核', confirmation_reason=verdict.get('_pending_reason', '前轮归一待核'),
                             _normalization_pending=True)
                if saved.get('speaker') is not None:
                    saved['unverified_speaker'] = saved['speaker']
                saved['speaker'] = None
                out[field].append(saved)
            elif verdict['accept']:
                saved = copy.deepcopy(row)
                if packet.get('method') == J2_V50:
                    item = next(x for x in packet['items'] if x['id'] == row['_id'])
                    saved = copy.deepcopy(item['candidate'])
                    if saved.get('requires_speaker') or verdict.get('speaker') is not None:
                        saved['requires_speaker'] = True
                        # 执行身份：Codex；131：核选人、句号、原文连接与既有持有人规则。
                        selected = verdict.get('speaker')
                        proof = selected if isinstance(selected, dict) else {}
                        complete = set(proof) == {'entity', 'p', 's'} and type(proof.get('s')) is int
                        in_candidates = complete and any(x['entity'] == proof for x in item['speaker_candidates'])
                        pointed = complete and {'p': proof['p'], 's': proof['s']} in item['pointers']
                        # 旧包也从原文重建，不信外带的署名表。
                        fresh, blocked = j2_prepare_packet_v50(material, [item['candidate']],
                                                             chapter_speakers=packet.get('chapter_speakers'))
                        linked = bool(not blocked and fresh['items'] and proof in fresh['items'][0]['signed_evidence'])
                        from pipeline_output28 import sentences
                        source = sentences(material).get(proof.get('p'), []) if complete else []
                        quoted = False
                        closing = []
                        pairs = {'“': '”', '「': '」', '『': '』', '‘': '’', '"': '"', "'": "'"}
                        for number, text in enumerate(source, 1):
                            for char in text:
                                inside = bool(closing)
                                if closing and char == closing[-1]:
                                    closing.pop()
                                elif char in pairs:
                                    closing.append(pairs[char])
                                if number == proof['s'] and (inside or closing):
                                    quoted = True
                        appellation = field == 'aliases' or (field == 'relations' and saved.get('aspect') == '称谓关系候选')
                        holder_ok = quoted or appellation or proof.get('entity') == saved.get('entity')
                        # 执行身份：Codex；132：非言说选择从原句重算，不信包外带的退门依据。
                        exit_proved = bool(not blocked and fresh['items'] and any(
                            x['choice'] == proof for x in fresh['items'][0]['non_speech_evidence']))
                        holder_known = saved.get('entity') not in ('未知', '无名', '无名说话人')
                        if in_candidates and pointed and proof.get('entity') is None and exit_proved and holder_known:
                            before = saved['_speaker_gate_before']
                            saved.update(speaker=None, requires_speaker=False,
                                         confirmation_status=before['status'], confirmation_reason=before['reason'])
                        elif in_candidates and pointed and linked and holder_ok:
                            saved.update(speaker=proof['entity'], confirmation_status='已确认', confirmation_reason=None)
                        else:
                            saved.update(speaker=None, confirmation_status='待核',
                                         confirmation_reason='署名证据未连上/待核' if holder_ok else '说话人与持有人不一致/待核',
                                         unverified_speaker=proof.get('entity') or saved.get('unverified_speaker'))
                out[field].append(saved)
            else:
                rejected.append({'id': row['_id'], 'reason': verdict['reason'], 'row': copy.deepcopy(row),
                                 'paragraph_ids': [e['p'] for e in row['ev']]})
    # 保留准备时编号，避免复核子包重新编号后错配。
    validated = validate('J2', out, material)
    for field in SECTIONS:
        for old, row in zip(out[field], validated[field]):
            row['_id'] = old['_id']
    return validated, rejected


def speaker_candidates_legacy(material, candidate, direct_only=False, strict_j2=False):
    """本章引号外署名宽列：人物到动词或冒号引语最多64字，前后各一句。

    候选是可能的署名，不是裁定；模型只能勾选程序给出的完整指针。
    引号跨段保持状态，台词中的人物和说话动词不产生署名候选。
    """
    from pipeline_output28 import sentences
    names = set()
    for row in candidate:
        for field in ('subject', 'entity'):
            name = row.get(field)
            if isinstance(name, str) and name.strip() and name not in ('未知', '无名', '无名说话人'):
                names.add(name)
        names.update(name for name in row.get('mentions', []) if isinstance(name, str) and name.strip()
                     and name not in ('未知', '无名', '无名说话人'))
    table, units, quote_end = sentences(material), [], None
    closing = {'“': '”', '「': '」', '『': '』', '"': '"'}
    for paragraph in material['paragraphs']:
        masked = []
        for char in paragraph['text']:
            if quote_end:
                masked.append(' ')
                if char == quote_end:
                    quote_end = None
            elif char in closing:
                quote_end = closing[char]
                masked.append(' ')
            else:
                masked.append(char)
        offset = 0
        for number, text in enumerate(table[paragraph['paragraph_id']], 1):
            plain = ''.join(masked[offset:offset + len(text)])
            units.append((paragraph['paragraph_id'], number, plain, text))
            offset += len(text)
    verbs = re.compile(r'说(?!法|服|明书)|(?<!知|通|铁|大|小)道(?!路|理|具|德)|问(?!题)|喊|答(?!案)|叫|回应|开口|补充|解释|叮嘱')
    found = set()
    meaningful = [index for index, (_, _, _, text) in enumerate(units)
                  if text.strip('“”「」『』"。！？\n \t')]
    positions = {index: position for position, index in enumerate(meaningful)}
    for index, (_, _, plain, original) in enumerate(units):
        for name in sorted(names):
            for occurrence in re.finditer(re.escape(name), plain):
                tail = plain[occurrence.end():occurrence.end() + 65]
                colon_quotes = re.finditer(r'[:：]\s*[“「『"]', original[occurrence.end():occurrence.end() + 65])
                # 只排除“对（于）X来说”；动作后的“走过来说…”仍是言语。
                comparison = {m.end() - 1 for m in re.finditer(r'对(?:于)?[^。！？：:，,\n]{1,64}?来说', plain)}
                anchors = [v.start() for v in verbs.finditer(tail)
                           if occurrence.end() + v.start() not in comparison] + [q.start() for q in colon_quotes]
                if not any(not re.search(r'[。！？\n]', tail[:position]) for position in anchors):
                    continue
                position = positions[index]
                for neighbor in ([index] if direct_only else meaningful[max(0, position - 1):position + 2]):
                    p, number, _, _ = units[neighbor]
                    found.add((name, p, number))
    order = {p: index for index, p in enumerate(table)}
    return [{'entity': name, 'p': p, 's': number}
            for name, p, number in sorted(found, key=lambda x: (order[x[1]], x[2], x[0]))]


def speaker_candidates(material, candidate, direct_only=False, strict_j2=False):
    from pipeline_context52 import speech_table, person_pool, has_speech_clause
    from pipeline_output28 import sentences
    entities={'people':[{'entity':r.get('entity',r.get('subject'))} for r in candidate if r.get('entity',r.get('subject'))]}
    names=person_pool(material,candidate,entities)
    table=sentences(material);found=set()
    rows=speech_table(material,candidate,entities,names)
    for row in rows:
        for ev in row['evidence']:
            allowed=('直接署名','引语后署名','紧邻下段明示','唯一承接署名') if direct_only or strict_j2 else ('直接署名','引语后署名','双人轮次候选','代词承接','B上下文候选','唯一承接署名')
            if ev['method'] not in allowed:
                continue  # 轮次和代词推定只能进候选，不冒作直接署名。
            evidence_p=ev.get('support_p',row['p'])
            chunks=table[evidence_p];offset=0;number=1
            for n,t in enumerate(chunks,1):
                if offset<=ev['offset']<offset+len(t):number=n;break
                offset+=len(t)
            found.add((ev['entity'],evidence_p,number))
    if not direct_only and not strict_j2:
        units=[(p,n) for p,ss in table.items() for n,t in enumerate(ss,1) if t.strip('“”「」『』"。！？\n \t')]
        for name,p,n in list(found):
            if (p,n) in units:
                i=units.index((p,n))
                found.update((name,pp,nn) for pp,nn in units[max(0,i-1):i+2]
                             if not has_speech_clause(table[pp][nn-1]))
    order={p:i for i,p in enumerate(table)}
    return [{'entity':n,'p':p,'s':s} for n,p,s in sorted(found,key=lambda x:(order[x[1]],x[2],x[0]))]


def normalize_speaker_claims(review, candidates, material):
    """补缺省空栏，清除结构合法但不在候选内的证明；不改裁定、理由或差量。"""
    from pipeline_output28 import sentences, size, REVIEW_CLAIM_MAX_BYTES
    if not isinstance(review, dict) or not isinstance(review.get('verdicts'), list):
        return review, []
    table = sentences(material)
    allowed = {(c['entity'], c['p'], c['s']) for c in candidates}
    result, changes = copy.deepcopy(review), []
    for verdict in result['verdicts']:
        if not isinstance(verdict, dict):
            continue  # 结构错误仍由原机检拒绝。
        if 'speaker_claims' not in verdict:
            verdict['speaker_claims'] = []
            changes.append({'verdict_id': verdict.get('id'), 'field': 'speaker_claims',
                            'action': 'default_empty'})
            continue
        if not isinstance(verdict['speaker_claims'], list):
            continue
        kept = []
        for index, claim in enumerate(verdict['speaker_claims']):
            # 指针错误、单项超界和额外字段仍交原机检；不借规范化绕过这些保护。
            valid = (isinstance(claim, dict) and set(claim) == {'entity', 'p', 's'}
                     and size(claim) <= REVIEW_CLAIM_MAX_BYTES
                     and isinstance(claim['entity'], str) and bool(claim['entity'])
                     and isinstance(claim['p'], str) and claim['p'] in table
                     and type(claim['s']) is int and 1 <= claim['s'] <= len(table[claim['p']]))
            if valid and (claim['entity'], claim['p'], claim['s']) not in allowed:
                changes.append({'verdict_id': verdict.get('id'), 'field': f'speaker_claims[{index}]',
                                'action': 'drop_outside_candidates', 'claim': copy.deepcopy(claim)})
            else:
                kept.append(claim)
        verdict['speaker_claims'] = kept
    return result, changes


def speaker_candidate_errors(verdict, candidates, material):
    """收集本裁定全部失败，不在首个证明处退出。"""
    from pipeline_output28 import sentences
    table = sentences(material)
    allowed = {(c['entity'], c['p'], c['s']) for c in candidates}
    errors = []
    def fail(field, detail):
        errors.append({'verdict_id': verdict.get('id'), 'field': field, 'error': detail,
                       'legal_example': {'reason': '符合提交原段', 'speaker_claims': []}})
    claims = verdict.get('speaker_claims')
    if not isinstance(claims, list):
        fail('speaker_claims', '复核缺说话归属检查栏')
        return errors
    for index, claim in enumerate(claims):
        field = 'speaker_claims[' + str(index) + ']'
        if not isinstance(claim, dict):
            fail(field, '说话证明须为对象')
            continue
        entity, p, number = claim.get('entity'), claim.get('p'), claim.get('s')
        if not isinstance(entity, str) or not entity or not isinstance(p, str) or p not in table or type(number) is not int or not 1 <= number <= len(table[p]):
            fail(field, '说话证明的人物、段号或句号指针无效')
        elif claim.get('q') != table[p][number - 1]:
            fail(field, '还原的说话证明与原句指针不一致')
        elif (entity, p, number) not in allowed:
            fail(field, '说话证明不在程序署名候选集合，须改选候选或清空')
    return errors


def check_speaker_claims(verdict, candidate, material, candidates=None):
    if candidates is not None:
        errors = speaker_candidate_errors(verdict, candidates, material)
        if errors:
            raise ValueError(json.dumps({'kind': 'speaker_candidate_membership', 'errors': errors},
                                        ensure_ascii=False, separators=(',', ':')))
        return
    def fail(field, detail):
        raise ValueError(json.dumps({'verdict_id': verdict.get('id'), 'field': field,
                                    'error': detail,
                                    'legal_example': {'reason': '符合提交原段', 'speaker_claims': []}},
                                   ensure_ascii=False, separators=(',', ':')))
    claims = verdict.get('speaker_claims')
    if not isinstance(claims, list):
        fail('speaker_claims', '复核缺说话归属检查栏')
    texts = {p['paragraph_id']: p['text'] for p in material['paragraphs']}
    proved = set()
    for index, claim in enumerate(claims):
        evidence([{'p': claim.get('p'), 'q': claim.get('q')}], material)
        entity = claim.get('entity')
        if not isinstance(entity, str) or not entity:
            fail('speaker_claims[' + str(index) + '].entity', '说话主体缺失')
        narration = re.sub(r'“[^”]*”|「[^」]*」|"[^"\n]*"', '', texts[claim['p']])
        pattern = re.escape(entity) + r'(?:轻声|低声|大声|笑着|接着|又|还|便|就|才|却)?(?:说|道|喊|问|答|叫)'
        claim_plain = re.sub(r'“[^”]*”|「[^」]*」|"[^"\n]*"', '', claim['q'])
        if not re.search(pattern, narration) or not re.search(pattern, claim_plain):
            fail('speaker_claims[' + str(index) + ']', '复核理由中的说话主体没有署名证据')
        proved.add(entity)
    names = set()
    for row in candidate:
        for field in ('subject', 'entity'):
            if isinstance(row.get(field), str):
                names.add(row[field])
        names.update(x for x in row.get('mentions', []) if isinstance(x, str))
    for name in names:
        if re.search(re.escape(name) + r'(?:说|说道|喊|问|答|叫)', verdict.get('reason', '')) and name not in proved:
            fail('reason', '复核理由的说话归属没有逐项证据')


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


def normalize_rejected_patches(review):
    """明确拒收优先；只删除结构合法且属于该拒收条目的差量，不改原件。"""
    if not isinstance(review, dict) or not isinstance(review.get('verdicts'), list) or not isinstance(review.get('patches'), list):
        return review, []
    verdicts = review['verdicts']
    if any(not isinstance(v, dict) or not isinstance(v.get('id'), str) for v in verdicts):
        return review, []
    if len({v['id'] for v in verdicts}) != len(verdicts):
        return review, []  # 重复裁定不能据其中一条丢弃差量，交原机检拒绝。
    rejected = {v['id'] for v in verdicts if v.get('accept') is False}
    kept, removed = [], []
    for patch in review['patches']:
        if (isinstance(patch, dict) and set(patch) == {'id', 'changes'}
                and isinstance(patch['id'], str) and patch['id'] in rejected
                and isinstance(patch['changes'], dict) and patch['changes']):
            removed.append(patch['id'])
        else:
            kept.append(patch)
    return {**copy.deepcopy(review), 'patches': copy.deepcopy(kept)}, removed


def review_apply(role, candidate, review, material, facts=None, previous=None, candidates=None):
    if role == 'B':
        review, _ = normalize_rejected_patches(review)
    rows = flatten(role, candidate)
    wanted = {r['_id'] for r in rows}
    verdicts = review.get('verdicts')
    if not isinstance(verdicts, list) or len(verdicts) != len(wanted) or {r.get('id') for r in verdicts} != wanted:
        raise ValueError('复核未逐项覆盖或重复')
    if role == 'B':
        candidates = speaker_candidates(material, rows) if candidates is None else candidates
        errors = [error for verdict in verdicts
                  for error in speaker_candidate_errors(verdict, candidates, material)]
        # 未能安全清除的非法差量仍同包反馈；不能更改拒收裁定。
        by_id = {verdict['id']: verdict for verdict in verdicts}
        if isinstance(review.get('patches'), list):
            for index, patch in enumerate(review['patches']):
                if isinstance(patch, dict) and patch.get('id') in by_id and by_id[patch['id']].get('accept') is False:
                    errors.append({'verdict_id': patch['id'], 'field': 'patches[' + str(index) + ']',
                                   'error': '拒收条目不能同时提交修订；保留拒收裁定并删除该条差量',
                                   'legal_example': {'accept': False, 'speaker_claims': [], 'patches': []}})
        if errors:
            kind = ('review_protocol_conflict' if any(e['field'].startswith('patches[') for e in errors)
                    else 'speaker_candidate_membership')
            raise ValueError(json.dumps({'kind': kind, 'errors': errors},
                                        ensure_ascii=False, separators=(',', ':')))
    else:
        for verdict in verdicts:
            check_speaker_claims(verdict, rows, material)
    patches = review.get('patches')
    if not isinstance(patches, list):
        raise ValueError('复核缺修订差量数组')
    patch_map = {}
    originals = {row['_id']: row for row in rows}
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != {'id', 'changes'}:
            raise ValueError('修订只允许编号与改动字段')
        ident, changes = patch['id'], patch['changes']
        if ident not in wanted or ident in patch_map or not isinstance(changes, dict) or not changes:
            raise ValueError('修订编号错指、重复或差量为空')
        if '_id' in changes or set(changes) - set(originals[ident]):
            raise ValueError('修订不能改编号或新增未定义字段')
        if any(originals[ident][k] == v for k, v in changes.items()):
            raise ValueError('修订差量重复回传未改字段')
        patch_map[ident] = changes
    by_id = {r['id']: r for r in verdicts}
    if any(not by_id[ident].get('accept') for ident in patch_map):
        raise ValueError('拒收条目不能同时提交修订')
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
            if 'patch' in verdict:
                raise ValueError('旧式全行patch协议已停用')
            kept.append({**row, **patch_map.get(row['_id'], {})})
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
    if not value.get('rows'):
        raise ValueError('保存计划为空，A阶段未完成')
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
            'J2_confirmation_audit': [],
            'review_audit': {k: [] for k in ('old_plan_rows', 'fact_chapters', 'source_chapters', 'plan_history', 'open_plan_keys', 'review_flags')}}
    for material in materials:
        chapter = material['chapter']
        part = current[chapter]
        facts = part.get('facts', [])
        pred['J2_confirmation_audit'].append({'chapter': chapter,
            'confirmed': sum(len(part.get('J2', {}).get(f, [])) for f in SECTIONS),
            'pending': len(part.get('J2_pending', [])), 'rejected': len(part.get('J2_rejected', [])),
            'pending_scoring_policy': '未确认，不计对；A/B/C原评分输入与评分器保持'})
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
    return b_scoring_projection(pred)


# 执行身份：Codex；111第1—3条：短编号归一，错误只影响本条。
ENUMS57 = {
    'reason': {'R0': '待核', 'R1': '符合原段', 'R2': '证据不足', 'R3': '归属不符',
               'R4': '时间不符', 'R5': '内容重复', 'R6': '分类不符',
               'R7': '内容超出原段', 'R8': '待独立修订'},
    'accept': {'D0': None, 'D1': True, 'D2': False},
    'status': {'T'+str(i): v for i, v in enumerate(STATUSES, 1)},
    'kind': {'K'+str(i): v for i, v in enumerate(('事件', '言语', '心理', '状态'), 1)},
    'layer': {'L'+str(i): v for i, v in enumerate(('现场', '回忆', '恒常', '未知'), 1)},
    'main_tag': {'C'+str(i): v for i, v in enumerate(TAGS, 1)},
}


def enum_value57(field, value, legacy=False):
    table = ENUMS57['main_tag' if field == 'secondary_tag' else field]
    if isinstance(value, str) and value in table:
        return table[value]
    if legacy and any(type(value) is type(v) and value == v for v in table.values()):
        return value
    if legacy and field == 'reason' and value == '符合提交原段':
        return '符合原段'
    raise ValueError('未知'+field+'编号')


def protocol_payload57(role, payload, material, review=False):
    """只生成发送视图；稳定长编号留在程序包，枚举表不取自模型或金标。"""
    out = copy.deepcopy(payload)
    out['output_protocol'] = 'enum_paragraph_v57'
    out['enum_tables'] = {k: copy.deepcopy(ENUMS57[k]) for k in (('reason', 'accept', 'status', 'kind', 'layer', 'main_tag') if review else ('reason', 'status') if role == 'A' else ('kind', 'layer') if role == 'B' else ('main_tag', 'layer'))}
    if role == 'B' and not review:
        from pipeline_output28 import pointer_payload
        out['paragraphs'] = pointer_payload(material)
    if review:
        choices = payload.get('speaker_candidates')
        if choices is None:
            choices = speaker_candidates(material, payload.get('rows', []), direct_only=True)
        out['speaker_candidates'] = {'S'+str(i): c for i, c in enumerate(choices, 1)}
    if role == 'A':
        from pipeline_plan52 import seed_holders
        for i, seed in enumerate(out.get('plan_seeds', []), 1):
            seed['seed_id'] = 'N'+str(i)
            seed['holders'] = {'H'+str(n): v for n, v in enumerate(
                sorted(seed_holders(seed)), 1)}
            if 'candidate_columns' in seed:
                holder_ids = {name: key for key, name in seed['holders'].items()}
                seed['candidate_columns'] = {column: [holder_ids[n] for n in names]
                                             for column, names in seed['candidate_columns'].items()}
                seed.pop('candidate_sources', None)
        refs = [f[0] for f in payload.get('facts', [])]
        out['fact_ids'] = {'F'+str(i): key for i, key in enumerate(refs, 1)}
        # 事实表首列也用短号，保留内容与段号供模型判断。
        for i, fact in enumerate(out.get('facts', []), 1):
            fact[0] = 'F'+str(i)
        refmap = {v: k for k, v in out['fact_ids'].items()}
        for seed in out.get('plan_seeds', []):
            seed['source'] = refmap.get(seed['source'], seed['source'])
            seed['basis'] = [refmap.get(x, x) for x in seed.get('basis', [])]
        out['previous_ids'] = {'P'+str(i): p['key'] for i, p in enumerate(payload.get('previous_plans', []), 1)}
        previous_refmap={v:k for k,v in out['previous_ids'].items()}
        for row in out.get('rows',[]):
            for field in ('source','fulfilled','condition_ref'):
                if row.get(field) is not None:row[field]=refmap.get(row[field],row[field])
            if 'basis' in row:row['basis']=[refmap.get(v,v) for v in row['basis']]
            if row.get('key') is not None:row['key']=previous_refmap.get(row['key'],row['key'])
        for i, old in enumerate(out.get('previous_plans', []), 1):
            old['key'] = 'P'+str(i)
    if role == 'C':
        from pipeline_context52 import person_pool
        out['viewpoints'] = {'V0': '全知', 'V1': '第一人称', **{
            'V'+str(i): n for i, n in enumerate(person_pool(material), 2)}}
    return out


def generation_normalize57(role, value, material, packet, facts=(), previous=(), legacy=False):
    """旧响应必须显式走离线兼容；未知长号不模糊匹配，也不按行序猜种子。"""
    from pipeline_output28 import resolve_pointer
    from pipeline_plan52 import check_local_plans
    fields = ['rows'] if role in ('A', 'B') else ['paragraphs', 'scenes']
    result = {f: [] for f in fields}; pending = []; log = []
    wire = protocol_payload57(role, packet, material)
    for field in fields:
        rows = value.get(field)
        if not isinstance(rows, list):
            raise ValueError('输出栏目须为数组：'+field)
        for i, raw in enumerate(rows):
            row = copy.deepcopy(raw); ident = role+':'+str(i)
            try:
                if not isinstance(row, dict):
                    raise ValueError('条目须为对象')
                if role == 'A':
                    wide_row = not legacy and 'holder_column' in row
                    if row.get('key') is not None and not legacy:
                        row['key'] = wire['previous_ids'][row['key']]
                    if row.get('key') is None:
                        selected = row.get('seed_id')
                        short = {'N'+str(n): s for n, s in enumerate(packet.get('plan_seeds', []), 1)}
                        seed = (next((s for s in packet.get('plan_seeds', []) if s['seed_id'] == selected), None)
                                if legacy else short.get(selected))
                        if seed is None:
                            raise ValueError('未知种子编号，保留待核，不猜长号')
                        row['seed_id'] = seed['seed_id']
                        if not legacy:
                            from pipeline_plan52 import seed_holders
                            holders = {'H'+str(n): v for n, v in enumerate(sorted(seed_holders(seed)), 1)}
                            row['holder'] = holders[row['holder']]
                        if wide_row:
                            column = row.pop('holder_column')
                            if row['holder'] not in seed.get('candidate_columns', {}).get(column, []):
                                raise ValueError('持有人不在所选栏位')
                            if not isinstance(row.get('content'), str) or not row['content'].strip() or not any(row['content'] in e['q'] for e in seed['ev']):
                                raise ValueError('计划内容必须逐字摘自种子窗口')
                            allowed = {'seed_id', 'holder', 'key', 'content', 'status', 'fulfilled', 'condition_ref'}
                            if set(row) - allowed:
                                raise ValueError('宽列短判断含未定义字段')
                            row.update(key=None, deadline=None, condition=None, reason='R1')
                            row.setdefault('fulfilled', None); row.setdefault('condition_ref', None)
                    row['status'] = enum_value57('status', row.get('status'), legacy)
                    if legacy:
                        # 旧A理由是解释文本，不参与状态/收拒；原文单独留在日志，不拿它当通过证据。
                        log.append({'id': ident, 'field': 'reason', 'before': row.get('reason'),
                                    'after': '旧响应解释未参与裁定', 'action': 'archive_optional_legacy_explanation'})
                        row['reason'] = '旧响应解释未参与裁定'
                    else:
                        row['reason'] = enum_value57('reason', row.get('reason'))
                        if row['reason'] == '待核':
                            raise ValueError('模型标记待核')
                        for f in ('source', 'fulfilled', 'condition_ref'):
                            if row.get(f) is not None:
                                row[f] = wire['fact_ids'][row[f]]
                        if 'basis' in row:
                            row['basis'] = [wire['fact_ids'][x] for x in row['basis']]
                    row = bind_plan_seeds({'rows': [row]}, packet.get('plan_seeds', []))['rows'][0]
                    row['state_paragraphs']=[]
                    row['condition_paragraphs']=[]
                    if row.get('key') is not None:row.pop('_seed_paragraphs',None)
                if role == 'B':
                    for f in ('kind', 'layer'):
                        row[f] = enum_value57(f, row.get(f), legacy)
                if role == 'C' and field == 'paragraphs':
                    for f in ('main_tag', 'secondary_tag'):
                        if row.get(f) is not None:
                            row[f] = enum_value57(f, row[f], legacy)
                    if not legacy:
                        row['viewpoint'] = wire['viewpoints'][row['viewpoint']]
                if 'ev' in row:
                    row['ev'] = [resolve_pointer(e, material) if set(e) == {'p', 's'} else e for e in row['ev']]
                    if not legacy and any(set(e) != {'p', 's'} for e in raw.get('ev', [])):
                        raise ValueError('证据只接受程序段号/句号')
                if role == 'C':
                    # C本轮为程序旁路；模型协议仍逐条核，不用默认值补坏段。
                    if field == 'scenes':
                        if not legacy:
                            row['layer'] = enum_value57('layer', row.get('layer'))
                            for cell_field in ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere', 'present'):
                                for cell in row.get(cell_field, []):
                                    cell['ev'] = [resolve_pointer(e, material) for e in cell['ev']]
                        for cell_field in ('location', 'light_weather', 'objects_visuals', 'sounds_smells', 'atmosphere', 'present'):
                            for cell in row.get(cell_field, []):
                                evidence(cell.get('ev'), material)
                    checked = copy.deepcopy(row)
                    if field == 'paragraphs':
                        p = next(p for p in material['paragraphs'] if p['paragraph_id'] == row['p'])
                        row['quote'] = p['text']
                        checked = validate('C', {'paragraphs': [row], 'scenes': []}, dict(material, paragraphs=[p]))[field][0]
                    else:
                        valid = {p['paragraph_id'] for p in material['paragraphs']}
                        if not row.get('paragraph_ids') or set(row['paragraph_ids']) - valid:
                            raise ValueError('场景段号未知')
                    checked['_id'] = field+':'+str(i)
                else:
                    checked = validate(role, {'rows': [row]}, material, facts, previous)['rows'][0]
                    checked['_id'] = ident
                    if role == 'A':
                        check_local_plans({'rows': [checked]}, packet, previous)
                        check_plan_seed_scope({'rows': [checked]}, packet.get('plan_seeds', []), previous)
                result[field].append(checked)
                if not legacy:
                    log.append({'id': ident, 'before': raw, 'after': checked, 'action': 'decode_numbers'})
            except (ValueError, KeyError, TypeError, StopIteration) as exc:
                pending.append({'id': ident, 'status': '待核', 'reason': str(exc), 'row': raw})
                log.append({'id': ident, 'before': raw, 'after': None, 'action': 'pending', 'error': str(exc)})
    if role == 'B':
        result['unresolved'] = copy.deepcopy(value.get('unresolved', []))
    return result, pending, log


# 执行身份：Codex；124：只容错accept的确定语义，不放宽其他编号。
def normalize_accept70(value):
    if type(value) is bool:
        return ('D1', 'bool_true') if value else ('D2', 'bool_false')
    if value is None:
        return 'D0', 'null'
    if isinstance(value, str) and value in ENUMS57['accept']:
        return value, None
    raise ValueError('未知accept编号')


def normalize_decisions57(value, packet, legacy=False):
    """完整保留原裁定；不认识的编号或理由只落待核，不改成收。"""
    if not isinstance(value, dict) or not isinstance(value.get('verdicts'), list):
        raise ValueError('裁定须为数组')
    verdicts = []; log = []; wanted = {x['id'] for x in packet['items']}
    accept_normalized = {'bool_true': 0, 'bool_false': 0, 'null': 0}
    by_id = {}
    for raw in value['verdicts']:
        if not isinstance(raw, dict) or not isinstance(raw.get('id'), str) or raw['id'] not in wanted:
            log.append({'before': raw, 'after': None, 'action': 'pending_unknown_id'})
            continue
        by_id.setdefault(raw['id'], []).append(raw)
    for item in packet['items']:
        ident = item['id']; rows = by_id.get(ident, [])
        raw = rows[0] if len(rows) == 1 else None
        out = {'id': ident, 'accept': False, 'reason': '待核', 'speaker': None}
        error = None
        try:
            if set(value) != {'verdicts'}:
                raise ValueError('裁定包含未定义字段')
            if raw is None:
                raise ValueError('漏项或重复编号')
            accept_code, normalized_kind = normalize_accept70(raw.get('accept'))
            out['accept'] = ENUMS57['accept'][accept_code]
            if normalized_kind:
                accept_normalized[normalized_kind] += 1
            if normalized_kind == 'null':
                raise ValueError('模型未给明确裁定')
            out['reason'] = enum_value57('reason', raw.get('reason'), legacy)
            if out['accept'] is None or out['reason'] == '待核':
                raise ValueError('模型标记待核')
            if out['accept'] != (out['reason']=='符合原段'):
                raise ValueError('接受编号与理由编号不一致')
            selected = raw.get('speaker')
            if selected is not None:
                names = [x['entity'] for x in item.get('speaker_candidates', [])]
                if legacy:
                    if selected not in names:
                        raise ValueError('署名不在程序候选')
                    out['speaker'] = selected
                else:
                    out['speaker'] = {'S'+str(i): n for i, n in enumerate(names, 1)}[selected]
            if set(raw) - {'id', 'accept', 'reason', 'speaker'}:
                raise ValueError('裁定含未定义字段')
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        if error:
            # 保留可识别的原收拒，待核标记优先，apply时不能进confirmed。
            out.update(_pending=True, _pending_reason=error)
        verdicts.append(out)
        if error or not legacy:
            log.append({'id': ident, 'before': raw if raw is not None else rows,
                        'after': out, 'action': 'pending' if error else 'decode_numbers'})
    return {'verdicts': verdicts, '_normalization_log': log, '_normalized57': True,
            'accept_normalized': accept_normalized}


def normalize_review57(role, value, rows, material, legacy=False, packet=None):
    """可选署名坏字段清除；坏裁定或坏差量单条待核，其他裁定照常核。"""
    from pipeline_output28 import check_review_shape, size, REVIEW_PATCH_MAX_BYTES, REVIEW_CLAIMS_MAX_BYTES
    value = copy.deepcopy(value)
    wire = protocol_payload57(role, packet or {'rows': rows}, material, review=True)
    claims = list(wire['speaker_candidates'].values())
    items = [{'id': row['_id'], 'speaker_candidates': []} for row in rows]
    simplified = {'verdicts': [{k: v for k, v in r.items() if k != 'speaker_claims'}
                             if isinstance(r, dict) else r for r in value.get('verdicts', [])]}
    result = normalize_decisions57(simplified, {'items': items}, legacy)
    logs = result.pop('_normalization_log'); result.pop('_normalized57')
    raws = {r.get('id'): r for r in value.get('verdicts', []) if isinstance(r, dict) and isinstance(r.get('id'), str)}
    raw_patches = value.get('patches', [])
    patches_overflow = isinstance(raw_patches, list) and size(raw_patches) > REVIEW_PATCH_MAX_BYTES
    claim_total = sum(size(r.get('speaker_claims', [])) for r in raws.values())
    pending = []; checked = []; patches = []; by_id = {r['_id']: r for r in rows}
    for v in result['verdicts']:
        ident = v['id']; raw = raws.get(ident, {})
        rawclaims = raw.get('speaker_claims', [])
        kept = []
        if claim_total > REVIEW_CLAIMS_MAX_BYTES:
            logs.append({'id': ident, 'field': 'speaker_claims', 'before': rawclaims, 'after': [], 'action': 'drop_optional_claims_over_bound'})
            rawclaims = []
        for claim in rawclaims if isinstance(rawclaims, list) else [rawclaims]:
            decoded = claim if legacy else {'S'+str(i): c for i, c in enumerate(claims, 1)}.get(claim) if isinstance(claim, str) else None
            if decoded in claims:
                kept.append(copy.deepcopy(decoded))
            else:
                logs.append({'id': ident, 'field': 'speaker_claims', 'before': claim,
                             'after': None, 'action': 'drop_optional_invalid_claim'})
        v.pop('speaker', None); v['speaker_claims'] = kept
        ps = value.get('patches', [])
        own = [p for p in ps if isinstance(p, dict) and p.get('id') == ident] if isinstance(ps, list) else None
        try:
            if v.get('_pending'):
                raise ValueError(v.get('_pending_reason', '裁定待核'))
            if own and patches_overflow:
                raise ValueError('差量数组超过既有1024字节上界')
            if own is None or len(own) > 1:
                raise ValueError('差量结构错误或重号')
            if not v['accept'] and own:
                logs.append({'id': ident, 'before': own, 'after': [], 'action': 'preserve_reject_drop_delta'})
                own = []
            for patch in own:
                if set(patch) != {'id', 'changes'} or not isinstance(patch['changes'], dict) or not patch['changes']:
                    raise ValueError('差量结构错误')
                changes = patch['changes']
                if any(k.startswith('_') for k in changes) or set(changes) - set(by_id[ident]):
                    raise ValueError('差量字段未知')
                for field in ('status', 'kind', 'layer', 'main_tag', 'secondary_tag', 'reason'):
                    if field in changes and changes[field] is not None:
                        changes[field] = enum_value57(field, changes[field], legacy)
                if not legacy:
                    from pipeline_output28 import resolve_pointer
                    if 'ev' in changes:
                        changes['ev'] = [resolve_pointer(e, material) for e in changes['ev']]
                    if 'speaker' in changes and changes['speaker'] is not None:
                        changes['speaker'] = wire['speaker_candidates'][changes['speaker']]['entity']
                    if role == 'A':
                        for f in ('source', 'fulfilled', 'condition_ref'):
                            if changes.get(f) is not None:
                                changes[f] = wire['fact_ids'][changes[f]]
                        if 'basis' in changes:
                            changes['basis'] = [wire['fact_ids'][x] for x in changes['basis']]
            one = check_review_shape({'verdicts': [v], 'patches': own}, [by_id[ident]], material)
            checked.extend(one['verdicts']); patches.extend(one['patches'])
        except (ValueError, TypeError, KeyError) as exc:
            pending.append({'id': ident, 'status': '待核', 'reason': str(exc), 'row': by_id[ident], 'raw_verdict': raw})
            logs.append({'id': ident, 'before': raw, 'after': None, 'action': 'pending', 'error': str(exc)})
    for p in value.get('patches', []) if isinstance(value.get('patches', []), list) else []:
        if not isinstance(p, dict) or not isinstance(p.get('id'), str) or p['id'] not in by_id:
            logs.append({'before': p, 'after': None, 'action': 'pending_unknown_patch_id'})
    return {'verdicts': checked, 'patches': patches,
            'accept_normalized': result['accept_normalized']}, pending, logs


def review_apply57(role, candidate, review, material, facts=None, previous=None, **kwargs):
    """归一后的单条裁定独立落盘；未裁定行保留待核，不凭缺省值通过。"""
    verdicts = {v['id']: v for v in review.get('verdicts', [])}
    patchmap = {p['id']: p['changes'] for p in review.get('patches', [])}
    fields = ['rows'] if role in ('A', 'B') else list(SECTIONS) if role == 'J2' else ['paragraphs', 'scenes']
    out = {f: [] for f in fields}; removed = []
    for f in fields:
        for row in candidate[f]:
            ident = row['_id']; v = verdicts.get(ident)
            if not v or v.get('_pending'):
                removed.append({'id': ident, 'status': '待核', 'reason': '裁定无效或缺失', 'row': row}); continue
            if not v['accept']:
                removed.append({'id': ident, 'status': '拒收', 'reason': v['reason'], 'row': row}); continue
            changed = {**copy.deepcopy(row), **patchmap.get(ident, {})}
            try:
                if role == 'C':
                    out[f].append(changed); continue
                if role == 'A':
                    from pipeline_plan52 import check_state_structure
                    check_state_structure(changed,material,facts or [],previous or [])
                one = {k: [changed] if k == f else [] for k in fields}
                valid = validate(role, one, material, facts, previous)[f][0]
                valid['_id'] = ident; out[f].append(valid)
            except (ValueError, KeyError, TypeError) as exc:
                removed.append({'id': ident, 'status': '待核', 'reason': str(exc), 'row': row, 'patch': patchmap.get(ident)})
    return out, removed
