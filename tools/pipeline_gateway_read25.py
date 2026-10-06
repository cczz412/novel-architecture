# 执行身份：Codex
"""Read existing gateway budget without making a model request."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from pipeline_budget25 import Budget
from pipeline_source25 import write_json

if __name__ == '__main__':
    reader = Budget.__new__(Budget)
    value = reader.get_budget(check_stop=False)
    write_json(Path(sys.argv[1]), {'method': 'GET /v1/budget', 'model_calls': 0, 'budget': value})
    print('执行身份：Codex；网关预算只读回执已保存')
