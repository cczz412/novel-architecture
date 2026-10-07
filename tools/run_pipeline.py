#!/usr/bin/env python3
# 执行身份：Codex
"""Five-argument source-only pipeline with resumable, bounded role stages."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from pipeline_source25 import chapter_range, digest, read_json, read_sources, write_json
from pipeline_prompts25 import SYSTEM, PROMPTS, REVIEW_PROMPT
from pipeline_budget25 import Budget, Halt, NetworkPause, RoleLimit, TotalLimit, TruncatedOutput, parse_response, blind_admission
from pipeline_output28 import (PROTOCOL, OUTPUT_POLICY, REPAIR_MAX_BYTES, OutputOverflow, J2RowOverflow,
    bounded_packets, split_packet, split_j2_rows, merge_values, hydrate_j2, check_review_shape, pointer_payload, repair_message)
from pipeline_records25 import validate, flatten, review_apply, facts_output, plans_output, assemble, speaker_candidates, normalize_rejected_patches
from pipeline_author25 import build_views, query
from pipeline_audit25 import local_closure, structural_checks
from pipeline_c_program25 import annotate

ROOT = Path(__file__).resolve().parent
CODE_FILES = tuple(ROOT / name for name in ('run_pipeline.py', 'pipeline_source25.py',
    'pipeline_prompts25.py', 'pipeline_budget25.py', 'pipeline_records25.py', 'pipeline_author25.py', 'pipeline_audit25.py', 'pipeline_c_program25.py', 'pipeline_output28.py'))
PROMPT_FILES = (ROOT / 'pipeline_prompts25.py',)
CONFIG_FILES = (ROOT / 'pipeline_terms25.json', ROOT / 'pipeline_background25.json')


def messages(instruction, payload):
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': instruction + '\n' +
             json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}]


def fact_map(rows):
    return [[r['local_key'], r.get('subject'), r['text'],
             sorted({e['paragraph_id'] for e in r['evidence']})] for r in rows]


def plan_summary(rows):
    latest = {r['key']: r for r in rows}
    fields = ('key', 'subject', 'content', 'status', 'deadline', 'condition', 'source', 'fulfilled', 'condition_ref')
    return [{k: r.get(k) for k in fields} for r in latest.values()]


def clean_checkpoint(state, calls, gateway_job_id):
    removed = []
    for name, stage in state['stages'].items():
        index = stage.get('request_index')
        if index is None:
            continue
        event = next((r for r in calls if r['index'] == index), None)
        if event is None:
            stage.pop('request_index')
            removed.append({'stage': name, 'unsubmitted_index': index})
            continue
        if event.get('stage_id') != name or event.get('gateway_job_id') != gateway_job_id:
            raise Halt('检查点请求归属不符，不能借用其他岗位或旧窗响应')
    state['unsubmitted_request_indexes_cleared'] = removed
    return removed


def run_stage(budget, state, state_path, role, material, payload, review=False, checker=None,
              suffix='', split_depth=0):
    name = role + ':' + material['chapter'] + (':review' if review else ':generate') + suffix
    base = messages(REVIEW_PROMPT if review else PROMPTS[role], payload)
    stage = state['stages'].setdefault(name, {'attempts': 0, 'status': 'pending'})
    cache = budget.output / 'stages' / (name.replace(':', '_') + '.json')
    if stage.get('local_row_split_failed'):
        raise ValueError(stage.get('machine_error', 'J2本地条目拆包已失败，不追加请求'))
    if stage['status'] == 'complete':
        if digest(cache) != stage['sha256']:
            raise Halt('同次结果检查点改变')
        cached = read_json(cache)['payload']
        if role == 'A':
            try:
                if review and not any(v.get('accept') for v in cached.get('verdicts', [])):
                    raise ValueError('缓存复核没有可保存计划，A阶段未完成')
                if not review:
                    if not cached.get('rows'):
                        raise ValueError('缓存计划候选为空，A阶段未完成')
                    if checker:
                        checker(cached, material, payload)
            except (ValueError, KeyError, TypeError) as exc:
                stage.update(status='incomplete_machine_check', machine_error=str(exc))
                write_json(state_path, state)
                raise
        return cached
    if stage['status'] == 'failed_truncation':
        raise OutputOverflow('该岗已在一次拆分后失败，不再投递')
    def split_once():
        if split_depth >= 1:
            stage.update(status='failed_truncation', split_depth=split_depth)
            write_json(state_path, state)
            raise OutputOverflow('拆分后的子包仍截断或超界，该岗停止')
        try:
            children = split_packet(material, payload, review)
        except OutputOverflow:
            stage.update(status='failed_truncation', split_depth=split_depth)
            write_json(state_path, state)
            raise
        stage.update(status='splitting', split_depth=split_depth, split_count=1)
        write_json(state_path, state)
        try:
            values = [run_stage(budget, state, state_path, role, child_material, child_payload,
                       review, checker, suffix + '.split' + str(n), split_depth + 1)
                      for n, (child_material, child_payload) in enumerate(children)]
        except OutputOverflow:
            stage['status'] = 'failed_truncation'
            write_json(state_path, state)
            raise
        combined = merge_values(role, values, review)
        write_json(cache, {'payload': combined})
        stage.update(status='complete', sha256=digest(cache))
        write_json(state_path, state)
        return combined
    if stage['status'] == 'splitting':
        return split_once()
    while stage.get('machine_failures', 0) < 2 or stage.get('request_index'):
        raw = None
        prior_index = stage.get('request_index')
        if prior_index:
            prior = next((r for r in budget.calls if r['index'] == prior_index), None)
            if prior and (prior.get('stage_id') != name or prior['role'] != role or
                          prior['chapter'] != material['chapter'] or prior['review'] != review or
                          prior.get('gateway_job_id') != budget.config['gateway_job_id']):
                raise Halt('请求归属不符，禁止使用其他岗位响应')
            if prior and prior['state'] == 'received':
                raw = read_json(prior['response'])
                stage.pop('request_index', None)
            elif prior and prior['state'] == 'inflight':
                raise NetworkPause('在途响应未结算，不重复请求')
            elif prior and prior['state'] == 'network_failed':
                # 断线续跑使用新计数；没有清掉旧请求的未知预留。
                stage['network_resumes'] = stage.get('network_resumes', 0) + 1
                stage.pop('request_index', None)
            elif prior is None:
                stage.pop('request_index', None)
                stage['attempts'] = max(0, stage['attempts'] - 1)
        if raw is None:
            if stage.get('machine_failures', 0) >= 2:
                raise ValueError('机检失败已用一次重试')
            stage['attempts'] += 1
            write_json(state_path, state)
            repair = stage.get('machine_error')
            previous_answer = stage.get('machine_answer')
            answer_message = ([{'role': 'assistant', 'content': previous_answer}]
                              if repair and review and isinstance(previous_answer, str) else [])
            current_messages = base + answer_message + ([repair_message(repair)] if repair else [])
            def dispatched(index):
                stage['request_index'] = index
                write_json(state_path, state)
            pool_reason = ('truncation_split' if split_depth else 'machine_retry' if repair
                           else 'network_resume' if stage.get('network_resumes') else None)
            raw = budget.send(role, material['chapter'], current_messages, review=review,
                              stage_id=name, on_dispatch=dispatched, pool_reason=pool_reason)
            stage.pop('request_index', None)
        try:
            decoded = parse_response(raw)
            if role == 'B' and review:
                decoded, removed = normalize_rejected_patches(decoded)
                if removed:
                    stage['rejected_patch_ids_removed'] = removed
                    stage['rejected_patch_policy'] = 'preserve_reject_drop_conflicting_delta'
            checked = checker(decoded, material, payload) if checker else decoded
            if role == 'A' and not review and not checked.get('rows'):
                raise ValueError('计划候选为空，A阶段未完成；只能补有原文依据的计划')
            write_json(cache, {'payload': checked})
            stage.update(status='complete', sha256=digest(cache))
            write_json(state_path, state)
            return checked
        except J2RowOverflow as exc:
            if role != 'J2' or review:
                raise
            # 已收到完整JSON：拆的是返回条目，不再缩原文后花共享池重生成。
            try:
                parts = split_j2_rows(decoded)
                values = [(checker(part, material, payload) if checker else hydrate_j2(part, material))
                          for part in parts]
            except (ValueError, KeyError, TypeError) as split_error:
                stage.update(status='incomplete_machine_check', machine_error=str(split_error),
                             local_row_split_failed=True, local_row_split_extra_requests=0)
                write_json(state_path, state)
                raise
            child_records = []
            for n, (part, value) in enumerate(zip(parts, values)):
                child_cache = cache.with_name(cache.stem + '.rows' + str(n) + '.json')
                write_json(child_cache, {'payload': value})
                child_records.append({'path': str(child_cache), 'sha256': digest(child_cache),
                                      'row_count': sum(len(part[k]) for k in part),
                                      'compact_bytes': len(json.dumps(part, ensure_ascii=False, separators=(',', ':')).encode())})
            combined = merge_values(role, values)
            write_json(cache, {'payload': combined})
            stage.update(status='complete', sha256=digest(cache), local_row_split=child_records,
                         local_row_split_reason=str(exc), local_row_split_extra_requests=0)
            write_json(state_path, state)
            return combined
        except (TruncatedOutput, OutputOverflow) as exc:
            # 不把截断正文交保存校验，不复发同一大包，也不占普通机检重试次数。
            stage['truncation_error'] = str(exc)
            stage['truncated_responses'] = stage.get('truncated_responses', 0) + 1
            write_json(state_path, state)
            return split_once()
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
            if len(error.encode()) > REPAIR_MAX_BYTES - 128:
                error = (json.dumps({'speaker_claims_all_clear': True,
                         'error': '署名机检多错；本包全部speaker_claims强制改为[]，reason只写核对结论，保留编号和accept，删除拒收条目差量并保留其他patches'}, ensure_ascii=False)
                         if review and role == 'B' and ('speaker_candidate_membership' in error
                                                       or 'review_protocol_conflict' in error)
                         else '多项字段或证据未通过机检；重新核对全部字段和原文指针。')
            stage['machine_error'] = error
            if review:
                previous_answer = raw.get('choices', [{}])[0].get('message', {}).get('content')
                if isinstance(previous_answer, str):
                    stage['machine_answer'] = previous_answer
            stage['machine_failures'] = stage.get('machine_failures', 0) + 1
            stage['machine_retries'] = min(1, stage['machine_failures'])
            write_json(state_path, state)
            if stage['machine_failures'] >= 2:
                stage['status'] = 'incomplete_machine_check'
                write_json(state_path, state)
                raise
    raise ValueError('机检步骤未完成')


def run_packets(budget, state, state_path, role, material, payload, review=False, checker=None):
    maximum = OUTPUT_POLICY['review' if review else role]['max_tokens']
    packets = bounded_packets(role, material, payload, maximum, review)
    values = [run_stage(budget, state, state_path, role, part, data, review, checker,
                        '.pack' + str(n)) for n, (part, data) in enumerate(packets)]
    return merge_values(role, values, review)


def check_review_packet(role, candidate, obj, material, packet, facts, previous):
    if role == 'B':
        obj, _ = normalize_rejected_patches(obj)
    checked = check_review_shape(obj, packet['rows'], material)
    wanted = {row['_id'] for row in packet['rows']}
    fields = ('rows',) if role in ('A', 'B') else tuple(candidate)
    subset = {**candidate, **{field: [row for row in candidate[field] if row['_id'] in wanted]
                             for field in fields}}
    # 在包内核差量语义，失败走run_stage的一次机检重试，不重发整岗。
    candidates = speaker_candidates(material, flatten(role, candidate)) if role == 'B' else None
    review_apply(role, subset, checked, material, facts, previous, candidates=candidates)
    return checked


def execute(input_package, book_id, chapters, output_dir, budget_file):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = read_json(budget_file)
    if config.get('book_id') != book_id or config.get('chapters') != chapters:
        raise Halt('预算与书号或章范围不同')
    materials = read_sources(input_package, book_id, chapters)
    if config.get('mode') == 'structure':
        report = {'book_id': book_id, 'chapters': chapters, 'model_calls': 0,
                  'sources': [{'member': m['source_member'], 'sha256': m['source_sha256'],
                               'paragraph_count': len(m['paragraphs'])} for m in materials],
                  'pipeline_steps_run': False, 'gold_read': False}
        write_json(output / 'structure_check.json', report)
        return report
    budget = Budget(budget_file, output, input_package, tuple(dict.fromkeys((*CODE_FILES, *PROMPT_FILES, *CONFIG_FILES))))
    state_path = output / 'checkpoint.json'
    state = read_json(state_path) if state_path.exists() else {'identity': budget.identity, 'stages': {}, 'chapters': {}, 'started_at': budget.calls[0]['started_at'] if budget.calls else None}
    if state['identity'] != budget.identity:
        raise Halt('检查点不属于同一冻结运行')
    clean_checkpoint(state, budget.calls, config['gateway_job_id'])
    write_json(state_path, state)
    status = {}
    try:
        budget.guard()
        all_facts, previous_plans, previous_people = [], [], []
        for material in materials:
            chapter = material['chapter']
            part = state['chapters'].setdefault(chapter, {})
            paragraphs = [[p['paragraph_id'], p['text']] for p in material['paragraphs']]
            for role in ('B', 'J2', 'A', 'C'):
                role_id = role + ':' + chapter
                if role in ('J2', 'A') and part.get('B_status') != 'complete':
                    status[role_id] = 'blocked_upstream'
                    part[role + '_status'] = 'blocked_upstream'
                    part[role + '_blocked_reason'] = '本章B尚未保存通过'
                    write_json(state_path, state)
                    continue
                if role == 'A' and any(state['chapters'][m['chapter']].get('A_status') != 'complete'
                                       for m in materials if m['chapter'] < chapter):
                    status[role_id] = 'blocked_upstream'
                    part['A_status'] = 'blocked_upstream'
                    part['A_blocked_reason'] = '前章计划未保存通过，不能跳过状态历史'
                    write_json(state_path, state)
                    continue
                if role == 'C':
                    part['C'] = validate('C', annotate(material, part.get('J2', {})), material)
                    part['C_mode'] = 'program'
                    status[role_id] = '完成'
                    write_json(state_path, state)
                    continue
                payload = {'paragraphs': paragraphs}
                if role == 'A':
                    prior_refs = {r.get(k) for r in previous_plans for k in ('source', 'fulfilled', 'condition_ref')}
                    relevant_facts = part.get('facts', []) + [f for f in all_facts if f['local_key'] in prior_refs]
                    payload.update(fact_fields=['key', 'subject', 'text', 'paragraph_ids'], facts=fact_map(relevant_facts), previous_plans=plan_summary(previous_plans))
                if role == 'J2':
                    payload.update(previous_people=[{k: r.get(k) for k in ('entity', 'aspect', 'value', 'layer')} for r in previous_people])
                facts = all_facts + part.get('facts', [])
                try:
                    def generation_check(obj, part_material, packet):
                        if role == 'J2':
                            obj = hydrate_j2(obj, part_material)
                        return validate(role, obj, part_material, facts, previous_plans)
                    candidate = run_packets(budget, state, state_path, role, material, payload,
                        checker=generation_check)
                    candidate = validate(role, candidate, material, facts, previous_plans)
                    reference_keys = {r.get(k) for r in candidate.get('rows', []) for k in ('source', 'fulfilled', 'condition_ref')} | {key for r in candidate.get('rows', []) for key in r.get('basis', [])}
                    review_payload = {'paragraphs': pointer_payload(material), 'rows': flatten(role, candidate), 'role': role,
                                      'input_bound': config['roles'][role]['review_rows_max_bytes'],
                                      'fact_fields': ['key', 'subject', 'text', 'paragraph_ids'],
                                      'facts': fact_map([f for f in facts if f['local_key'] in reference_keys]) if role == 'A' else []}
                    if role == 'B':
                        review_payload['speaker_candidates'] = speaker_candidates(material, candidate['rows'])
                    review_result = run_packets(budget, state, state_path, role, material, review_payload,
                        review=True, checker=lambda obj, part_material, packet:
                        check_review_packet(role, candidate, obj, part_material, packet, facts, previous_plans))
                    approved, rejected = review_apply(role, candidate, review_result, material, facts, previous_plans)
                    part[role] = approved
                    part[role + '_rejected'] = rejected
                    if role == 'B':
                        part['facts'] = facts_output(approved, material)
                    elif role == 'A':
                        part['plans'] = plans_output(approved, material, previous_plans)
                        if not part['plans']:
                            raise ValueError('保存计划为空，A阶段未完成')
                    part[role + '_status'] = 'complete'
                    status[role_id] = '完成'
                    write_json(state_path, state)
                except RoleLimit as exc:
                    status[role_id] = '未完成（预算或授权）'
                    part[role + '_status'] = 'failed'
                    part[role + '_limit'] = str(exc)
                    write_json(state_path, state)
                    continue
                except (ValueError, KeyError, TypeError) as exc:
                    status[role_id] = '未完成（机检）'
                    part[role + '_status'] = 'failed'
                    part[role + '_error'] = str(exc)
                    write_json(state_path, state)
                    continue
            all_facts.extend(part.get('facts', []))
            previous_plans.extend(part.get('plans', []))
            previous_people.extend(part.get('J2', {}).get('people', []))
        prediction = assemble(materials, state['chapters'])
        author = build_views(materials, state['chapters'])
        status['H6'] = author['status']
        write_json(output / 'prediction.json', prediction)
        write_json(output / 'author_store.json', author)
        complete = all(value in ('完成', 'complete') for value in status.values())
        empty_roles = [role + ':' + m['chapter'] for m in materials for role in ('B', 'A', 'J2')
                       if not (state['chapters'][m['chapter']].get('facts') if role == 'B'
                               else state['chapters'][m['chapter']].get('plans') if role == 'A'
                               else any(state['chapters'][m['chapter']].get('J2', {}).values()))]
        write_json(output / 'run_status.json', {'roles': status, 'complete': complete,
                    'identity': budget.identity, 'requests': budget.spent()[0], 'charged_tokens': budget.spent()[1],
                    'C_mode': 'program', 'C_formal': False,
                    'empty_views': [name for name, rows in author['views'].items() if not rows],
                    'empty_roles': empty_roles,
                    'eligible_for_blind': blind_admission(complete, status, budget.spent()[1], empty_roles)})
        budget.close('本次运行完成' if complete else '本次运行有未完成岗位，不进盲测')
        return {'complete': complete, 'roles': status}
    except (TotalLimit, Halt, OSError) as exc:
        write_json(state_path, state)
        write_json(output / 'run_status.json', {'roles': status, 'complete': False,
                    'error': str(exc), 'error_type': type(exc).__name__, 'eligible_for_blind': False,
                    'identity': budget.identity, 'requests': budget.spent()[0], 'charged_tokens': budget.spent()[1]})
        budget.close('停止新请求：' + str(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description='从正文运行有限预算小说管线')
    parser.add_argument('input_package')
    parser.add_argument('book_id')
    parser.add_argument('chapter_range')
    parser.add_argument('output_dir')
    parser.add_argument('budget_file')
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    import shlex
    (out / 'run_command.txt').write_text('执行身份：Codex\n' + shlex.join(sys.argv) + '\n')
    class Tee:
        def __init__(self, terminal, log): self.terminal, self.log = terminal, log
        def write(self, value): self.terminal.write(value); self.log.write(value)
        def flush(self): self.terminal.flush(); self.log.flush()
    from contextlib import redirect_stdout, redirect_stderr
    with (out / 'run.log').open('a') as log:
        log.write('执行身份：Codex\n')
        with redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
            try:
                result = execute(args.input_package, args.book_id, chapter_range(args.chapter_range), args.output_dir, args.budget_file)
                print(json.dumps({'execution_identity': 'Codex', **result}, ensure_ascii=False))
                return 2 if result.get('complete') is False else 0
            except Exception as exc:
                print(json.dumps({'execution_identity': 'Codex', 'error_type': type(exc).__name__, 'error': str(exc)}, ensure_ascii=False))
                raise



if __name__ == '__main__':
    raise SystemExit(main())
