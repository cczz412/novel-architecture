# 执行身份：Codex
"""External audit wrapper; excluded from the frozen pipeline closure."""
import sys
sys.dont_write_bytecode = True
import json
import os
import fnmatch
import hashlib
from pathlib import Path

OUTPUT = Path(sys.argv[4]).resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
OPEN_EVENTS = []
ACTIVE = True


def hook(event, args):
    if event != 'open' or not ACTIVE:
        return
    path = args[0]
    if isinstance(path, int):
        OPEN_EVENTS.append({'fd': path, 'mode': str(args[1]), 'flags': args[2]})
        return
    text = os.fsdecode(path)
    mode = str(args[1])
    flags = args[2]
    is_read = bool('r' in mode or 'a' not in mode and 'w' not in mode and flags & os.O_ACCMODE != os.O_WRONLY)
    normalized = text.replace('\\', '/')
    forbidden = any(x in normalized for x in ('/facts/', 'old_plan_rows', 'novel-samples', '/adopted', '/_封存', '/_试算_')) or fnmatch.fnmatch(Path(text).name, '*_result.json')
    OPEN_EVENTS.append({'path': str(Path(text).resolve()), 'mode': mode, 'flags': flags,
                        'read': is_read, 'forbidden': forbidden})
    if is_read and '/tools/__pycache__/' in normalized and normalized.endswith('.pyc'):
        OPEN_EVENTS[-1]['denied_bytecode'] = True
        raise FileNotFoundError('外层审计只准加载已登记源码')
    if forbidden and is_read:
        raise PermissionError('运行包装器拦下禁读路径')


sys.addaudithook(hook)
exit_code = 1
error = None
try:
    import run_pipeline
    from pipeline_r04_gate25 import R04Budget
    run_pipeline.Budget = R04Budget
    exit_code = run_pipeline.main()
except Exception as exc:
    error = {'type': type(exc).__name__, 'message': str(exc)}
finally:
    modules = sorted({str(Path(m.__file__).resolve()) for m in sys.modules.values()
                      if getattr(m, '__file__', None)})
    local_root = str(Path(__file__).resolve().parent) + '/'
    source_hashes = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in modules if path.startswith(local_root) and path.endswith('.py')}
    ACTIVE = False
    value = {'execution_identity': 'Codex', 'wrapper': str(Path(__file__).resolve()),
             'argv': sys.argv, 'exit_code': exit_code, 'error': error,
             'modules': modules, 'local_source_sha256': source_hashes, 'open_events': OPEN_EVENTS}
    (OUTPUT / 'runtime_audit.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
if error:
    print(json.dumps({'execution_identity': 'Codex', 'error': error}, ensure_ascii=False))
raise SystemExit(exit_code)
