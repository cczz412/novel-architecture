# 执行身份：Codex
"""人物计划步骤先核对可装配字段；一次重写超限仍停止，不代判计划。"""
import json
import uuid
from pr_ark_client_r02 import Client as ArkClient, OUT
from pr_shape_guard_r02 import decode, A_FIELDS, STATUSES


def validate(response, materials):
    obj, conversions = decode(response,A_FIELDS)
    current = materials['chapter']
    for index,row in enumerate(obj['A']):
        if not isinstance(row.get('change_id'),str) or not row['change_id']:
            raise ValueError('A第'+str(index)+'行缺有效change_id')
        if not isinstance(row.get('old_ledger_keys'),list):
            raise ValueError('A第'+str(index)+'行old_ledger_keys须为数组')
        if row.get('plan') is not None:
            plan=row['plan']
            if not isinstance(plan,dict) or not isinstance(plan.get('content'),str) or not plan['content']:
                raise ValueError('A第'+str(index)+'行计划须有content正文字符串，不能是对象或空值')
    for index,row in enumerate(obj['old_plan_rows']):
        if not isinstance(row,dict) or not isinstance(row.get('old_key'),str) or not row['old_key']:
            raise ValueError('old_plan_rows第'+str(index)+'行缺old_key；不能直接复制输入local_key行，须按五字段结构明确归类')
        for key in ('meaning','plan_keys','retained_native_field','note'):
            if key not in row:
                raise ValueError('old_plan_rows第'+str(index)+'行缺'+key)
        if not isinstance(row['plan_keys'],list):
            raise ValueError('旧行plan_keys须为数组')
    expected={row['local_key'] for row in materials['old_plan_rows']}
    seen=[row['old_key'] for row in obj['old_plan_rows']]
    if set(seen)!=expected or len(seen)!=len(set(seen)):
        raise ValueError('本章旧召回行归类有缺失、重复或越界：'+json.dumps(sorted(expected-set(seen)),ensure_ascii=False))
    available={r['change_id'] for r in obj['A']}|{r['change_id'] for r in materials['previous_plans']['A']}
    previous={h['plan_key'] for h in materials['previous_plans']['plan_history']}
    given=set()
    for index,h in enumerate(obj['plan_history']):
        if not isinstance(h.get('plan_key'),str) or not isinstance(h.get('states'),list) or not isinstance(h.get('A_change_ids'),list):
            raise ValueError('plan_history第'+str(index)+'行计划键、状态数组或变动引用类型错误')
        if h['plan_key'] in given:
            raise ValueError('本章计划历史键重复：'+h['plan_key'])
        given.add(h['plan_key'])
        if not set(h['A_change_ids']).issubset(available):
            raise ValueError('计划历史变动引用不存在于当前或前章候选：'+h['plan_key'])
        if len(h['states'])!=1 or not isinstance(h['states'][0],dict) or h['states'][0].get('chapter')!=current:
            raise ValueError('计划历史本步骤只给本章'+current+'的一条状态，不复制早章；早章由程序保留：'+h['plan_key'])
        if h['states'][0].get('status') not in STATUSES:
            raise ValueError('计划历史状态必须从五种合法状态选择：'+h['plan_key'])
    if not previous.issubset(given):
        raise ValueError('既有计划缺本章明确状态，不能默删历史：'+json.dumps(sorted(previous-given),ensure_ascii=False))
    return obj,conversions


class Client(ArkClient):
    def call(self,model,messages,parameters,max_tokens=32000):
        materials=json.loads(messages[1]['content'].rsplit('\n输入材料：\n',1)[-1])
        folder=OUT/'format_attempts'/self.job/uuid.uuid4().hex
        folder.mkdir(parents=True,exist_ok=True)
        summary=dict(execution_identity='Codex',model=model,format_retry_limit=1,attempts=[],conversions=[])
        current=messages
        for retry in range(2):
            response=super().call(model,current,parameters,max_tokens=max_tokens)
            (folder/('attempt_'+str(retry)+'_response.json')).write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n')
            try:
                obj,conversions=validate(response,materials)
                summary['attempts'].append(dict(retry=retry,valid=True))
                summary['conversions'].extend(conversions)
                response['choices'][0]['message']['content']=json.dumps(obj,ensure_ascii=False,separators=(',',':'))
                (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
                return response
            except (ValueError,KeyError,TypeError,AttributeError) as exc:
                error=str(exc)
                summary['attempts'].append(dict(retry=retry,valid=False,error=error))
                summary['no_progress']=retry==1 and summary['attempts'][0].get('error')==error
                (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
                content=response.get('choices',[{}])[0].get('message',{}).get('content') or ''
                current=messages+([dict(role='assistant',content=content)] if content else [])+[dict(role='user',content=
                    '具体装配错误：'+error+'。请只重写人物计划步骤的五数组。输入旧行每条按old_key、meaning、plan_keys、retained_native_field、note归类。明确原字段归属，不代造计划。前章历史不能丢，本章状态有无变化都给明确记录；不要重复早章状态。其他正确故事内容保留。')]
        raise ValueError('人物计划步骤一次结构重写后仍不合格，停止本章：'+error)
