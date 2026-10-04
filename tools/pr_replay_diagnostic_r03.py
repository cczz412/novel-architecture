# 执行身份：Codex
"""完整旧响应的机械恢复诊断；缺少的A状态只报缺口，不请求模型。"""
import argparse, hashlib, json
from pathlib import Path
from types import SimpleNamespace
import pr_layers_v2_r03 as pipeline


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--book',required=True,choices=('gongan','dayi','qishi'))
    p.add_argument('--model',required=True,choices=pipeline.MODELS)
    a=p.parse_args()
    source=pipeline.external(a.source);output=pipeline.external(a.out)
    old=json.loads((source/'run_receipt.json').read_text())
    assert len(old['completed_chapters'])==8,'仅诊断原模型完整8章响应'
    pipeline.Client=lambda:None
    def replay(client,model,policy,schema,material,gate,folder,label,receipt,layer,reviewer=None):
        if layer!='A':raise RuntimeError('BC原响应缺失，诊断不能生成替代')
        ch=material['chapter']
        if any((source/('ch'+ch)).glob(label+'_response_[01].json')):
            return pipeline.replay_task(source,ch,label,gate,folder,receipt)
        raw={'updates':[]} if label.startswith('A_update') else {'old_rows':[],'plans':[]}
        raw,errors,log=gate(raw)
        pipeline.dump(folder/(label+'_task.json'),dict(execution_identity='Codex',diagnostic_only=True,missing_original_response=True,pending_errors=errors))
        return raw,errors
    pipeline.task=replay
    args=SimpleNamespace(book=a.book,model=a.model,out=str(output),round=2,chapters=8,
        a_model=None,b_model=None,c_model=None,b_group=16,c_group=24,a_group=8,
        replay_bc=str(source),review_model=None,policy=str(pipeline.OUT/'probe/reasoning_policy.json'))
    code=pipeline.run(args)
    receipt=json.loads((output/'run_receipt.json').read_text())
    receipt.update(diagnostic_only=True,actual_new_model_requests=0,inherited_source=str(source),
                   diagnostic_entry_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   limitations=['原响应产生时的前章上下文与恢复后不同，不能当新配置生成质量','缺少的逐章状态未补写'])
    pipeline.dump(output/'run_receipt.json',receipt)
    return code


if __name__=='__main__':raise SystemExit(main())
