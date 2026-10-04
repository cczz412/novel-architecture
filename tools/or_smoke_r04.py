# 执行身份：Grok Bot（调度者）：经本地网关对 OpenRouter 三个模型各发一次极小虚构请求（只读 PR_LLM_BASE_URL，不用密钥）。
import json, os, time, urllib.request
BASE, JOB = os.environ['PR_LLM_BASE_URL'].rstrip('/'), os.environ['PR_JOB_ID']
OUT = '/workspace/codex-work/out/管线修复_R04/probe/or_smoke.json'
PARAMS = {'xiaomi/mimo-v2.6-flash': {'reasoning': {'enabled': False}}, 'xiaomi/mimo-v2.6-pro': {'reasoning': {'enabled': False}},
          'typesafe/jev-router': {}}
rows = []
for model, extra in PARAMS.items():
    body = dict({'model': model, 'messages': [{'role': 'user', 'content': '虚构连通题：只输出 JSON {"ok":true}。'}], 'max_tokens': 300,
                 'temperature': 0, 'response_format': {'type': 'json_object'}}, **extra)
    req = urllib.request.Request(BASE + '/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json', 'X-PR-Job-ID': JOB})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))
        ch, u = d['choices'][0], d['usage']
        row = {'model': model, 'http': 200, 'finish': ch.get('finish_reason'), 'content': (ch['message'].get('content') or '')[:80],
               'reasoning_len': len(ch['message'].get('reasoning') or ch['message'].get('reasoning_content') or ''), 'resp_model': d.get('model'),
               'prompt_tokens': u.get('prompt_tokens'), 'completion_tokens': u.get('completion_tokens'),
               'reasoning_tokens': (u.get('completion_tokens_details') or {}).get('reasoning_tokens'), 'cost': u.get('cost')}
    except Exception as e:
        row = {'model': model, 'http': getattr(e, 'code', None), 'error': type(e).__name__}
    row['sec'] = round(time.time() - t, 1)
    rows.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
open(OUT, 'w').write(json.dumps(rows, ensure_ascii=False, indent=1) + '\n')
