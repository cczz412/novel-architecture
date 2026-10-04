# 执行身份：Codex
"""R04增量抽取：三层独立保存、有限重写、输入指纹检查点。"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from pr_pipeline_r02 import (OUT, MODELS, RULES, SYSTEM, read_book, empty_result,
                             assemble, dump, external)
from pr_ark_client_r02 import Client
from pr_resolved_r02 import groups, chapter_facts
import pr_layers_headroom_r03 as gates
from pr_b_only_r02 import SCHEMA as B_SCHEMA
from pr_c_steps_r03 import ANNOTATE, SCENES
from pr_review_r04 import judge, isolate

MODELS = (*MODELS, 'xiaomi/mimo-v2.6-flash', 'xiaomi/mimo-v2.6-pro')

RULE = RULES.replace('C 与事实同遍抽：', 'C由单独步骤处理：')
DISCOVER = gates.A_DISCOVER + '''
本步old_plan_rows只含意向字段与字段未知的旧召回，其他字段由程序保留。
输入existing只用于查重，不要求复述历史。计划正文写窄目标动作，主体名只放subject；
例如虚构人物阿岚说“我明早修木桥”，content写“明早修木桥”，deadline写“明早”。
旧召回与当前事实必须核原段，不能只因旧行属于意向字段就立计划。
旧行若来自早章且已经对应已有计划，只说明沿用，不重新建晚章计划。
'''
UPDATE = gates.A_UPDATE + '''
状态不变时basis为空，fulfilled和condition_ref继承有效旧引用；状态变化才写本章变化依据。
没有履约结果时不能因“准备”“打算”判兑现。理由须对应本条具体目标与所见证据。
'''
B_FIDELITY = B_SCHEMA + '''
逐条比原段再决定沿用。替换只修明确错误：元语言、非逐字直引、漏掉的原因反应、
错误归属、否定/条件/情态丢失。不能为了文风换同义词，不能把可能改为确定。
一句里独立心声、情绪、反应、原因均要保留；拆句后每个明写片段仍须有事实句承接。
程序只校验逐字和格式，语义保真由本步负责。不要用原文称、叙述称等作为故事归属。
'''


META_TERMS = ('原文', '本章', '本段', '本回叙述', '旁白', '叙述称', '正文', '材料未', '文本未', '不能据此', '无法据此', '不进错率', '待复核', '审稿')


def b_gate(raw, data):
    raw, errors, conversions = gates.b_gate(raw, data)
    facts = {r['local_key']:r for r in data['facts']}
    paragraphs = {r['paragraph_id']:r['text'] for r in data['paragraphs'] + data.get('context_paragraphs', [])}
    def inspect(text, ids, **where):
        original = '\n'.join(paragraphs.get(k, '') for k in ids)
        hits = [t for t in META_TERMS if t in text and t not in original]
        if hits:
            errors.append(dict(field='正文框架', error='原段没有这些审稿框架词：'+'、'.join(hits)+'；保留故事内容，修正文后才可沿用或替换', **where))
    for key in raw['keep']:
        if key in facts:
            row = facts[key]
            inspect(row['text'], row.get('paragraph_ids', []), key=key)
    for kind in ('replace', 'add'):
        for i, row in enumerate(raw[kind]):
            if isinstance(row, dict) and isinstance(row.get('text'), str):
                inspect(row['text'], [gates.full_pid(e.get('p'), data) for e in row.get('evidence', []) if isinstance(e, dict)], path=f'{kind}[{i}]', key=row.get('key'))
    return raw, errors, conversions


def isolate_metadata(raw, errors):
    raw = copy.deepcopy(raw)
    keys = {e['key'] for e in errors if e.get('field') == '正文框架' and e.get('key')}
    raw['keep'] = [k for k in raw.get('keep', []) if k not in keys]
    raw['replace'] = [r for r in raw.get('replace', []) if r.get('key') not in keys]
    for key in sorted(keys):
        if key not in raw.setdefault('flag', []):
            raw['flag'].append(key)
    bad_adds = {int(e['path'][4:-1]) for e in errors if e.get('field') == '正文框架' and str(e.get('path', '')).startswith('add[')}
    raw['add'] = [r for i, r in enumerate(raw.get('add', [])) if i not in bad_adds]
    return raw


def pending_flags(doc, data, layer, pending):
    # 转换器处理结构错误；独立判断与被隔离的新增项也须进入作者负担账。
    for error in pending:
        path = str(error.get('path', ''))
        if error.get('independent') or layer == 'B' and error.get('field') == '正文框架' and path.startswith('add['):
            key = error.get('key')
            pids = [error['paragraph_id']] if error.get('paragraph_id') else None
            gates.flag(doc, data, layer, key, f"{path or key or '候选'}：" + error.get('error', '具体疑点未解决'), pids)
            flag = doc['review_audit']['review_flags'][-1]
            if not key:
                flag['fact_keys'] = []
            if error.get('independent'):
                flag['category'] = '管线语义黄标'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source(path):
    p = Path(path).resolve()
    allowed = [OUT, OUT.parent / '管线修复_R03']
    if not any(p.is_relative_to(root) for root in allowed):
        raise ValueError('继承材料只允许R03或R04交付目录')
    return p


def task(client, model, policy, schema, material, gate, folder, label, receipt, layer):
    """检查点匹配才能复用；中断已保存响应也不再付费重抽。"""
    review_model = receipt.get('review_model') if layer in receipt.get('review_layers', '') else None
    dependencies = {n: hashlib.sha256((Path(__file__).parent / n).read_bytes()).hexdigest() for n in ('pr_incremental_r04.py', 'pr_review_r04.py', 'pr_layers_headroom_r03.py', 'pr_pipeline_r02.py', 'pr_normalize_v2_r03.py', 'pr_resolved_r02.py', 'pr_compact_bc_r02.py', 'pr_ark_client_r02.py', 'pr_c_steps_r03.py', 'pr_b_only_r02.py', 'pr_chapter_c_r02.py')}
    stamp = digest(dict(model=model, policy=policy, schema=schema, material=material, review_model=review_model, upgrade_model=receipt.get('upgrade_model'), dependencies=dependencies,
                        rule=RULE, version='r04-1',
                        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        gate_sha256=hashlib.sha256(Path(gates.__file__).read_bytes()).hexdigest()))
    done = folder / (label + '_done.json')
    if done.exists():
        record = json.loads(done.read_text())
        if record['input_sha256'] != stamp:
            raise ValueError('检查点输入或配置变化，须另开输出目录：' + label)
        receipt['checkpoint_hits'] += 1
        receipt['upgrade_items_used'] = receipt.get('upgrade_items_used', 0) + record.get('upgrade_count', 0)
        return record['raw'], record['pending']
    messages = [dict(role='system', content=SYSTEM), dict(role='user', content=RULE + '\n' + schema + '\n输入材料：\n' + json.dumps(material, ensure_ascii=False, separators=(',', ':')))]
    original = messages
    raw, errors, first, reviews = {}, [], None, []
    upgrade_before = receipt.get('upgrade_items_used', 0)
    for attempt in range(2):
        reviews = []
        path = folder / (label + f'_response_{attempt}.json')
        if path.exists():
            meta = json.loads((folder / (label + '_input.json')).read_text())
            if meta['input_sha256'] != stamp:
                raise ValueError('已有响应配置不一致：' + label)
            response = json.loads(path.read_text())
        else:
            dump(folder / (label + '_input.json'), dict(execution_identity='Codex', input_sha256=stamp, layer=layer, model=model))
            response = client.call(model, messages, policy, max_tokens=8000 if layer != 'B' else 12000)
            dump(path, response)
        try:
            raw, errors, conversions = gate(gates.parse(response))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            errors = [dict(path=label, error=str(exc))]
            conversions = []
        dump(folder / (label + f'_gate_{attempt}.json'), dict(execution_identity='Codex', errors=errors, conversions=conversions))
        if not errors and review_model:
            if review_model == model:
                raise ValueError('独立复核必须与生成模型不同')
            policies = receipt['policies']
            reviews = judge(client, review_model, policies[review_model]['parameters'], schema, material, raw, folder, label+'_review'+str(attempt), layer)
            undecided = [r['id'] for r in reviews if r['decision'] == '不确定']
            upgrade_model = receipt.get('upgrade_model')
            room = max(0, 4 - receipt.get('upgrade_items_used', 0))
            if upgrade_model and undecided and room:
                selected = undecided[:room]
                upgraded = judge(client, upgrade_model, policies[upgrade_model]['parameters'], schema, material, raw, folder, label+'_upgrade'+str(attempt), layer, selected)
                receipt['upgrade_items_used'] = receipt.get('upgrade_items_used', 0) + len(selected)
                replacement = {r['id']:r for r in upgraded}
                reviews = [replacement.get(r['id'],r) for r in reviews]
            errors.extend(dict(path=r['id'], field=r.get('field'), error=r['reason'], independent=True, decision=r['decision']) for r in reviews if r['decision'] != '通过')
        signature = digest(errors)
        if first is None:
            first = signature
        if not errors or reviews and all(r['decision'] != '明确错误' for r in reviews):
            break
        if attempt == 0:
            messages = original + [dict(role='assistant', content=response['choices'][0]['message'].get('content') or '{}'), dict(role='user', content='这些是具体机检错误：' + json.dumps(errors, ensure_ascii=False) + '。只修错误，保留其他正确内容，再输出本步完整对象。总共只允许这一次重写。')]
    if layer == 'B' and all(isinstance(raw.get(k), list) for k in ('keep','replace','add')):
        raw = isolate_metadata(raw, errors)
    if reviews:
        raw = isolate(raw, reviews)
    record = dict(execution_identity='Codex', input_sha256=stamp, layer=layer, model=model,
                  raw=raw, reviews=reviews, upgrade_count=receipt.get('upgrade_items_used',0)-upgrade_before, pending=errors, rewrites=attempt, no_progress=bool(errors) and digest(errors) == first)
    dump(done, record)
    return raw, errors


def inherited(path, chapter, layer):
    p = source(path)
    doc = json.loads((p / 'prediction.json').read_text())
    receipt = json.loads((p / 'run_receipt.json').read_text())
    if chapter not in receipt['completed_chapters']:
        raise ValueError('继承源没有交付本章：' + chapter)
    out = empty_result()
    if layer == 'B':
        out['B'] = [r for r in doc['B'] if r.get('chapter') == chapter]
        for field in ('fact_chapters', 'source_chapters'):
            out['review_audit'][field] = [r for r in doc['review_audit'][field] if r.get('chapter') == chapter]
    elif layer == 'C':
        out['C'] = [r for r in doc['C'] if r.get('chapter') == chapter]
    else:
        histories = doc['review_audit']['plan_history']
        for h in histories:
            states = [s for s in h['states'] if s['chapter'] == chapter]
            if states:
                out['review_audit']['plan_history'].append(dict(h, states=states))
        ids = {i for h in histories if h['introduced_chapter'] == chapter for i in h['A_change_ids']}
        out['A'] = [copy.deepcopy(r) for r in doc['A'] if r['change_id'] in ids or not r.get('plan') and r.get('as_of_chapter') == chapter]
        # 累计A视图可能已是末章；引入章保存层只取原始内容，由本章历史投影状态。
        for row in out['A']:
            row['as_of_chapter'] = chapter
        out['review_audit']['old_plan_rows'] = [r for r in doc['review_audit']['old_plan_rows'] if any(r['old_key'] in a.get('old_ledger_keys', []) for a in out['A'])]
    flags = [f for f in doc['review_audit']['review_flags'] if f.get('chapter') == chapter]
    out['review_audit']['review_flags'] = [f for f in flags if ':' + layer + ':' in f.get('flag_id', '') or layer == 'A' and ':A格式:' in f.get('flag_id', '')]
    return out


def seed_before(path, chapter):
    """只取已经交付的早章状态，不从金标或旧召回猜状态。"""
    out = empty_result()
    if not path:
        return out, dict(source='输入旧召回；无可信的前章已交付计划状态', plans=0,
                         limitation='早章未跑，不把旧召回猜成完整历史；本章仍逐项判断提供的旧召回')
    p = source(path)
    doc = json.loads((p / 'prediction.json').read_text())
    completed = set(json.loads((p / 'run_receipt.json').read_text())['completed_chapters'])
    for h in doc['review_audit']['plan_history']:
        states = [s for s in h['states'] if s['chapter'] < chapter and s['chapter'] in completed]
        if not states:
            continue
        out['review_audit']['plan_history'].append(dict(copy.deepcopy(h), states=copy.deepcopy(states)))
        for r in doc['A']:
            if r['change_id'] in h['A_change_ids']:
                row = copy.deepcopy(r)
                row['as_of_chapter'] = states[-1]['chapter']
                if row.get('plan'):
                    row['plan']['status'] = states[-1]['status']
                    row['candidate_refs'] = {k:states[-1].get(k) for k in ('source_record_key','fulfilled_record_key','condition_record_key')}
                out['A'].append(row)
    out['B'] = [copy.deepcopy(r) for r in doc['B'] if r.get('chapter', '99') < chapter]
    return out, dict(source=str(p), plans=len(out['review_audit']['plan_history']),
                     limitation='只继承已保存早章状态；来源没交付的计划仍缺失，未重判早章')


def run_a(data, doc, prior, catalog, client, model, policy, folder, receipt):
    facts = chapter_facts(data, doc)
    histories = prior['review_audit']['plan_history']
    existing = []
    for h in histories:
        row = next((r for r in prior['A'] if r['change_id'] in h['A_change_ids'] and r.get('plan')), None)
        if not row:
            continue
        item = dict(key=h['plan_key'], subject=row['subject_text'], plan=row['plan'], source=h['states'][0]['source_record_key'], previous_state=h['states'][-1])
        existing.append(item)
        if item['previous_state']['status'] in ('兑现', '放弃'):
            state = dict(item['previous_state'], chapter=data['chapter'], change_basis_record_keys=[], note='本章未改动已结的窄目标：' + row['plan']['content'])
            doc['review_audit']['plan_history'].append(dict(h, states=[state]))
    open_items = [v for v in existing if v['previous_state']['status'] not in ('兑现', '放弃')]
    degraded = []
    common = dict(book_id=data['book_id'], chapter=data['chapter'], paragraphs=data['paragraphs'], scope_limits=data['scope_limits'], current_facts=facts)
    for start in range(0, len(open_items), 8):
        items = open_items[start:start + 8]
        refs = {k for v in items for k in (v['source'], v['previous_state'].get('fulfilled_record_key'), v['previous_state'].get('condition_record_key')) if k}
        material = dict(common, existing=items, previous_facts=[f for f in catalog if f['local_key'] in refs])
        label = 'A_update' + str(start // 8)
        raw, pending = task(client, model, policy, UPDATE, material, lambda v: gates.a_gate(v, 'update', material), folder, label, receipt, 'A')
        gates.a_apply(raw, material, doc, prior, 'update', pending)
        pending_flags(doc, data, 'A', pending)
        if pending:
            degraded.append(label)
    # 字段职责明确的非意向召回只保留原类，意向与未知行仍由模型判断。
    previous_links = {}
    for h in histories:
        for key in h.get('old_ledger_keys', []):
            previous_links.setdefault(key, []).append(h['plan_key'])
    inherited_rows = [r for r in data['old_plan_rows'] if r['local_key'] in previous_links]
    deterministic = [r for r in data['old_plan_rows'] if r not in inherited_rows and r.get('native_field') and not r['native_field'].startswith('intent_seq')]
    undecided = [r for r in data['old_plan_rows'] if r not in deterministic and r not in inherited_rows]
    refs = {v['source'] for v in existing}
    material = dict(common, old_plan_rows=undecided, existing=[dict(key=v['key'], subject=v['subject'], content=v['plan']['content'], status=v['previous_state']['status'], source=v['source']) for v in existing], previous_facts=[f for f in catalog if f['local_key'] in refs])
    raw, pending = task(client, model, policy, DISCOVER, material, lambda v: gates.a_gate(v, 'discover', material), folder, 'A_discover', receipt, 'A')
    raw = copy.deepcopy(raw)
    raw.setdefault('old_rows', []).extend(dict(key=r['local_key'], meaning='非计划保留原类', retained_field=r['native_field'], reason='保留输入已明确的原人物字段：' + r['native_field']) for r in deterministic)
    material['old_plan_rows'] = undecided + deterministic
    gates.a_apply(raw, material, doc, prior, 'discover', pending)
    pending_flags(doc, data, 'A', pending)
    for row in inherited_rows:
        doc['review_audit']['old_plan_rows'].append(dict(old_key=row['local_key'], meaning='沿用原意', plan_keys=previous_links[row['local_key']], retained_native_field=None, note='该输入旧键已经对应现有计划，本章状态由更新步骤负责'))
    if pending:
        degraded.append('A_discover')
    return degraded


def run_c(data, client, model, policy, folder, receipt):
    annotations, degraded, flags = [], [], []
    for start in range(0, len(data['paragraphs']), 24):
        ps = data['paragraphs'][start:start + 24]
        scope = dict(data, paragraphs=ps, group=start // 24, facts=[], owned_paragraph_ids=[p['paragraph_id'] for p in ps])
        material = {k:scope[k] for k in ('book_id','chapter','paragraphs','scope_limits','owned_paragraph_ids')}
        material['read_only_chapter_context'] = data['paragraphs'][:start] + data['paragraphs'][start + 24:]
        label = 'C_tags' + str(start // 24)
        raw, pending = task(client, model, policy, ANNOTATE, material, lambda v: gates.c_gate(dict(v, scenes=[]), scope), folder, label, receipt, 'C')
        local = empty_result()
        gates.c_convert(raw, scope, local, pending)
        pending_flags(local, scope, 'C', pending)
        flags.extend(local['review_audit']['review_flags'])
        annotations.extend(dict(id=gates.full_pid(p['paragraph_id'], data), main=p['main_tag'], secondary=p['secondary_tag'], viewpoint=p['viewpoint'], quote=p['quote'], note=p.get('note','')) for c in local['C'] for p in c['paragraphs'])
        if pending:
            degraded.append(label)
    scope = dict(data, group='chapter', facts=[], owned_paragraph_ids=[p['paragraph_id'] for p in data['paragraphs']])
    material = {k:data[k] for k in ('book_id','chapter','paragraphs','scope_limits')}
    def gate(v):
        obj, errors, log = gates.c_gate(dict(v, paragraphs=annotations), scope)
        errors = [e for e in errors if not str(e.get('path', '')).startswith('paragraphs[') and e.get('field') != '段标注']
        return obj, errors, log
    raw, pending = task(client, model, policy, SCENES, material, gate, folder, 'C_scenes', receipt, 'C')
    raw['paragraphs'] = annotations
    out = empty_result()
    gates.c_convert(raw, scope, out, pending)
    pending_flags(out, scope, 'C', pending)
    out['review_audit']['review_flags'].extend(flags)
    if pending:
        degraded.append('C_scenes')
    return out, degraded


def run(args):
    output = external(args.out)
    output.mkdir(parents=True, exist_ok=True)
    config = next(c for c in json.loads((OUT / 'books_selected.json').read_text()) if c['code'] == args.book)
    policies = json.loads((OUT / 'probe/reasoning_policy.json').read_text())
    models = {k:getattr(args, k.lower() + '_model') or args.model for k in 'ABC'}
    sources = {k:getattr(args, k.lower() + '_source') or args.source for k in 'ABC'}
    for layer in 'ABC':
        if layer not in args.layers and sources[layer]:
            saved = json.loads((source(sources[layer]) / 'run_receipt.json').read_text())
            models[layer] = saved.get('layer_models', {}).get(layer, saved['model'])
    roles = {'A':{'deepseek-v4.1-flash'}, 'C':{'deepseek-v4.1-flash'}, 'B':{'glm-5.3-flash','xiaomi/mimo-v2.6-flash'}}
    for layer in args.layers:
        if models[layer] not in roles[layer]:
            raise ValueError('生成模型不符合本轮岗位分工：'+layer)
    selected = getattr(args, 'chapter_ids', None) or [f'{n:02d}' for n in range(1, args.chapters + 1)]
    selected = sorted(set(f'{int(ch):02d}' for ch in selected))
    receipt = dict(review_model=args.review_model, review_layers=args.review_layers, upgrade_model=args.upgrade_model, policies=policies, dependency_stale_A=('B' in args.layers and 'A' not in args.layers), execution_identity='Codex', book=args.book, model=args.model, layer_models=models, round=args.round, chapters_requested=len(selected), chapter_ids=selected, score_scope='full_book' if len(selected)==8 else 'chapter_projection', completed_chapters=[], clean_chapters=[], degraded_chapters=[], calls=[], rewrites=0, checkpoint_hits=0, partial=False, inherited_layers=[k for k in 'ABC' if k not in args.layers], layer_sources=sources, code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    receipt['b_group_size'] = getattr(args, 'b_group', 16)
    receipt['generation_rewrite_limit'] = 1
    receipt['layer_completed_chapters'] = {k:[] for k in 'ABC'}
    receipt['partial_chapters'] = []
    result, seed = seed_before(getattr(args, 'a_seed_source', None), selected[0])
    receipt['a_start_source'] = seed
    receipt['a_history_gaps'] = [f'{n:02d}' for n in range(int(selected[0]), int(selected[-1])) if f'{n:02d}' not in selected]
    catalog = []
    if result['B']:
        for n in range(1, int(selected[0])):
            catalog.extend(chapter_facts(read_book(config, f'{n:02d}'), result))
    result['batch_id'] = 'PR_R04'
    client = Client()
    for ch in selected:
        data = read_book(config, ch)
        folder = output / ('ch' + ch)
        folder.mkdir(exist_ok=True)
        doc, degraded = empty_result(), []
        try:
            if 'B' in args.layers:
                for piece in groups(data, getattr(args, 'b_group', 16)):
                    label = 'B_g' + str(piece['group'])
                    raw, pending = task(client, models['B'], policies[models['B']]['parameters'], B_FIDELITY, piece, lambda v: b_gate(v, piece), folder, label, receipt, 'B')
                    gates.b_convert(raw, piece, doc, pending)
                    pending_flags(doc, piece, 'B', pending)
                    if pending:
                        degraded.append(label)
            else:
                assemble(doc, inherited(sources['B'], ch, 'B'))
            receipt['layer_completed_chapters']['B'].append(ch)
            dump(folder / 'layer_B.json', doc)
            if 'C' in args.layers:
                c, bad = run_c(data, client, models['C'], policies[models['C']]['parameters'], folder, receipt)
                assemble(doc, c)
                degraded.extend(bad)
            else:
                assemble(doc, inherited(sources['C'], ch, 'C'))
            receipt['layer_completed_chapters']['C'].append(ch)
            dump(folder / 'layer_C.json', doc)
            if 'A' in args.layers:
                degraded.extend(run_a(data, doc, result, catalog, client, models['A'], policies[models['A']]['parameters'], folder, receipt))
            else:
                assemble(doc, inherited(sources['A'], ch, 'A'))
            receipt['layer_completed_chapters']['A'].append(ch)
            dump(folder / 'layer_A.json', doc)
            for step in folder.glob('*_done.json'):
                record = json.loads(step.read_text())
                for issue in record['pending']:
                    if issue.get('independent'):
                        gates.flag(doc, data, record['layer'], None, '独立复核仍有具体疑点：'+str(issue.get('field'))+'；'+issue['error'])
            if 'B' in args.layers:
                facts = chapter_facts(data, doc)
                for p in data['paragraphs']:
                    keys = [f['local_key'] for f in facts if p['paragraph_id'] in (f.get('paragraph_ids') or [e['paragraph_id'] for e in f.get('evidence') or []])]
                    # 不把没有事实的纯画面默判为漏抽；保存去向，争议由候选语义判断负责。
                    doc['review_audit']['source_chapters'].append(dict(book_id=data['book_id'], chapter=ch, paragraphs=[dict(paragraph_id=p['paragraph_id'].rsplit(':',1)[-1], fact_record_keys=keys, disposition='已有句承接' if keys else '未决', note='' if keys else '事实层未声明本段去向')]))
                    if not keys:
                        gates.flag(doc, data, 'B', None, '事实层未声明本段是否只有画面或仍有漏句', [p['paragraph_id']])
            assemble(result, doc)
            catalog.extend(chapter_facts(data, doc))
            receipt['completed_chapters'].append(ch)
            inherited_bad = sum(':' + k + ':' in f.get('flag_id','') for k in receipt['inherited_layers'] for f in doc['review_audit']['review_flags'])
            if degraded or inherited_bad:
                receipt['degraded_chapters'].append(dict(chapter=ch, steps=degraded, inherited_pending=inherited_bad))
            else:
                receipt['clean_chapters'].append(ch)
            dump(folder / 'result.json', doc)
            print('R04章节交付', args.book, ch, '新降级', len(degraded), '黄标', len(doc['review_audit']['review_flags']), flush=True)
        except Exception as exc:
            receipt['partial'] = True
            receipt['error'] = str(exc)
            completed = [k for k in 'BCA' if ch in receipt['layer_completed_chapters'][k]]
            if completed:
                # 分层完成与整章完成分开记；只保存已经完成层的快照，失败层不伪造。
                for index in range(len(completed)-1, -1, -1):
                    safe_doc = json.loads((folder / ('layer_'+completed[index]+'.json')).read_text())
                    try:
                        assemble(result, safe_doc)
                    except (ValueError, TypeError, KeyError, AttributeError):
                        continue
                    preserved = completed[:index+1]
                    for layer in completed[index+1:]:
                        receipt['layer_completed_chapters'][layer].remove(ch)
                    receipt['partial_chapters'].append(dict(chapter=ch, completed_layers=preserved, error=str(exc)))
                    dump(folder / 'partial_result.json', safe_doc)
                    break
                else:
                    for layer in completed:
                        receipt['layer_completed_chapters'][layer].remove(ch)
            dump(folder / 'failure.json', dict(execution_identity='Codex', error=str(exc)))
            break
        finally:
            done = [json.loads(p.read_text()) for p in output.glob('ch*/*_done.json')]
            receipt['rewrites'] = sum(d['rewrites'] for d in done)
            receipt['calls'] = [dict(layer=json.loads((p.parent / (p.name.rsplit('_response_',1)[0] + '_input.json')).read_text())['layer'], model=json.loads((p.parent / (p.name.rsplit('_response_',1)[0] + '_input.json')).read_text())['model'], usage=json.loads(p.read_text()).get('usage',{})) for p in output.glob('ch*/*_response_*.json')]
            dump(output / 'prediction.json', result)
            dump(output / 'run_receipt.json', receipt)
    return int(receipt['partial'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--book', choices=('gongan','dayi','qishi','tianmu','tianzai'), required=True)
    p.add_argument('--model', choices=MODELS, required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--layers', choices=('A','B','C','AB','ABC'), required=True)
    p.add_argument('--round', type=int, choices=range(1,9), required=True)
    p.add_argument('--chapters', type=int, choices=range(1,9), default=8)
    p.add_argument('--chapter-ids', nargs='+', choices=tuple(f'{n:02d}' for n in range(1,9)))
    p.add_argument('--a-seed-source')
    p.add_argument('--review-model', choices=('kimi-k2.8-preview',))
    p.add_argument('--review-layers', choices=('A','B','C','ABC'), default='A')
    p.add_argument('--upgrade-model', choices=('xiaomi/mimo-v2.6-pro',))
    p.add_argument('--b-group', type=int, choices=(16,24), default=16)
    p.add_argument('--source')
    for k in 'abc':
        p.add_argument('--' + k + '-source')
        p.add_argument('--' + k + '-model', choices=MODELS)
    return run(p.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
