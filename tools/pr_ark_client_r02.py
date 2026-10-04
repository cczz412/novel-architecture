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

OUT = Path('/workspace/codex-work/out/管线修复_R03')
TRANSPORT_RETRIES = 2
BLOCKED = OUT / 'control/UPSTREAM_BLOCKED.json'
RECOVERY = OUT / 'control/RECOVERY_CONFIRMED.json'


def is_blocked():
    if not BLOCKED.exists():return False
    if not RECOVERY.exists():return True
    try:
        proof=json.loads(RECOVERY.read_text())
        return not (proof.get('ok') is True and len(proof.get('probe_jobs',[]))>=2
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
        if is_blocked():
            raise RuntimeError('已观察到上游额度或限流错误，停止新请求')
        if set(parameters) - {'thinking', 'reasoning_effort'}:
            raise ValueError('仅允许方舟思考控制参数')
        payload = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=0,
                       response_format={'type': 'json_object'}, **parameters)
        req = urllib.request.Request(
            self.base + '/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json', 'X-PR-Job-ID': self.job})
        for attempt in range(TRANSPORT_RETRIES + 1):
            if is_blocked():
                raise RuntimeError('已观察到上游额度或限流错误，停止新请求')
            start = time.monotonic()
            try:
                with self.opener.open(req, timeout=1200) as response:
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
                    BLOCKED.parent.mkdir(parents=True, exist_ok=True)
                    BLOCKED.write_text(json.dumps(dict(execution_identity='Codex', job_id=self.job,
                                                       model=model, http_status=exc.code,
                                                       reason='上游额度或限流错误，停止后续请求'),
                                                  ensure_ascii=False)+'\n')
                    raise RuntimeError('网关返回 HTTP '+str(exc.code)+'，停止新请求') from None
                if exc.code not in (500, 502, 503, 504) or attempt == TRANSPORT_RETRIES:
                    raise RuntimeError('网关返回 HTTP '+str(exc.code)) from None
                time.sleep((2, 6)[attempt])

            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                self.trace(dict(model=model,attempt=attempt,http_status=0,error_type=type(exc).__name__))
                if attempt == TRANSPORT_RETRIES:
                    raise RuntimeError('传输失败，有限重试已用尽：'+type(exc).__name__) from None
                time.sleep((2,6)[attempt])
