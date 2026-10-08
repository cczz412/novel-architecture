# 执行身份：Codex
"""Locked paired offline tests for the v85 direct-review route. Never sends requests."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
W = Path('/workspace/codex-work/work/管线修复_R04/novel-architecture')
sys.path.insert(0, str(W / 'tools'))
import pipeline_records25 as rec
import run_pipeline as entry
import pipeline_prompts25 as prompts


def model_tier_policy(saved, wrong_ids):
    """Probe assessment rule, not a change to production confirmation rules."""
    result = copy.deepcopy(saved)
    model_rows = [r for r in rec.flatten('J2', result)
                  if r.get('_source_review', {}).get('tier') == 'model'
                  and r.get('confirmation_status') == '已确认']
    triggered = bool(set(wrong_ids) & {r['_id'] for r in model_rows})
    if triggered:
        for row in model_rows:
            row.update(confirmation_status='待核', confirmation_reason='模型档出现错确认，整档退回')
    return result, triggered


def fixture(sticky=False, all_source=False):
    texts = ['沈澈说：“木箱放在东廊。”', '“顾棠会带来绳索。”', '陆祁修好了木梯。']
    mat = {'book_id': 'synthetic', 'chapter': '01', 'paragraphs': [
        {'paragraph_id': 'x'+str(i), 'full_id': 'synthetic:ch01:x'+str(i), 'text': t}
        for i, t in enumerate(texts, 1)]}
    rows = [{'entity': n, 'aspect': '未知', 'layer': '现场', 'value': q,
             'ev': [{'p': 'x'+str(i), 'q': q}], '_id': 'people:'+str(i-1),
             'confirmation_status': '已确认', 'confirmation_reason': None}
            for i, (n, q) in enumerate([('沈澈', '木箱放在东廊'), ('顾棠', '顾棠会带来绳索'),
                                        ('陆祁', '陆祁修好了木梯')], 1)]
    if sticky: rows[0]['_normalization_pending'] = True
    if all_source: rows = rows[:2]
    candidate = {f: rows if f == 'people' else [] for f in rec.SECTIONS}
    facts = [{'subject': n, 'mentions': [n]} for n in ('沈澈', '顾棠', '陆祁')]
    return mat, candidate, facts


def exercise(dest, mode='correct', sticky=False, all_source=False, resume=False):
    mat, candidate, facts = fixture(sticky, all_source)
    prepared, blocked = rec.j2_prepare_packet(mat, rec.flatten('J2', candidate), facts=facts, itemwise=True)
    assert not blocked
    source = {i['id'] for i in prepared['items'] if i['candidate'].get('requires_speaker')}
    assert source == {'people:0', 'people:1'}
    assert any(g['tier'] == 'program' for g in prepared['items'][0]['evidence_groups'])
    assert any(g['tier'] == 'model' for g in prepared['items'][1]['evidence_groups'])
    original = copy.deepcopy(candidate)
    state = {'execution_identity': 'Codex', 'chapters': {'01': {}}, 'stages': {}}
    budget = SimpleNamespace(output=dest, config={'per_stage_reservation': {
        'J2:01:generate': 100000, 'J2:01:review': 100000}})
    calls, first_saves, cache = [], [], {}
    state_path = dest / 'checkpoint.json'
    current_mode = [mode]
    def store(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'execution_identity': 'Codex', **value}, ensure_ascii=False, indent=2)+'\n')
    def stage(b, st, path, role, child, packet, review=False, checker=None, suffix=''):
        phase = 'review' if review else 'generate'
        key = phase+suffix
        if key in cache:
            assert cache[key][0] == packet
            return copy.deepcopy(cache[key][1])
        calls.append({'phase': phase, 'ids': [i['id'] for i in packet['items']]})
        first_saves.append(copy.deepcopy(st['chapters']['01']))
        if current_mode[0] == 'fail_'+phase:
            raise entry.NetworkPause('synthetic request failure')
        if current_mode[0] == 'format' and review:
            return rec.j2_short_decisions({'verdicts': 'broken'}, packet)
        verdicts = []
        for item in packet['items']:
            ident = item['id']
            if current_mode[0] == 'missing' and review and ident == 'people:0': continue
            code = next(('S'+str(n) for n, x in enumerate(item['speaker_candidates'], 1)
                         if x['entity'].get('entity') == '沈澈' and x['entity'].get('role') == 'speaker'), None)
            v = {'id': ident, 'accept': 'D1', 'reason': 'R1', 'speaker': code if review else None}
            if current_mode[0] == 'source_null' and review and ident in source: v['speaker'] = None
            if current_mode[0] == 'source_D0' and review and ident in source: v.update(accept='D0', reason='R0', speaker=None)
            if current_mode[0] == 'reject_content' and review and ident == 'people:0': v.update(accept='D2', reason='R2', speaker=None)
            if current_mode[0] == 'reject_ordinary' and not review and ident not in source: v.update(accept='D2', reason='R2', speaker=None)
            verdicts.append(v)
        result = rec.j2_short_decisions({'verdicts': verdicts}, packet)
        cache[key] = (copy.deepcopy(packet), copy.deepcopy(result))
        return result
    def invoke():
        try:
            return entry.run_j2_short(budget, state, state_path, mat, facts)
        except entry.NetworkPause:
            return None
    with patch.object(entry, 'j2_program_candidates', return_value=(copy.deepcopy(candidate), {})), \
         patch.object(entry, 'j2_enrich_candidates', side_effect=lambda m, c, f: copy.deepcopy(c)), \
         patch.object(entry, 'run_stage', side_effect=stage), patch.object(entry, 'write_json', side_effect=store):
        answer = invoke()
        before_resume = copy.deepcopy(state['chapters']['01'])
        if resume:
            state = json.loads(state_path.read_text())
            current_mode[0] = 'correct'
            answer = invoke()
            calls_after_resume = copy.deepcopy(calls)
            # A second completed resume must use the same cached packets and add no dispatches.
            state = json.loads(state_path.read_text())
            invoke()
            assert calls == calls_after_resume
    assert candidate == original
    part = state['chapters']['01']
    def ids(p):
        confirmed = {r['_id'] for r in rec.flatten('J2', p.get('J2', {f:[] for f in rec.SECTIONS}))}
        pending = {r['id'] for r in p.get('J2_pending', [])}
        rejected = {r['id'] for r in p.get('J2_rejected', [])}
        assert not confirmed & pending and not confirmed & rejected and not pending & rejected
        return confirmed, pending, rejected
    return {'calls': calls, 'part': part, 'before_resume': before_resume, 'first_saves': first_saves,
            'source': source, 'initial': original, 'ids': ids(part), 'answer': answer, 'prepared': prepared, 'material': mat}


def run(root):
    root.mkdir(parents=True, exist_ok=True)
    results = []
    def check(ident, fn):
        try: fn(); results.append({'id': ident, 'passed': True})
        except Exception as exc: results.append({'id': ident, 'passed': False, 'error': repr(exc)})
    def coverage(r):
        c, p, d = r['ids']
        assert c | p | d == {x['_id'] for x in rec.flatten('J2', r['initial'])}
        originals = r['part']['J2_source_originals']
        assert originals == {x['_id']: x for x in rec.flatten('J2', r['initial']) if x['_id'] in r['source']}
    data = {}
    for mode in ('correct','source_null','source_D0','reject_content','reject_ordinary','missing','format','fail_review','fail_generate'):
        try: data[mode] = exercise(root/mode, mode)
        except Exception as exc:
            results.append({'id': 'setup_'+mode, 'passed': False, 'error': repr(exc)})
    def route():
        r=data['correct']; coverage(r)
        assert [c['ids'] for c in r['calls'] if c['phase']=='generate'] == [['people:2']]
        assert {i for c in r['calls'] if c['phase']=='review' for i in c['ids']} == {'people:0','people:1','people:2'}
        assert r['ids'][0] == {'people:0','people:1','people:2'}
        assert r['source'] <= {p['id'] for p in r['first_saves'][0]['J2_pending']}
        assert all(p['phase']=='review' and '生成轮已判' not in p['reason'] for p in r['first_saves'][0]['J2_pending'] if p['id'] in r['source'])
    check('B85-01_route_both_tiers_before_generation', route)
    def ordinary():
        r=data['reject_ordinary']; coverage(r)
        assert r['ids'][2] == {'people:2'}
        assert {i for c in r['calls'] if c['phase']=='review' for i in c['ids']} == r['source']
    check('B85-02_ordinary_generation_keeps_rejection', ordinary)
    for mode in ('source_null','source_D0','missing','format','fail_review','fail_generate'):
        def pending(mode=mode):
            r=data[mode];coverage(r)
            wanted={'people:0'} if mode=='missing' else r['source']
            assert wanted <= r['ids'][1] and not r['ids'][2]
            assert all(p['row']['ev'] for p in r['part']['J2_pending'])
        check('B85-03_'+mode+'_keeps_original_pending',pending)
    def reject_content():
        r=data['reject_content'];coverage(r)
        assert r['ids'][2] == {'people:0'} and 'people:1' in r['ids'][0]
    check('B85-04_content_without_support_can_be_rejected',reject_content)
    for mode in ('fail_review','fail_generate','missing'):
        def resumed(mode=mode):
            r=exercise(root/('resume_'+mode),mode,resume=True);coverage(r)
            expected={'people:0'} if mode=='missing' else set()
            assert r['ids'][1] == expected
            assert not r['ids'][2]
            assert r['before_resume']['J2_source_originals'] == r['part']['J2_source_originals']
        check('B85-05_resume_'+mode,resumed)
    def all_source():
        r=exercise(root/'all_source',all_source=True);coverage(r)
        assert [c['phase'] for c in r['calls']]==['review']
    check('B85-06_source_only_skips_empty_generation',all_source)
    def sticky():
        r=exercise(root/'sticky',sticky=True);coverage(r)
        assert 'people:0' in r['ids'][1] and 'people:1' in r['ids'][0]
        row=next(p['row'] for p in r['part']['J2_pending'] if p['id']=='people:0')
        assert row['_normalization_pending'] is True
    check('B85-07_existing_normalization_pending_preserved',sticky)
    def wire():
        r=data['correct'];packet=copy.deepcopy(r['prepared'])
        for item in packet['items']:
            item['candidate'].update(confirmation_status='待核',confirmation_reason='旧理由待核',
                unverified_speaker='旧推断待核',_normalization_pending=True,_internal_future='旧理由待核')
        before=copy.deepcopy(packet);w=rec.j2_wire_payload(packet,r['material']);assert packet==before
        excluded={'confirmation_status','confirmation_reason','unverified_speaker','requires_speaker','speaker','attribution','evaluation_source'}
        assert not any(k.startswith('_') or k in excluded for fs in w['candidate_fields'].values() for k in fs)
        assert '旧理由待核' not in json.dumps(w,ensure_ascii=False)
        for row,item in zip(w['items'],packet['items']):
            fields=w['candidate_fields'][item['id'].split(':')[0]];content=dict(zip(fields,row[1]))
            assert content['value']==item['candidate']['value'] and content['entity']==item['candidate']['entity']
        assert w['paragraphs']==rec.j2_wire_payload(before,r['material'])['paragraphs']
    check('B85-08_wire_clean_local_lossless',wire)
    def prompt():
        assert len(prompts.J2_ITEM_PROMPT.encode()) < 3250
        assert all(t in prompts.J2_ITEM_PROMPT for t in ('生成','复核','D1','D2','D0','来源','内容'))
    check('B85-09_prompt_separates_content_and_source',prompt)
    for wrong in ([],['people:1']):
        def policy(wrong=wrong):
            r=data['correct']; saved=r['part']['J2']; before=copy.deepcopy(saved)
            out,triggered=model_tier_policy(saved,wrong)
            assert saved==before and triggered==bool(wrong)
            for row in rec.flatten('J2',out):
                is_model=row.get('_source_review',{}).get('tier')=='model'
                assert (row['confirmation_status']=='待核') == (is_model and bool(wrong))
        check('B85-10_model_policy_'+('one_wrong' if wrong else 'all_correct'),policy)
    result={'execution_identity':'Codex','real_requests':0,'cases':results,'passed':sum(x['passed'] for x in results),'total':len(results)}
    (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    return result

if __name__=='__main__':
    result=run(Path(sys.argv[1]))
    raise SystemExit(0 if result['passed']==result['total'] else 1)
