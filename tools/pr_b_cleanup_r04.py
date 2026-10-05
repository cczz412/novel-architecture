# 执行身份：Codex
"""事实正文的窄清理步骤：只删审稿说明，保留故事内容和原键。"""
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import pr_layers_headroom_r03 as gates
from pr_pipeline_r02 import empty_result, dump
from pr_review_r04 import judge

SCHEMA = '''本步只清理已有事实句中的审稿说明，不补漏、不重新抽句、不改写故事。
只输出五数组keep/exclude/flag/replace/add；exclude与add必须空。每个facts旧键恰好一次。
完整结构：{"keep":["输入旧键"],"exclude":[],"flag":[],"replace":[{"key":"输入旧键","text":"清理后事实","reason":"删除哪类审稿说明","evidence":[{"p":"输入段号","q":"连续逐字短引"}]}],"add":[]}。
replace只用key，不用local_key；evidence必须是对象数组，不能是字符串。每个证据同时写p和q。
keep表示整句都是故事内容；replace只删除审稿者添加的解释、证据不足说明、真假免责声明，
其text保留其余原字原句（句末标点可整理），evidence仍用对应原段的逐字短引。
flag只用于删与不删确实无法判断的句。不能仅因说明谨慎就保留它。
例如虚构旧句“阿岚关上木门；本句没有明说她已经睡着。”，只删除分号后的审稿话。
如果旧句是“阿岚关上木门；她没有睡着，而是在修椅子。”，后半是故事事实，须保留。
人物的台词、心声、真实否定、条件、推测、未来承诺均是故事内容，不能因为尚未兑现删掉。
不要改人名、代词、数量、期限、窄动作、原因和反应；本步不替它们做同义润色。
read_only_chapter_context只帮助判断归属。复核必须同时核两件事：删掉的是否故事内容、
正文里是否仍有审稿说明。保留审稿说明就是本步明确错误，不能以“不矛盾”“没误删”通过。
coverage核指定facts的这两项职责；本步没有其他段补漏职责。
'''

# 只选疑点送模型；词表不直接删字，不能当语义真值。
EDITOR = re.compile(r'本[章节句段回]|原文|旁白|正文|叙述|据此|不(?:证明|等于|扩大|推成|倒|擅|补|写成|作现实)|'
                    r'(?:没有|未)(?:写|给|说明|交代|确认|明确|直接确认)|尚未|不是(?:已|已经|当前|世界|现实)|'
                    r'这(?:是|只是|些仍是)|只确认|只作本书|保留.{0,8}[，,]|未知|未解释')
QUOTES = re.compile(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"')


def suspicious(text):
    unquoted = QUOTES.sub(lambda m: ' ' * len(m.group()), text)
    return bool(EDITOR.search(unquoted))


def deletion_only(before, after):
    """只容许保留原字顺序；标点可整理，正文不可增字、换词。"""
    normalize = lambda s: re.sub(r'[\s，,。.;；：:！？!?、…]+', '', s)
    old, new = normalize(before), normalize(after)
    if not new:
        return False
    position = 0
    for char in new:
        position = old.find(char, position)
        if position < 0:
            return False
        position += 1
    return True


def cleanup_gate(raw, material):
    if not isinstance(raw, dict):
        raise ValueError('窄清理须为五数组对象')
    shape_errors = []
    for field in ('keep', 'exclude', 'flag', 'replace', 'add'):
        if not isinstance(raw.get(field), list):
            shape_errors.append(dict(field=field, error='须为数组'))
    for index, row in enumerate(raw.get('replace', []) if isinstance(raw.get('replace'), list) else []):
        if not isinstance(row, dict):
            shape_errors.append(dict(path=f'replace[{index}]', error='须为对象'))
            continue
        if not isinstance(row.get('key'), str):
            shape_errors.append(dict(path=f'replace[{index}]', field='key', error='须使用输入旧键，字段名为key'))
        evidence = row.get('evidence')
        if not isinstance(evidence, list) or not evidence or any(not isinstance(e, dict) for e in evidence):
            shape_errors.append(dict(path=f'replace[{index}]', field='evidence', error='须为非空对象数组，每项有p段号和q逐字短引，不能是字符串'))
    if shape_errors:
        return raw, shape_errors, []
    raw, errors, log = gates.b_gate(raw, material)
    if raw['add'] or raw['exclude']:
        errors.append(dict(field='窄清理范围', error='本步不能新增或排除整条事实'))
    facts = {f['local_key']: f for f in material['facts']}
    for row in raw['replace']:
        if isinstance(row, dict) and row.get('key') in facts and isinstance(row.get('text'), str):
            if not deletion_only(facts[row['key']]['text'], row['text']):
                errors.append(dict(key=row['key'], field='只删不改写', error='只删除审稿说明，其他故事文字保留，不换同义词或添加正文'))
    return raw, errors, log


def valid_subset(raw, material):
    """坏条目单独隔离；只将过窄检查的原键送独立复核。"""
    facts = {f['local_key']: f for f in material['facts']}
    candidate = dict(keep=[], exclude=[], flag=[], replace=[], add=[])
    seen, rejected = set(), []
    keys = [row.get('key') if isinstance(row, dict) else row for kind in ('keep', 'replace', 'flag')
            for row in (raw.get(kind, []) if isinstance(raw.get(kind), list) else [])]
    occurrences = Counter(key for key in keys if isinstance(key, str))
    for kind in ('keep', 'replace'):
        for row in raw.get(kind, []) if isinstance(raw.get(kind), list) else []:
            key = row.get('key') if isinstance(row, dict) else row
            if not isinstance(key, str) or key not in facts or occurrences[key] != 1 or key in seen:
                rejected.append(dict(key=key, error='旧键越界或重复'))
                continue
            stub = dict(keep=[], exclude=[], flag=[], replace=[], add=[])
            stub[kind] = [row]
            _, errors, _ = cleanup_gate(stub, dict(material, facts=[facts[key]]))
            if errors:
                rejected.extend(dict(e, key=key) for e in errors)
                continue
            seen.add(key)
            candidate[kind].append(row)
    selected = dict(material, facts=[f for f in material['facts'] if f['local_key'] in seen])
    return candidate, selected, rejected


def run_cleanup(data, doc, effective_facts, task, client, model, policy, folder, receipt, replay_source=None):
    all_facts = []
    for f in effective_facts:
        f = copy.deepcopy(f)
        if not f.get('paragraph_ids'):
            f['paragraph_ids'] = [e['paragraph_id'] for e in f.get('evidence', []) if isinstance(e, dict) and e.get('paragraph_id')]
        all_facts.append(f)
    selected = [f for f in all_facts if suspicious(f['text'])]
    summary = dict(chapter=data['chapter'], candidates=len(selected), changed=0, uncertain=0)
    degraded = []
    for offset in range(0, len(selected), 24):
        facts = selected[offset:offset + 24]
        positions = {p for f in facts for p in f['paragraph_ids']}
        material = dict(book_id=data['book_id'], chapter=data['chapter'], group='cleanup' + str(offset // 24),
                        facts=facts, paragraphs=[p for p in data['paragraphs'] if p['paragraph_id'] in positions],
                        context_paragraphs=[p for p in data['paragraphs'] if p['paragraph_id'] not in positions],
                        owned_paragraph_ids=sorted(positions), scope_limits=data['scope_limits'],
                        new_key_prefix='unused:cleanup:', review_scope='指定旧句必须清掉审稿说明并保留故事内容；审稿话即使不与故事矛盾也不能通过；无其他段补漏职责')
        label = 'B_cleanup' + str(offset // 24)
        if replay_source:
            origin = Path(replay_source)
            source_receipt = json.loads((origin / 'run_receipt.json').read_text())
            if source_receipt['book'] != receipt['book'] or source_receipt.get('b_cleanup_input') != receipt.get('b_cleanup_input'):
                raise ValueError('清理复放来源书或事实输入版本不一致')
            origin_done = origin / folder.name / (label + '_done.json')
            record = json.loads(origin_done.read_text())
            raw, pending = record['raw'], record['pending']
            referenced = {r.get('key') if isinstance(r, dict) else r for k in ('keep','flag','replace') for r in raw.get(k, [])}
            expected = {f['local_key'] for f in facts}
            if referenced != expected:
                raise ValueError('复放候选旧键范围与当前材料不一致')
            dump(folder / (label + '_replay.json'), dict(execution_identity='Codex', source=str(origin_done),
                 source_sha256=hashlib.sha256(origin_done.read_bytes()).hexdigest(), input_fact_sha256=hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), incremental_generation_requests=0))
        else:
            raw, pending = task(client, model, policy, SCHEMA, material,
                                lambda v: cleanup_gate(v, material), folder, label, receipt, 'B')
            record = json.loads((folder / (label + '_done.json')).read_text()) if (folder / (label + '_done.json')).exists() else {}
        # 整批机检失败时，坏条目不能阻断其余条目的独立复核。
        if replay_source or receipt.get('review_model') and not record.get('reviews'):
            candidate, reviewed_material, rejected = valid_subset(raw, material)
            review_model = receipt.get('review_model')
            if not review_model or review_model == model:
                raise ValueError('清理复放或部分复核必须有独立模型')
            reviews = judge(client, review_model, receipt['policies'][review_model]['parameters'], SCHEMA,
                            reviewed_material, candidate, folder, label + '_subset', 'B') if reviewed_material['facts'] else []
            approved = {r['id'] for r in reviews if r['decision'] == '通过'}
            accepted = dict(keep=[r for i,r in enumerate(candidate['keep']) if f'keep[{i}]' in approved],
                            replace=[r for i,r in enumerate(candidate['replace']) if f'replace[{i}]' in approved],
                            exclude=[], add=[], flag=[])
            accepted_keys = set(accepted['keep']) | {r['key'] for r in accepted['replace']}
            accepted['flag'] = [f['local_key'] for f in facts if f['local_key'] not in accepted_keys]
            pending = rejected + [dict(path=r['id'], error=r['reason'], independent=True, decision=r['decision']) for r in reviews if r['decision'] != '通过']
            dump(folder / (label + '_subset_done.json'), dict(execution_identity='Codex', raw=accepted, reviews=reviews,
                 pending=pending, rewrites=0, rejected_keys=sorted(expected - accepted_keys) if replay_source else accepted['flag']))
            raw = accepted
        # 最终候选仍过窄检查，不让有限重写失败偷偷改变故事。
        fact_by_key = {f['local_key']: f for f in facts}
        for row in raw.get('replace', []):
            if not isinstance(row, dict) or row.get('key') not in fact_by_key:
                continue
            key = row['key']
            stub = dict(keep=[], exclude=[], flag=[], replace=[row], add=[])
            _, errors, _ = cleanup_gate(stub, dict(material, facts=[fact_by_key[key]]))
            if errors:
                gates.flag(doc, data, 'B', key, '审稿话清理未通过窄检查，保留原候选', fact_by_key[key]['paragraph_ids'])
                continue
            existing = next((f for f in doc['B'] if f.get('local_key') == key), None)
            if existing is None:
                existing = dict(change_id='R04:B:cleanup:' + hashlib.sha256(key.encode()).hexdigest()[:16],
                                book_id=data['book_id'], chapter=data['chapter'], operation='替换',
                                old_record_keys=[key], local_key=key)
                doc['B'].append(existing)
            existing.update(text=row['text'], reason=row.get('reason', ''),
                            evidence=[dict(paragraph_id=gates.full_pid(e['p'], data), quote=e['q']) for e in row['evidence']])
            if row['text'] != fact_by_key[key]['text']:
                summary['changed'] += 1
            for scope in doc['review_audit']['fact_chapters']:
                known = any(key in scope.get(field, []) for field in ('kept_old_keys', 'flagged_old_keys', 'revised_old_keys'))
                if known:
                    for field in ('kept_old_keys', 'flagged_old_keys'):
                        scope[field] = [k for k in scope.get(field, []) if k != key]
                    if key not in scope['revised_old_keys']:
                        scope['revised_old_keys'].append(key)
        for key in raw.get('flag', []):
            if key in fact_by_key:
                summary['uncertain'] += 1
                gates.flag(doc, data, 'B', key, '审稿说明和故事内容的边界仍不确定，保留原候选', fact_by_key[key]['paragraph_ids'])
        for error in pending:
            if error.get('independent'):
                gates.flag(doc, data, 'B', error.get('key'), error.get('error', '清理复核疑点未解决'))
        if pending:
            degraded.append(label)
    receipt.setdefault('b_cleanup', []).append(summary)
    return degraded
