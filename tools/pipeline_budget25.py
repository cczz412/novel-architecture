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
from pipeline_output28 import OUTPUT_POLICY, REPAIR_MAX_BYTES

MODELS = {'B': 'glm-5.3-flash', 'A': 'deepseek-v4.1-flash',
          'J2': 'deepseek-v4.1-flash', 'review': 'kimi-k2.8-preview'}
WINDOW_REQUEST_CAPS = {'T5c': 26, 'blind': 34}
TOKEN_CAP = 300000
BLIND_ADMISSION_TOKENS = 150000


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def before(value):
    return datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(value)


def input_estimate(messages, config=None, role=None, review=False):
    size = len(json.dumps(messages, ensure_ascii=False).encode())
    calibration = (config or {}).get('token_calibration')
    if not calibration:
        return size + 1024  # 历史预算兼容；新草案必须登记实测系数。
    coefficient = calibration['roles']['review' if review else role]
    if role == 'A' and review:
        a_coefficient = calibration['roles']['A']
        if (a_coefficient['k_numerator'] * coefficient['k_denominator'] >
                coefficient['k_numerator'] * a_coefficient['k_denominator']):
            coefficient = a_coefficient  # A样本保护：复核也取A与复核的较大系数。
    numerator, denominator = coefficient['k_numerator'], coefficient['k_denominator']
    if type(numerator) is not int or type(denominator) is not int or min(numerator, denominator) <= 0:
        raise Halt('输入token系数未登记为正整数分数')
    return (size * numerator + denominator - 1) // denominator


def reserve(messages, completion, config=None, role=None, review=False):
    return input_estimate(messages, config, role, review) + completion


def request_maximum(config, role, review, payload):
    limits = config['roles'][role]
    old = limits['review_completion'] if review else limits['max_completion_per_call']
    if role != 'A' or not config.get('A_output_calibration'):
        return old
    observed = config['A_output_calibration']['review' if review else 'generate']
    count = len(payload['rows']) if review else len(payload.get('plan_seeds', [])) + len(payload.get('previous_plans', []))
    return max(observed['observed_max_times_2'], count * observed.get('single_row_reasonable_tokens',observed.get('single_row_measured_upper_tokens',0)))


def runtime_guard_errors(config):
    """检查新守门配置；未知估计不能当已证明的上界。"""
    guard = config.get('runtime_guard', {})
    errors = []
    for name in ('enabled', 'hard_caps_on_wire', 'stop_before_send', 'account_actual_usage'):
        if guard.get(name) is not True:
            errors.append(name)
    if not config.get('token_calibration'):
        errors.append('token_calibration')
    for role, requests, tokens in (('B',8,110000), ('J2',8,120000), ('A',7,45000), ('C',0,0)):
        item = config.get('roles', {}).get(role, {})
        if item.get('max_requests') != requests or item.get('max_tokens') != tokens:
            errors.append('role_cap:' + role)
    if config.get('total') != {'max_requests':26, 'max_tokens':300000}:
        errors.append('total_cap')
    pool = config.get('shared_pool', {})
    if pool.get('max_requests') != 3 or pool.get('max_tokens') != 25000 or pool.get('per_role_max_requests') != 3:
        errors.append('shared_pool')
    # 正式预算不在本轮写集；旧值为1须报不合要求，不能放宽守卫。
    if config.get('A_retry_policy', {}).get('max_retries') != 2:
        errors.append('A_retry')
    for phase in ('generate','review'):
        calibration=config.get('A_output_calibration',{}).get(phase,{})
        if any(type(calibration.get(k)) is not int or calibration[k]<=0 for k in ('observed_max_times_2','single_row_reasonable_tokens')):
            errors.append('A_output:' + phase)
    return errors


class Halt(RuntimeError):
    pass


class RoleLimit(Halt):
    pass


class TotalLimit(Halt):
    pass


class NetworkPause(Halt):
    pass


class TruncatedOutput(ValueError):
    pass


def check_limits(config):
    total, roles = config['total'], config['roles']
    window = config.get('budget_window', 'T5c')
    if window not in WINDOW_REQUEST_CAPS:
        raise Halt('预算窗口未登记')
    values = list(total.values()) + [r[k] for r in roles.values() for k in ('max_requests', 'max_tokens')]
    if any(type(v) is not int or v < 0 for v in values):
        raise Halt('预算上限须为非负整数')
    if total['max_requests'] > WINDOW_REQUEST_CAPS[window] or total['max_tokens'] > TOKEN_CAP:
        raise Halt('预算超过窗口硬顶')
    if sum(r['max_tokens'] for r in roles.values()) > total['max_tokens']:
        raise Halt('岗位Token分配超过总硬顶')
    pool = config.get('shared_pool')
    if pool is not None:
        bases = [r.get('base_requests') for r in roles.values()]
        if any(type(v) is not int or v < 0 for v in bases):
            raise Halt('各岗基础请求额度未登记')
        if type(pool.get('max_requests')) is not int or pool['max_requests'] < 0 or pool.get('per_role_max_requests') != 3:
            raise Halt('共享池须登记非负额度，单岗最多取3次')
        if sum(bases) + pool['max_requests'] != total['max_requests']:
            raise Halt('基础请求与共享池之和须等于窗口请求硬顶')
        if any(r['max_requests'] > r['base_requests'] + (3 if r['base_requests'] else 0) for r in roles.values()):
            raise Halt('单岗请求额度超过基础额度加3次共享池')
    elif sum(r['max_requests'] for r in roles.values()) > total['max_requests']:
        raise Halt('岗位请求分配超过总硬顶')
    return {'cap_requests': total['max_requests'], 'cap_tokens': total['max_tokens'], 'C_calls': 0}


def blind_admission(complete, roles, tokens, empty_roles):
    return (complete and bool(roles) and all(v in ('完成', 'complete') for v in roles.values())
            and not empty_roles and type(tokens) is int and 0 <= tokens <= BLIND_ADMISSION_TOKENS)


def blind_role_limits(measured_roles):
    """仅换算已测账；1417/1000等于1.09×1.3，整数计算向上取整。"""
    roles = {}
    for role, measured in measured_roles.items():
        if any(type(measured.get(k)) is not int or measured[k] < 0 for k in ('requests', 'tokens')):
            raise Halt('盲测预算须使用已测的非负整数用量')
        roles[role] = {out: (measured[key] * 1417 + 999) // 1000
                       for key, out in (('requests', 'max_requests'), ('tokens', 'max_tokens'))}
    config = {'budget_window': 'blind', 'roles': roles,
              'total': {k: sum(r[k] for r in roles.values()) for k in ('max_requests', 'max_tokens')}}
    check_limits(config)
    return config


class Budget:
    def __init__(self, budget_path, output, archive, code_files):
        self.path, self.output = Path(budget_path), Path(output)
        self.config = read_json(self.path)
        self.identity = {'budget_sha': digest(self.path), 'input_sha': digest(archive),
                         'gateway_job_id': self.config.get('gateway_job_id'),
                         'checkpoint_protocol': 'v29_owned_shared_pool',
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
        if config.get('runtime_guard'):
            errors = runtime_guard_errors(config)
            if errors:
                raise Halt('运行期守门配置不完整：' + ','.join(errors))
        if not config.get('enabled') or not before(config['stop_new_calls_at']) or not before(config['deadline']):
            raise Halt('预算未开启或已到停新请求时间')
        if digest(self.path) != self.identity['budget_sha']:
            raise Halt('跑中预算文件改变')
        limits = check_limits(config)
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
        return limits

    def record_event(self, event):
        write_json(self.output / 'call_events' / ('call_' + str(event['index']) + '.json'), event)

    def spent(self, role=None):
        rows = [r for r in self.calls if role is None or r['role'] == role]
        return len(rows), sum(r['known_tokens'] if type(r.get('known_tokens')) is int
                             and r['known_tokens'] > 0 else r['reserved_tokens'] for r in rows)

    def role_charged(self, role):
        # 106第12条：A拆半只扣共享池；仍由spent()计入整窗总额。
        rows = [r for r in self.calls if r['role'] == role and not (
            role == 'A' and self.config.get('runtime_guard') and
            r.get('quota_source') == 'shared_pool' and r.get('pool_reason') == 'truncation_split')]
        return len(rows), sum(r['known_tokens'] if type(r.get('known_tokens')) is int
                             and r['known_tokens'] > 0 else r['reserved_tokens'] for r in rows)

    def shared_usage(self, role=None):
        return sum(r.get('quota_source') == 'shared_pool' for r in self.calls
                   if role is None or r['role'] == role)

    def request_quota(self, role, pool_reason=None, reservation=0):
        pool = self.config.get('shared_pool')
        if pool is None:
            return 'base', None
        limits = self.config['roles'][role]
        base_used = sum(r['role'] == role and r.get('quota_source') == 'base' for r in self.calls)
        role_count, role_tokens = self.role_charged(role)
        own_available = (base_used < limits['base_requests'] and role_count < limits['max_requests']
                         and role_tokens + reservation <= limits['max_tokens'])
        # A截断子包继续遵守已锁定的池规则；一般重试先用本岗位余量。
        if own_available and not (role == 'A' and self.config.get('runtime_guard') and pool_reason == 'truncation_split'):
            return 'base', pool_reason
        pool_tokens = sum(r['known_tokens'] if type(r.get('known_tokens')) is int and r['known_tokens'] > 0
                          else r['reserved_tokens'] for r in self.calls if r.get('quota_source') == 'shared_pool')
        available = pool['max_tokens'] - pool_tokens
        if reservation > available:
            raise RoleLimit(f'无法重试：单次预留{reservation}超过共享池可用{available}；本岗位余量不足')
        if self.config.get('runtime_guard'):
            if pool_reason not in ('machine_retry', 'network_resume', 'truncation_split', 'review_extension'):
                raise RoleLimit('共享池只用于超帽重试或一次复核扩展')
        if self.shared_usage() >= pool['max_requests']:
            raise RoleLimit('共享拆分池已空，本岗停止')
        if not limits['base_requests'] or self.shared_usage(role) >= pool['per_role_max_requests']:
            raise RoleLimit('本岗共享池额度已用满，最多取3次')
        return 'shared_pool', pool_reason or 'additional_packet'

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

    def send(self, role, chapter, messages, review=False, stage_id=None, on_dispatch=None, pool_reason=None):
        try:
            return self._send_checked(role, chapter, messages, review, stage_id, on_dispatch, pool_reason)
        except (RoleLimit, TotalLimit, Halt) as exc:
            if not hasattr(self,'output'):raise  # 未完成初始化的对象仍保留原停止原因。
            payload = {}
            try:
                payload = json.loads(messages[1]['content'].split('\n')[-1])
                maximum = request_maximum(self.config, role, review, payload)
                estimate = reserve(messages, maximum, self.config, role, review)
            except (KeyError, ValueError, TypeError, IndexError):
                maximum, estimate = None, None
            write_json(self.output / 'guard_stops' / (str(len(self.calls)) + '_' + role + '_' + str(stage_id).replace(':','_') + '.json'),
                       {'role':role, 'stage_id':stage_id, 'reason':str(exc),
                        'estimated_request_tokens':estimate, 'max_tokens':maximum,
                        'role_used':self.role_charged(role), 'window_used':self.spent(),
                        'role_cap':self.config.get('roles',{}).get(role), 'window_cap':self.config.get('total'),
                        'stopped_before_send':len(self.calls) == getattr(self, '_before_send_count', len(self.calls))})
            raise

    def _send_checked(self, role, chapter, messages, review=False, stage_id=None, on_dispatch=None, pool_reason=None):
        self._before_send_count = len(self.calls)
        auth = self.guard()
        if role == 'C' and auth.get('C_calls') == 0:
            raise RoleLimit('本轮C模型调用未授权')
        if role == 'A' and len(json.dumps(messages,ensure_ascii=False).encode()) > 8192:
            raise RoleLimit('A实际发送包超过8KB，停止在发送前并保留候选待核')
        limits = self.config['roles'][role]
        payload = json.loads(messages[1]['content'].rsplit('\n', 1)[1]) if self.config.get('token_calibration') else {}
        maximum = request_maximum(self.config, role, review, payload)
        if not (role == 'A' and self.config.get('A_output_calibration')) and maximum != OUTPUT_POLICY['review' if review else role]['max_tokens']:
            raise RoleLimit('输出上限尚未绑定v28协议余量')
        reservation = reserve(messages, maximum, self.config, role, review)
        retry_policy = self.config.get('A_retry_policy')
        split_from_pool = role == 'A' and self.config.get('runtime_guard') and pool_reason == 'truncation_split'
        if role == 'A' and retry_policy and pool_reason == 'network_resume':
            # 恢复v57网络续发条件；仍由后面的在途、岗位及总预算闸拦截。
            retries=[c for c in self.calls if c['role']=='A' and c.get('pool_reason') in ('machine_retry','network_resume','truncation_split')
                     and not (self.config.get('runtime_guard') and c.get('pool_reason')=='truncation_split')]
            if retries:raise RoleLimit('A整岗一次网络续发已用，停止在发送前')
            if not self.config.get('runtime_guard') and reservation > retry_policy['max_group_retry_reservation']:
                raise RoleLimit('A重试材料超过整岗最大组重试预留，停止在发送前')
        if role == 'A' and pool_reason in ('machine_retry', 'truncation_split'):
            group=str(stage_id).split('.split')[0]
            retries=[c for c in self.calls if c['role']=='A' and c.get('chapter')==chapter
                     and str(c.get('stage_id')).split('.split')[0]==group
                     and c.get('pool_reason') in ('machine_retry','truncation_split')]
            if stage_id is None or len(retries)>=2:
                raise RoleLimit('A本包最多两次可修失败重试，停止在发送前')
            if retry_policy and not self.config.get('runtime_guard') and reservation > retry_policy['max_group_retry_reservation']:
                raise RoleLimit('A重试材料超过整岗最大组重试预留，停止在发送前')
        stage_name = role + ':' + chapter + (':review' if review else ':generate')
        if not self.config.get('runtime_guard') and reservation > self.config['per_stage_reservation'][stage_name]:
            raise RoleLimit('本次材料超过整流程预留证明上界，未截删')
        if not self.config.get('runtime_guard') and role == 'A' and self.config.get('A_retry_policy') and pool_reason in ('machine_retry', 'network_resume', 'truncation_split'):
            prior_group = [c for c in self.calls if c['role'] == 'A' and c.get('stage_id') == stage_id]
            group_spent = sum(c['known_tokens'] if type(c.get('known_tokens')) is int and c['known_tokens'] > 0
                              else c['reserved_tokens'] for c in prior_group)
            if group_spent + reservation > self.config['per_stage_reservation'][stage_name]:
                raise RoleLimit('A本组含一次重试超过阶段单请求帽，停止在发送前')
        n, used = self.spent()
        total = self.config['total']
        if n + 1 > min(total['max_requests'], auth['cap_requests']) or used + reservation > min(total['max_tokens'], auth['cap_tokens']):
            raise TotalLimit('总预算不足，停止全部')
        count, spent = self.role_charged(role)
        quota_source, quota_reason = self.request_quota(role, pool_reason, reservation)
        # 112：旧max字段就是基础次数；追加只走已存在的共享池，不抬总帽。
        max_requests=limits['max_requests']
        if self.config.get('shared_pool') and quota_source=='shared_pool':
            pool=self.config['shared_pool']
            extra=min(pool['max_requests']-self.shared_usage(),pool['per_role_max_requests']-self.shared_usage(role))
            max_requests=limits['base_requests']+self.shared_usage(role)+extra
        if not split_from_pool and (count + 1 > max_requests or spent + reservation > limits['max_tokens']):
            raise RoleLimit(f'无法重试或发送：本岗剩余{limits["max_tokens"]-spent} Token/{max_requests-count}次，单次预留{reservation}；基础次数及总帽不变')
        if self.config.get('runtime_guard') and quota_source == 'shared_pool':
            pool_used = sum(c.get('known_tokens') if type(c.get('known_tokens')) is int and c['known_tokens'] > 0
                            else c['reserved_tokens'] for c in self.calls if c.get('quota_source') == 'shared_pool')
            if pool_used + reservation > self.config['shared_pool']['max_tokens']:
                raise RoleLimit('共享池Token不足，停止在发送前')
        if any(r['state'] == 'inflight' for r in self.calls):
            raise NetworkPause('上次在途请求尚未结算，不重复发送')
        gateway = self.get_budget()
        self.guard()
        index = len(self.calls) + 1
        write_json(self.output / 'gateway' / ('before_' + str(index) + '.json'), gateway)
        request = {'model': MODELS['review'] if review else MODELS[role], 'messages': messages,
                   'max_tokens': maximum, 'temperature': 0, 'response_format': {'type': 'json_object'}}
        if request['model'] == 'glm-5.3-flash':
            request['reasoning_effort'] = 'low'
        elif request['model'] in ('deepseek-v4.1-flash', 'kimi-k2.8-preview'):
            request['thinking'] = {'type': 'disabled'}
        path = self.output / 'requests' / ('request_' + str(index) + '.json')
        write_json(path, request)
        event = {'index': index, 'role': role, 'chapter': chapter, 'review': review,
                 'stage_id': stage_id,
                 'quota_source': quota_source, 'pool_reason': quota_reason,
                 'model': request['model'], 'reserved_tokens': reservation, 'known_tokens': None,
                 'state': 'inflight', 'started_at': now(), 'request': str(path),
                 'job_id': self.config['request_prefix'] + role + '_' + chapter + '_' + str(index),
                 'usage': None, 'gateway_job_id': self.config['gateway_job_id']}
        self.calls.append(event)
        self.save()
        self.record_event(event)
        # 请求落账后再登记检查点编号；被预算拒绝时，两处都不新增记录。
        if on_dispatch is not None:
            on_dispatch(index)
        url = os.environ['PR_LLM_BASE_URL'].rstrip('/') + '/chat/completions'
        req = urllib.request.Request(url, data=json.dumps(request, ensure_ascii=False).encode(),
                                     headers={'Content-Type': 'application/json', 'X-PR-Job-ID': self.config['gateway_job_id']})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(req, timeout=1200) as response:
                raw = json.load(response)
            truncated = any(c.get('finish_reason') == 'length' for c in raw.get('choices', []))
            if truncated:
                # 106第13条：原响应仅作审计；后续只能提取完整行到待核。
                raw['audit_only'] = True
                raw['truncated'] = True
            response_path = self.output / 'requests' / ('response_' + str(index) + '.json')
            write_json(response_path, raw)
            tokens = raw.get('usage', {}).get('total_tokens')
            usage = raw.get('usage', {})
            if tokens is None and isinstance(usage.get('prompt_tokens'), int) and isinstance(usage.get('completion_tokens'), int):
                tokens = usage['prompt_tokens'] + usage['completion_tokens']
            event.update(state='received', response=str(response_path), usage=usage, known_tokens=tokens, ended_at=now(),
                         truncated=truncated, response_use='audit_only' if truncated else 'parse')
            self.save()
            self.record_event(event)
            try:
                write_json(self.output / 'gateway' / ('after_' + str(index) + '.json'), self.get_budget(check_stop=False))
            except Exception as exc:
                write_json(self.output / 'gateway' / ('after_' + str(index) + '.json'), {'readback_failed': type(exc).__name__})
            if (type(tokens) is not int or tokens <= 0 or tokens > reservation
                    or self.config.get('token_calibration') and
                    (type(usage.get('prompt_tokens')) is not int or type(usage.get('completion_tokens')) is not int
                     or usage['prompt_tokens'] > input_estimate(messages, self.config, role, review)
                     or usage['completion_tokens'] > maximum)):
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
    if choice.get('finish_reason') == 'length':
        raise TruncatedOutput('输出长度耗尽，必须拆包')
    if choice.get('finish_reason') != 'stop':
        raise ValueError('输出未正常结束')
    content = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', choice['message']['content'])
    return json.loads(content)


def complete_truncated_rows(raw, review=False):
    """106第1/13条：只取目标数组里完整的JSON对象，绝不补齐残行。"""
    choice = raw.get('choices', [{}])[0]
    if choice.get('finish_reason') != 'length':
        return []
    content = choice.get('message', {}).get('content', '')
    key = 'verdicts' if review else 'rows'
    start = re.match(r'\s*(?:```json\s*)?\{\s*"' + key + r'"\s*:\s*\[', content)
    if not start:
        return []
    pos = start.end()
    decoder = json.JSONDecoder()
    rows = []
    while pos < len(content):
        pos += len(content[pos:]) - len(content[pos:].lstrip())
        try:
            row, end = decoder.raw_decode(content, pos)
        except (ValueError, TypeError):
            break
        if not isinstance(row, dict):
            break
        rows.append(row)
        pos = end + len(content[end:]) - len(content[end:].lstrip())
        if pos >= len(content) or content[pos] != ',':
            break
        pos += 1
    return rows
