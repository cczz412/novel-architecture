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
from pipeline_budget25 import Budget, Halt, NetworkPause, RoleLimit, TotalLimit, parse_response
from pipeline_records25 import validate, flatten, review_apply, facts_output, plans_output, assemble
from pipeline_author25 import build_views, query
from pipeline_audit25 import local_closure, structural_checks
from pipeline_c_program25 import annotate

ROOT = Path(__file__).resolve().parent
CODE_FILES = tuple(ROOT / name for name in ('run_pipeline.py', 'pipeline_source25.py',
    'pipeline_prompts25.py', 'pipeline_budget25.py', 'pipeline_records25.py', 'pipeline_author25.py', 'pipeline_audit25.py', 'pipeline_c_program25.py'))
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


def run_stage(budget, state, state_path, role, material, payload, review=False, checker=None):
    name = role + ':' + material['chapter'] + (':review' if review else ':generate')
    base = messages(REVIEW_PROMPT if review else PROMPTS[role], payload)
    stage = state['stages'].setdefault(name, {'attempts': 0, 'status': 'pending'})
    cache = budget.output / 'stages' / (name.replace(':', '_') + '.json')
    if stage['status'] == 'complete':
        if digest(cache) != stage['sha256']:
            raise Halt('同次结果检查点改变')
        return read_json(cache)['payload']
    while stage.get('machine_failures', 0) < 2 or stage.get('request_index'):
        raw = None
        prior_index = stage.pop('request_index', None)
        if prior_index:
            prior = next((r for r in budget.calls if r['index'] == prior_index), None)
            if prior and prior['state'] == 'received':
                raw = read_json(prior['response'])
            elif prior and prior['state'] == 'inflight':
                raise NetworkPause('在途响应未结算，不重复请求')
            elif prior and prior['state'] == 'network_failed':
                # 断线续跑使用新计数；没有清掉旧请求的未知预留。
                stage['network_resumes'] = stage.get('network_resumes', 0) + 1
            elif prior is None:
                stage['attempts'] -= 1
        if raw is None:
            if stage.get('machine_failures', 0) >= 2:
                raise ValueError('机检失败已用一次重试')
            stage['attempts'] += 1
            stage['request_index'] = len(budget.calls) + 1
            write_json(state_path, state)
            repair = stage.get('machine_error')
            current_messages = base + ([{'role': 'user', 'content': '机检失败，修正后重给完整JSON：' + repair}] if repair else [])
            raw = budget.send(role, material['chapter'], current_messages, review=review)
            stage.pop('request_index', None)
        try:
            decoded = parse_response(raw)
            checked = checker(decoded) if checker else decoded
            write_json(cache, {'payload': checked})
            stage.update(status='complete', sha256=digest(cache))
            write_json(state_path, state)
            return checked
        except (ValueError, KeyError, TypeError) as exc:
            stage['machine_error'] = str(exc)[:3000]
            stage['machine_failures'] = stage.get('machine_failures', 0) + 1
            stage['machine_retries'] = min(1, stage['machine_failures'])
            write_json(state_path, state)
            if stage['machine_failures'] >= 2:
                stage['status'] = 'incomplete_machine_check'
                write_json(state_path, state)
                raise
    raise ValueError('机检步骤未完成')


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
                    candidate = run_stage(budget, state, state_path, role, material, payload,
                        checker=lambda obj: validate(role, obj, material, facts, previous_plans))
                    encoded_bytes = len(json.dumps(candidate, ensure_ascii=False).encode())
                    if encoded_bytes > config['roles'][role]['review_rows_max_bytes']:
                        raise RoleLimit('候选超过已预留复核材料上界，未截删')
                    reference_keys = {r.get(k) for r in candidate.get('rows', []) for k in ('source', 'fulfilled', 'condition_ref')} | {key for r in candidate.get('rows', []) for key in r.get('basis', [])}
                    review_payload = {'paragraphs': paragraphs, 'rows': flatten(role, candidate), 'role': role,
                                      'fact_fields': ['key', 'subject', 'text', 'paragraph_ids'],
                                      'facts': fact_map([f for f in facts if f['local_key'] in reference_keys]) if role == 'A' else []}
                    checked = run_stage(budget, state, state_path, role, material, review_payload,
                        review=True, checker=lambda obj: {'approved': review_apply(role, candidate, obj, material, facts, previous_plans)[0],
                                                          'rejected': review_apply(role, candidate, obj, material, facts, previous_plans)[1]})
                    approved = checked['approved']
                    part[role] = approved
                    part[role + '_rejected'] = checked['rejected']
                    if role == 'B':
                        part['facts'] = facts_output(approved, material)
                    elif role == 'A':
                        part['plans'] = plans_output(approved, material, previous_plans)
                    status[role_id] = '完成' if role != 'C' or not checked['rejected'] else '未完成（复核拒收标注）'
                    write_json(state_path, state)
                except RoleLimit as exc:
                    status[role_id] = '未完成（预算或授权）'
                    part[role + '_limit'] = str(exc)
                    write_json(state_path, state)
                    continue
                except (ValueError, KeyError, TypeError) as exc:
                    status[role_id] = '未完成（机检）'
                    part[role + '_error'] = str(exc)
                    write_json(state_path, state)
                    continue
            all_facts.extend(part.get('facts', []))
            previous_plans.extend(part.get('plans', []))
            previous_people.extend(part.get('J2', {}).get('people', []))
        prediction = assemble(materials, state['chapters'])
        author = build_views(materials, state['chapters'])
        write_json(output / 'prediction.json', prediction)
        write_json(output / 'author_store.json', author)
        complete = all(value == '完成' for value in status.values())
        write_json(output / 'run_status.json', {'roles': status, 'complete': complete,
                    'identity': budget.identity, 'requests': budget.spent()[0], 'charged_tokens': budget.spent()[1],
                    'C_mode': 'program', 'C_formal': False,
                    'empty_views': [name for name, rows in author['views'].items() if not rows],
                    'eligible_for_blind': complete and budget.spent()[0] <= 12 and budget.spent()[1] <= 150000})
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
