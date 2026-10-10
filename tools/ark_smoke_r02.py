# 执行身份：Codex
from pipeline_common.local_paths import external_path
# 执行身份：Grok Bot（调度者）：经本地网关对 5 个模型各发一次极小虚构请求（只读 PR_LLM_BASE_URL，不用密钥）。
import json, os, time, urllib.request
BASE, JOB = os.environ['PR_LLM_BASE_URL'].rstrip('/'), os.environ['PR_JOB_ID']
OUT = external_path('PR_WORKSPACE_ROOT') / 'out/管线修复_R02/probe/smoke_gateway.json'
PARAMS = {'kimi-k2.8-preview': {'thinking': {'type': 'disabled'}}, 'glm-5.3-flash': {'reasoning_effort': 'low'},
          'deepseek-v4.1-flash': {'thinking': {'type': 'disabled'}}, 'doubao-seed-2.0-mini': {'thinking': {'type': 'disabled'}},
          'doubao-seed-2.1-lite': {'thinking': {'type': 'disabled'}}}
rows = []
for model, extra in PARAMS.items():
    for label, ex in (('降思考/关思考', extra), ('默认思考', {})):
        body = dict({'model': model, 'messages': [{'role': 'user', 'content': '虚构连通题：只输出 JSON {"ok":true}。'}], 'max_tokens': 2000,
                     'temperature': 0, 'response_format': {'type': 'json_object'}}, **ex)
        req = urllib.request.Request(BASE + '/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json', 'X-PR-Job-ID': JOB})
        t = time.time()
        try:
            d = json.load(urllib.request.urlopen(req, timeout=300))
            ch, u = d['choices'][0], d['usage']
            row = {'model': model, 'mode': label, 'http': 200, 'finish': ch['finish_reason'], 'content': ch['message'].get('content'),
                   'reasoning_content_len': len(ch['message'].get('reasoning_content') or ''), 'prompt_tokens': u['prompt_tokens'],
                   'completion_tokens': u['completion_tokens'], 'reasoning_tokens': (u.get('completion_tokens_details') or {}).get('reasoning_tokens')}
        except Exception as e:
            row = {'model': model, 'mode': label, 'http': getattr(e, 'code', None), 'error': type(e).__name__}
        row['sec'] = round(time.time() - t, 1)
        rows.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
open(OUT, 'w').write(json.dumps(rows, ensure_ascii=False, indent=1) + '\n')
