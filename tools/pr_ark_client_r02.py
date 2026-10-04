# 执行身份：Codex
"""方舟文件队列客户端：仅本机网关，有限重试，保存数字和结束状态。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

OUT = Path('/workspace/codex-work/out/管线修复_R04')
TRANSPORT_RETRIES = 2
BLOCKED = OUT / 'control/UPSTREAM_BLOCKED.json'
RECOVERY = OUT / 'control/RECOVERY_CONFIRMED.json'


OR_MODELS = {'xiaomi/mimo-v2.6-flash', 'xiaomi/mimo-v2.6-pro', 'typesafe/jev-router'}


def is_blocked(model=None):
    if model in OR_MODELS:
        return False
    if not BLOCKED.exists():return False
    if not RECOVERY.exists():return True
    try:
        proof=json.loads(RECOVERY.read_text())
        probes=[r.get('probe',{}) for r in proof.get('receipts',[])]
        representative=(len(probes)>=2 and all(p.get('ok') is True and p.get('input_utf8_bytes',0)>=40000 and p.get('max_output_tokens',0)>=8000 for p in probes))
        return not (proof.get('ok') is True and len(proof.get('probe_jobs',[]))>=2 and representative
                    and proof.get('blocked_sha256')==hashlib.sha256(BLOCKED.read_bytes()).hexdigest())
    except (ValueError,OSError):return True


def summarize_response(response):
    result = copy.deepcopy(response)
    for choice in result.get('choices', []):
        message = choice.get('message', {})
        thinking = message.pop('reasoning_content', None)
        if thinking is not None:
            message['reasoning_content_characters'] = len(thinking)
    return result


class Client:
    def __init__(self):
        self.base = os.environ['PR_LLM_BASE_URL'].rstrip('/')
        url = urllib.parse.urlparse(self.base)
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path != '/v1' or not url.port:
            raise ValueError('只允许网关本机地址')
        self.job = os.environ['PR_JOB_ID']

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def get(self, path):
        with self.opener.open(self.base + path, timeout=45) as response:
            return json.load(response)

    def trace(self, event):
        folder = OUT / 'call_events' / self.job
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (uuid.uuid4().hex + '.json')).write_text(
            json.dumps(dict(execution_identity='Codex', job_id=self.job, **event), ensure_ascii=False) + '\n')

    def call(self, model, messages, parameters, max_tokens=32000):
        if is_blocked(model):
            raise RuntimeError('已观察到上游额度或限流错误，停止新请求')
        allowed = {'reasoning'} if model in OR_MODELS else {'thinking', 'reasoning_effort'}
        if set(parameters) - allowed:
            raise ValueError('思考字段与模型路由不符')
        payload = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=0,
                       response_format={'type': 'json_object'}, **parameters)
        req = urllib.request.Request(
            self.base + '/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json', 'X-PR-Job-ID': self.job})
        for attempt in range(TRANSPORT_RETRIES + 1):
            if is_blocked(model):
                raise RuntimeError('已观察到上游额度或限流错误，停止新请求')
            start = time.monotonic()
            try:
                with self.opener.open(req, timeout=2400) as response:
                    data = json.load(response)
                choice = data.get('choices', [{}])[0]
                content = choice.get('message', {}).get('content') or ''
                valid_json = False
                if content:
                    try:
                        clean = content.strip()
                        if clean.startswith('```'):
                            clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0]
                        json.loads(clean)
                        valid_json = True
                    except (ValueError, TypeError):
                        pass
                self.trace(dict(model=model, attempt=attempt, http_status=200,
                                elapsed_s=round(time.monotonic()-start, 3), parameters=parameters,
                                finish_reason=choice.get('finish_reason'), content_empty=not content,
                                json_valid=valid_json, usage=data.get('usage', {})))
                return summarize_response(data)
            except urllib.error.HTTPError as exc:
                self.trace(dict(model=model, attempt=attempt, http_status=exc.code,
                                elapsed_s=round(time.monotonic()-start, 3), parameters=parameters))
                if exc.code in (402, 429):
                    try:
                        detail = json.load(exc).get('error', {})
                    except (ValueError, OSError):
                        detail = {}
                    code = detail.get('code', 'budget_or_quota') if isinstance(detail, dict) else detail if isinstance(detail, str) else 'budget_or_quota'
                    self.trace(dict(model=model, attempt=attempt, http_status=exc.code, error_code=code, retry_after=detail.get('retry_after') if isinstance(detail, dict) else None))
                    # 本轮窗口由网关管理；不写跨路由永久阻塞，不叠加额度重试。
                    raise RuntimeError('网关额度阻塞：'+str(code)+'；本作业停止新请求') from None
                if model in OR_MODELS:
                    raise RuntimeError('OR网关已承担有限退避，客户端不叠加HTTP重试：'+str(exc.code)) from None
                if exc.code not in (500, 502, 503, 504) or attempt == TRANSPORT_RETRIES:
                    raise RuntimeError('网关返回 HTTP '+str(exc.code)) from None
                time.sleep((2, 6)[attempt])

            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                self.trace(dict(model=model,attempt=attempt,http_status=0,error_type=type(exc).__name__))
                if attempt == TRANSPORT_RETRIES:
                    raise RuntimeError('传输失败，有限重试已用尽：'+type(exc).__name__) from None
                time.sleep((2,6)[attempt])
