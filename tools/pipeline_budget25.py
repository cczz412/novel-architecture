# 执行身份：Codex
"""Portable per-role hard limits and immutable budget accounting."""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from pipeline_source25 import digest, read_json, write_json

MODELS = {'B': 'glm-5.3-flash', 'A': 'deepseek-v4.1-flash',
          'J2': 'deepseek-v4.1-flash', 'review': 'kimi-k2.8-preview'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def before(value):
    return datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(value)


def reserve(messages, completion):
    return len(json.dumps(messages, ensure_ascii=False).encode()) + 1024 + completion


class Halt(RuntimeError):
    pass


class RoleLimit(Halt):
    pass


class TotalLimit(Halt):
    pass


class NetworkPause(Halt):
    pass


class Budget:
    def __init__(self, budget_path, output, archive, code_files):
        self.path, self.output = Path(budget_path), Path(output)
        self.config = read_json(self.path)
        self.identity = {'budget_sha': digest(self.path), 'input_sha': digest(archive),
                         'source_sha': {str(p): digest(p) for p in code_files}}
        if self.config.get('input_pkg_sha') != self.identity['input_sha']:
            raise Halt('输入包与预算登记不同')
        self.ledger_path = self.output / 'calls.json'
        if self.ledger_path.exists():
            prior = read_json(self.ledger_path)
            if prior['identity'] != self.identity:
                raise Halt('续跑的代码、预算或输入发生变化')
            self.calls = prior['calls']
        else:
            self.calls = []
        self.save()
        write_json(self.output / 'budget_limits.json', self.config)
        write_json(self.output / 'code_freeze_snapshot.json', self.config.get('freeze', {}))

    def save(self):
        write_json(self.ledger_path, {'identity': self.identity, 'calls': self.calls, 'updated_at': now()})

    def close(self, reason):
        write_json(self.output / 'closed.json', {'closed_at': now(), 'closed_reason': reason})

    def guard(self):
        config = self.config
        if not config.get('enabled') or not before(config['stop_new_calls_at']) or not before(config['deadline']):
            raise Halt('预算未开启或已到停新请求时间')
        if digest(self.path) != self.identity['budget_sha']:
            raise Halt('跑中预算文件改变')
        total = config['total']
        if any(v < 0 for v in (total['max_requests'], total['max_tokens'])) or any(v < 0 for r in config['roles'].values() for v in (r['max_requests'], r['max_tokens'])):
            raise Halt('预算上限不能为负')
        if sum(r['max_tokens'] for r in config['roles'].values()) > total['max_tokens']:
            raise Halt('岗位分配超过总硬顶')
        if total['max_requests'] > 20 or total['max_tokens'] > 300000:
            raise Halt('预算超过管线硬顶')
        if config.get('C_mode') != 'program' or config['roles']['C']['max_requests'] != 0:
            raise Halt('C必须走零调用程序版')
        if not config.get('request_prefix') or not config.get('gateway_job_id', '').startswith(config['request_prefix']) or not config.get('full_pipeline_reserved'):
            raise Halt('请求前缀或整线预留缺失')
        freeze = config['freeze']
        if {row['path']:row['sha256'] for row in freeze['files']} != self.identity['source_sha']:
            raise Halt('冻结清单不等于实际执行的代码/提示词/配置')
        lines = []
        for row in sorted(freeze['files'], key=lambda r: r['path']):
            if digest(row['path']) != row['sha256']:
                raise Halt('冻结文件改变')
            lines.append(row['path'] + ' ' + row['sha256'])
        import hashlib
        overall = hashlib.sha256(('\n'.join(lines) + '\n').encode()).hexdigest()
        if overall != freeze['overall_sha256'] or config['code_freeze_sha'] != overall:
            raise Halt('预算内嵌冻结清单不一致')
        if not freeze.get('effective'):
            raise Halt('预算尚未绑定生效冻结')
        return {'cap_requests': total['max_requests'], 'cap_tokens': total['max_tokens'], 'C_calls': 0}

    def record_event(self, event):
        write_json(self.output / 'call_events' / ('call_' + str(event['index']) + '.json'), event)

    def spent(self, role=None):
        rows = [r for r in self.calls if role is None or r['role'] == role]
        return len(rows), sum(r.get('known_tokens') or r['reserved_tokens'] for r in rows)

    def get_budget(self, check_stop=True):
        base = os.environ['PR_LLM_BASE_URL'].rstrip('/')
        parsed = urllib.parse.urlparse(base)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path != '/v1' or not parsed.port:
            raise Halt('调用只允许既有本机网关')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(base + '/budget', timeout=30) as response:
            obj = json.load(response)
        window = obj.get('window', {})
        if check_stop and (obj.get('stop') or obj.get('soft_stop') or window.get('soft') or window.get('block_left_s')):
            raise Halt('网关停止新请求')
        return obj

    def send(self, role, chapter, messages, review=False):
        auth = self.guard()
        if role == 'C' and auth.get('C_calls') == 0:
            raise RoleLimit('本轮C模型调用未授权')
        limits = self.config['roles'][role]
        maximum = limits['review_completion'] if review else limits['max_completion_per_call']
        reservation = reserve(messages, maximum)
        stage_name = role + ':' + chapter + (':review' if review else ':generate')
        if reservation > self.config['per_stage_reservation'][stage_name]:
            raise RoleLimit('本次材料超过整流程预留证明上界，未截删')
        n, used = self.spent()
        total = self.config['total']
        if n + 1 > min(total['max_requests'], auth['cap_requests']) or used + reservation > min(total['max_tokens'], auth['cap_tokens']):
            raise TotalLimit('总预算不足，停止全部')
        count, spent = self.spent(role)
        if count + 1 > limits['max_requests'] or spent + reservation > limits['max_tokens']:
            raise RoleLimit('本岗预算不足')
        if any(r['state'] == 'inflight' for r in self.calls):
            raise NetworkPause('上次在途请求尚未结算，不重复发送')
        gateway = self.get_budget()
        self.guard()
        index = len(self.calls) + 1
        write_json(self.output / 'gateway' / ('before_' + str(index) + '.json'), gateway)
        request = {'model': MODELS['review'] if review else MODELS[role], 'messages': messages,
                   'max_tokens': maximum, 'temperature': 0, 'response_format': {'type': 'json_object'},
                   'thinking': {'type': 'disabled'}}
        path = self.output / 'requests' / ('request_' + str(index) + '.json')
        write_json(path, request)
        event = {'index': index, 'role': role, 'chapter': chapter, 'review': review,
                 'model': request['model'], 'reserved_tokens': reservation, 'known_tokens': 0,
                 'state': 'inflight', 'started_at': now(), 'request': str(path),
                 'job_id': self.config['request_prefix'] + role + '_' + chapter + '_' + str(index),
                 'usage': None, 'gateway_job_id': self.config['gateway_job_id']}
        self.calls.append(event)
        self.save()
        self.record_event(event)
        url = os.environ['PR_LLM_BASE_URL'].rstrip('/') + '/chat/completions'
        req = urllib.request.Request(url, data=json.dumps(request, ensure_ascii=False).encode(),
                                     headers={'Content-Type': 'application/json', 'X-PR-Job-ID': self.config['gateway_job_id']})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(req, timeout=1200) as response:
                raw = json.load(response)
            response_path = self.output / 'requests' / ('response_' + str(index) + '.json')
            write_json(response_path, raw)
            tokens = raw.get('usage', {}).get('total_tokens')
            usage = raw.get('usage', {})
            if tokens is None and isinstance(usage.get('prompt_tokens'), int) and isinstance(usage.get('completion_tokens'), int):
                tokens = usage['prompt_tokens'] + usage['completion_tokens']
            event.update(state='received', response=str(response_path), usage=usage, known_tokens=tokens or 0, ended_at=now())
            self.save()
            self.record_event(event)
            try:
                write_json(self.output / 'gateway' / ('after_' + str(index) + '.json'), self.get_budget(check_stop=False))
            except Exception as exc:
                write_json(self.output / 'gateway' / ('after_' + str(index) + '.json'), {'readback_failed': type(exc).__name__})
            if not isinstance(tokens, int) or tokens <= 0 or tokens > reservation:
                raise Halt('实际用量未知或超过预留')
            return raw
        except Halt:
            raise
        except Exception as exc:
            event.update(state='network_failed', error_type=type(exc).__name__, ended_at=now())
            self.save()
            self.record_event(event)
            self.close('网络失败，保持计数，原冻结件可续跑')
            raise NetworkPause(type(exc).__name__) from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def parse_response(raw):
    choice = raw['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('输出未正常结束')
    content = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', choice['message']['content'])
    return json.loads(content)
