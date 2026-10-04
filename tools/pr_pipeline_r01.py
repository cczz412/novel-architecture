#!/usr/bin/env python3
# 执行身份：Codex
"""R06 代用基线与有限修复；样本输入输出只在外部交付目录。"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BOOKS=('gongan','dayi','qishi')
MODELS=('z-ai/glm-5.3-flash','z-ai/glm-5.3-flashx','deepseek/deepseek-v4.1-flash','moonshotai/kimi-k3')
OUT=Path('/workspace/codex-work/out/管线修复_R01')
AUDIT=('old_plan_rows','fact_chapters','source_chapters','plan_history','open_plan_keys','review_flags')
STATUSES=('未执行','执行中','兑现','落空','放弃')
TAGS=('叙述带过','动作展开','对话','心理','场景')
TRANSPORT_RETRIES=2
REPAIR_RETRIES=1
SYSTEM='你是小说抽取的事实与账本处理员。仅用本次给出的材料，不借已知故事补写。输出单个合法 JSON，不输出解释或代码围栏。'
RULES='''执行身份：Codex。按现行 R6 抽取规则完成本章 R06 离线候选，不宣称正式入账或独立复核。
抽句保留已写原因、情绪、旁人反应、物件细节、否定、条件、将要、不确定和说话或心想归属；抽句不提前按计划分类。正确旧句沿用，错句替换，漏句新增，不借替换重写正确句子。引号必须是所引段的逐字原话；不能用碎片引号拼接叙述。事实正文禁止原文称、本章、旁白、审稿说明、分析标签和括注，正常故事归属必须保留。梦境、回忆和内层故事写明持有人与层次，不当当前现场。
记账才分类承诺动作与未来内容，一句可多账。渴望、困境、抉择不塞进人物计划。自己将要做的可执行行动可立计划，同章做成仍记兑现。名词准备、正在发生的动作、别人提出的要求不能仅凭词命中立计划。当场被拒、回述意向、玩笑、不可能条件、愿望感慨、未建人物档的一次性匿名或非人主体、书中书角色意向只留事实。无名但承担稳定安排职能的角色不能仅因无姓名撤掉；拿不准如实黄标。
状态仅未执行、执行中、兑现、落空、放弃。未开头且无后文结果保持未执行；开始不等于完成。已开头的一次性动作只在离场、明确期限过或前提排除时收尾，且先核是否已做成；长期目标继续执行中。主动咽回话或改主意是放弃。放弃后重做另起新计划键。目标结果出现但不能证明本人主动做到，不自动兑现。窄目标做成不借更大目标失败标落空。
条件只存前提原话，条件出现必须另有事实；未出现保持未执行，出现且做到兑现，出现但有未履行证据才落空。假设回答须条件可发生且认真说才立计划。期限保存原话，不用章号或现实时间造故事锚；没依据留空。查看意向以靠近查看等原目标为完成线。不能补未写的承诺内容、对象、延期原因或后果。
每条有效计划有稳定键及从引入章到本章的逐章历史；只凭本章新事实更新，不倒填前章、不覆盖历史。前章已结状态继续保留但不进未了结清单。兑现指向真正履约句，不能来源兑现同键或偷换为提问、准备动作、后续不同事件；主体与目标须一致。引用用本地候选键，正式三个事实引用均 null。
C 与事实同遍抽：所有本章段落各一个主标签、最多一个不同副标签，视角按感知者而非说话人；不知道留空并说明。真实现场的地点、光线天气、陈设视觉物、声音气味、氛围分别摘短引，没写留空，不用占位词或整段照贴。纯画面留 C，不漏 B 中明写的心声、情绪和原因。身份别名只在已建立双重身份时可对照，不擅自统一正文人名异写。
旧句去向表四类互斥完整，仍未决但有效的正文保留；原段去向逐段注明有效事实键，没可抽事实要有具体原因。旧计划召回行不一定是计划，记录每条去向，正确其他人物序列保留。理由写本条具体证据，不能用模板或把审查腔写进正文或黄标。拿不准分管线语义黄标、原文真实未知、内容限审、格式引用缺口；不要假称调用过另一模型。
不得越过 scope_limits；爽点、成长、伏笔、动机分析属于后期组装，不混进事实、计划或 C。事实句号与变动号不冒充正式事实身份。'''
FORMAT='''输出完整本章候选结构：batch_id,identity,basis,A[],B[],C[],unresolved[],coverage[],review_audit{}。
A 行：change_id,book_id,as_of_chapter,old_ledger_keys,decision(沿用/修订/新增/撤回计划分类),subject_text,plan,candidate_refs,reason,evidence。
plan 为 null 或 {content,scope:"in_book_character",status,source_fact_ref:null,fulfilled_fact_ref:null,deadline:null或{text,story_time:null},condition:null或原话,condition_fact_ref:null}。candidate_refs 为 null 或 {source_record_key,fulfilled_record_key,condition_record_key}。新计划的稳定键写在 plan_history；更新前章计划使用原 A 变动号和历史计划键。
B 行：change_id,book_id,chapter,operation(替换/新增),old_record_keys[],local_key,text,reason,evidence[{paragraph_id,quote}]；新增键使用本次提供的前缀，替换使用原旧键。所有新变动证据用完整段号及连续逐字短引。
C 按本章 {book_id,chapter,paragraphs:[{paragraph_id(短段号),main_tag,secondary_tag,viewpoint,quote,review_status:"已标注"或"限审",note}],scenes:[{scene_id,paragraph_ids(短号数组),location[],light_weather[],objects_visuals[],sounds_smells[],atmosphere[]}]}；场景格是 {text,evidence:[{paragraph_id(完整号),quote}]} 数组。
review_audit 必有六数组：old_plan_rows:[{old_key,meaning(沿用原意/修正原意/非计划保留原类/审查批注/未决),plan_keys,retained_native_field,note}]；fact_chapters:[{book_id,chapter,kept_old_keys,revised_old_keys,excluded_nonstory_keys,flagged_old_keys}]；source_chapters:[{book_id,chapter,paragraphs:[{paragraph_id,fact_record_keys,disposition(已有句承接/本次补修/没有可抽事实/限审/未决),note}]}]；plan_history:[{plan_key,book_id,old_ledger_keys,A_change_ids,introduced_chapter,states:[{chapter,status,source_record_key,fulfilled_record_key,condition_record_key,change_basis_record_keys,note}]}]；open_plan_keys 为本书本章未执行/执行中键数组；review_flags:[{flag_id,book_id,chapter,category(管线语义黄标/原文真实未知/内容限审/格式引用缺口),fact_keys,plan_keys,paragraph_ids,reason,conservative_text,original_gap_keys}]。已有历史的早章由程序保留不变，本章 states 只输出本章追加状态，不重复复制早章；已结计划也保留本章状态。不要重复列前章 B 或 C。JSON 紧凑输出，短引、具体短理由，不缩减实核内容。
本地身份固定 OFFLINE_SAMPLE_DELTA_NOT_FORMAL_LEDGER，依据固定 EXTRACTION_R6_INTENT_V2_1_PR374_INPUT_R06。本章覆盖只报实际阅读量。'''


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def external(path):
    p=Path(path).resolve()
    if not p.is_relative_to(OUT):
        raise ValueError('样本相关输出只能放本任务交付目录')
    return p


class Client:
    def __init__(self):
        self.base=os.environ['PR_LLM_BASE_URL'].rstrip('/')
        url=urllib.parse.urlparse(self.base)
        if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path!='/v1' or not url.port:
            raise ValueError('只允许网关本机地址')
        self.job=os.environ['PR_JOB_ID']
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def get(self,path):
        with self.opener.open(self.base+path,timeout=45) as response:
            return json.load(response)

    def call(self,model,messages,reasoning,max_tokens=16000):
        payload={'model':model,'messages':messages,'max_tokens':max_tokens,'temperature':0,
                 'response_format':{'type':'json_object'},'reasoning':reasoning}
        req=urllib.request.Request(self.base+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),
                                   headers={'Content-Type':'application/json','X-PR-Job-ID':self.job})
        for attempt in range(TRANSPORT_RETRIES+1):
            try:
                with self.opener.open(req,timeout=1200) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                # 上游正文与请求头不打印；5xx 若网关已 STOP，重试会被拒绝。
                if exc.code not in (429,500,502,503,504) or attempt==TRANSPORT_RETRIES:
                    raise RuntimeError('网关返回 HTTP '+str(exc.code)) from None
                time.sleep((1,3)[attempt])


def parse_response(response):
    choice=response['choices'][0]
    if choice.get('finish_reason') not in ('stop',None):
        raise ValueError('模型输出未正常结束，不能把截断算完整')
    text=choice['message']['content']
    text=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',text)
    data=json.loads(text)
    if not isinstance(data,dict) or any(not isinstance(data.get(k),list) for k in ('A','B','C')):
        raise ValueError('缺少三层对象数组')
    if not isinstance(data.get('review_audit'),dict) or any(not isinstance(data['review_audit'].get(k),list) for k in AUDIT):
        raise ValueError('缺少完整核对数组')
    return data


def old_rows_for_chapter(rows,keys,chapter):
    return [r for r in rows if set(r.get('source_record_keys',[])) & keys or
            re.search(r':ch0*'+str(int(chapter))+r'(?:\D|$)',str(r.get('as_of_source_key','')))]


def read_book(config,chapter):
    bid=config['book_id']
    with zipfile.ZipFile(config['group_files']['input_zip']) as z:
        prefix='books/'+bid+'/'
        source=json.loads(z.read(prefix+'sources/'+chapter+'_paragraphs.json'))
        facts=json.loads(z.read(prefix+'facts/'+chapter+'.json'))['facts']
        old=json.loads(z.read(prefix+'old_plan_rows.json'))
        if isinstance(old,dict):old=old.get('rows',[])
        limits=json.loads(z.read(prefix+'scope_limits.json')) if prefix+'scope_limits.json' in z.namelist() else {}
        schema_hashes={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('rules/') or n.endswith('.schema.json')}
    return dict(book_id=bid,chapter=chapter,paragraphs=source['paragraphs'],facts=facts,
                old_plan_rows=old_rows_for_chapter(old,{f['local_key'] for f in facts},chapter),
                scope_limits=limits,basis_hashes=schema_hashes)


def messages_for(data,previous):
    materials={k:v for k,v in data.items() if k!='basis_hashes'}
    materials['previous_plans']={'A':previous['A'],'plan_history':previous['review_audit']['plan_history']}
    materials['new_key_prefix']='local:pr:'+data['book_id']+':ch'+data['chapter']+':add:'
    instructions=RULES+'\n'+FORMAT+'\n本次只处理书号 '+data['book_id']+' 的第 '+data['chapter']+' 章。'
    return [{'role':'system','content':SYSTEM},{'role':'user','content':instructions+'\n输入材料：\n'+json.dumps(materials,ensure_ascii=False,separators=(',',':'))}]


def empty_result():
    return dict(batch_id='PR_R01',identity='OFFLINE_SAMPLE_DELTA_NOT_FORMAL_LEDGER',
                basis='EXTRACTION_R6_INTENT_V2_1_PR374_INPUT_R06',A=[],B=[],C=[],unresolved=[],coverage=[],
                review_audit={k:[] for k in AUDIT})


def merge_rows(old,new,key):
    result={str(r[key]):copy.deepcopy(r) for r in old}
    for r in new:
        result[str(r[key])]=copy.deepcopy(r)
    return list(result.values())


def _assemble(result,chapter_result):
    for k in ('A','B'):
        result[k]=merge_rows(result[k],chapter_result[k],'change_id')
    for k in ('C','unresolved','coverage'):
        result[k].extend(copy.deepcopy(chapter_result.get(k,[])))
    ra,cr=result['review_audit'],chapter_result['review_audit']
    for k in ('fact_chapters','source_chapters','review_flags'):
        ra[k].extend(copy.deepcopy(cr[k]))
    ra['old_plan_rows']=merge_rows(ra['old_plan_rows'],cr['old_plan_rows'],'old_key')
    current={h['plan_key']:h for h in ra['plan_history']}
    for h in cr['plan_history']:
        if h['plan_key'] in current:
            old=current[h['plan_key']]
            past={str(s['chapter']):s for s in old['states']}
            for s in h['states']:
                c=str(s['chapter'])
                if c in past and past[c]!=s:
                    raise ValueError('试图覆盖既有历史，停止装配')
            h=copy.deepcopy(h)
            h['states']=merge_rows(old['states'],h['states'],'chapter')
        current[h['plan_key']]=copy.deepcopy(h)
    ra['plan_history']=list(current.values())
    ra['open_plan_keys']=sorted(h['plan_key'] for h in current.values() if h['states'] and h['states'][-1]['status'] in ('未执行','执行中'))
    # A 是当前候选视图。只投影模型明确给出的历史终态与引用，不推断语义。
    for h in ra['plan_history']:
        if not h['states']:continue
        s=h['states'][-1]
        for row in result['A']:
            if row.get('change_id') in h.get('A_change_ids',[]) and row.get('plan'):
                row['plan']['status']=s['status']
                row['as_of_chapter']=s['chapter']
                row['candidate_refs']={k:s.get(k) for k in ('source_record_key','fulfilled_record_key','condition_record_key')}
    return result


def assemble(result,chapter_result):
    # 验证失败时不留半套变动，避免已有历史与当前候选失去对应。
    candidate=copy.deepcopy(result)
    _assemble(candidate,chapter_result)
    result.clear()
    result.update(candidate)
    return result


def check_quote_guard(doc,data):
    """一轮只处理逐字证据及直引，不用词表替语义作判断。"""
    paragraphs={r['paragraph_id']:r['text'] for r in data['paragraphs']}
    errors=[]
    for row in doc['B']:
        evidence=row.get('evidence',[])
        sources=[]
        for e in evidence:
            pid=e.get('paragraph_id','')
            if pid not in paragraphs or not e.get('quote') or e['quote'] not in paragraphs[pid]:
                errors.append({'key':row.get('local_key'),'type':'证据不是所指段的逐字子串','paragraph_id':pid})
            elif pid in paragraphs:sources.append(paragraphs[pid])
        for q in re.findall(r'“([^”]+)”|「([^」]+)」|『([^』]+)』|"([^"\n]+)"',row.get('text','')):
            quote=next(x for x in q if x)
            if not any(quote in s for s in sources):
                errors.append({'key':row.get('local_key'),'type':'事实直引不是关联段逐字子串','quote':quote})
        if re.search(r'”\s*[、，,]?\s*“',row.get('text','')):
            errors.append({'key':row.get('local_key'),'type':'碎片引号拼接叙述'})
    return errors


def configure_probe(client,output):
    models=client.get('/models')
    guide=client.get('/reasoning-guide')
    dump(output/'models.json',models)
    dump(output/'reasoning_guide.json',guide)
    # 必须已查到官方 enabled 参数说明，再发虚构短文验证，不能凭记忆猜参数。
    if 'enabled' not in guide.get('html','') or 'false' not in guide.get('html',''):
        raise RuntimeError('未取得关闭思考的官方说明')
    policies={}
    for model in MODELS:
        metadata=next((m for m in models['data'] if m['id']==model),None)
        if metadata is None:
            policies[model]={'usable':False,'reason':'模型目录缺失'};continue
        supported=metadata.get('supported_parameters',[])
        capabilities=metadata.get('reasoning') or {}
        mandatory=capabilities.get('mandatory',False)
        if mandatory:
            efforts=capabilities.get('supported_efforts') or []
            if not efforts:
                policies[model]={'usable':False,'reason':'强制思考模型未说明可用低档'};continue
            reasoning={'effort':efforts[-1],'exclude':True}
        else:
            reasoning={'enabled':False,'exclude':True}
        try:
            response=client.call(model,[{'role':'user','content':'虚构测试。只输出 JSON：{"ok":true}。'}],reasoning,max_tokens=2048 if mandatory else 128)
            dump(output/(model.replace('/','_')+'_probe.json'),response)
            detail=response.get('usage',{}).get('completion_tokens_details') or {}
            rt=detail.get('reasoning_tokens')
            stop=response['choices'][0].get('finish_reason')=='stop'
            verified=stop and rt is not None and (mandatory or rt==0)
            policies[model]={'usable':verified,'reasoning':reasoning,'reasoning_tokens':rt,'mandatory':mandatory,
                             'supported_parameters':supported,'verified':verified,
                             'reason':'实测最低思考档，不能关闭' if mandatory and verified else '实测关闭思考' if verified else '思考量或结束状态未验证'}
        except Exception as exc:
            policies[model]={'usable':False,'reason':str(exc)}
    dump(output/'reasoning_policy.json',policies)
    return policies


def run_book(args):
    config=next(r for r in json.loads((OUT/'books_selected.json').read_text()) if r['code']==args.book)
    output=external(args.out)
    output.mkdir(parents=True,exist_ok=True)
    result=empty_result()
    receipt={'book':args.book,'model':args.model,'round':args.round,'chapters_requested':args.chapters,
             'completed_chapters':[],'calls':[],'partial':False,'unmeasured':['语义独立复核'],'transport_retry_limit':TRANSPORT_RETRIES,'repair_retry_limit':REPAIR_RETRIES,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    client=None if args.prepare_only else Client()
    policy=None
    if client:
        policies=json.loads(external(args.policy).read_text())
        policy=policies[args.model]
        if not policy['usable']:raise RuntimeError('模型思考参数尚未验证，禁止实跑')
    for n in range(1,args.chapters+1):
        ch=f'{n:02d}'
        data=read_book(config,ch)
        messages=messages_for(data,result)
        if args.prepare_only:
            dump(output/f'ch{ch}_prepared.json',{'book_id':data['book_id'],'chapter':ch,'basis_hashes':data['basis_hashes'],
                 'input_bytes':len(json.dumps(messages,ensure_ascii=False).encode()),'paragraph_count':len(data['paragraphs']),
                 'fact_count':len(data['facts']),'old_plan_count':len(data['old_plan_rows'])})
            continue
        try:
            response=client.call(args.model,messages,policy['reasoning'])
            dump(output/f'ch{ch}_response.json',response)
            receipt['calls'].append(response.get('usage',{}))
            candidate=parse_response(response)
            if args.guard=='quotes':
                errors=check_quote_guard(candidate,data)
                dump(output/f'ch{ch}_checks_before.json',errors)
                if errors:
                    fingerprint=hashlib.sha256(json.dumps(errors,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    # 每个责任章至多一次返回修正；同类错误未减少即停止，不重复循环。
                    repair=messages+[{'role':'assistant','content':json.dumps(candidate,ensure_ascii=False)},
                                     {'role':'user','content':'只修这些逐字引文问题，其他正确内容保持，输出完整本章结构：'+json.dumps(errors,ensure_ascii=False)}]
                    response=client.call(args.model,repair,policy['reasoning'])
                    dump(output/f'ch{ch}_repair_response.json',response)
                    receipt['calls'].append(response.get('usage',{}))
                    candidate=parse_response(response)
                    after=check_quote_guard(candidate,data)
                    dump(output/f'ch{ch}_checks_after.json',after)
                    if after:
                        dump(output/f'ch{ch}_stop_rule.json',{'remaining':len(after),'retry_limit':1,
                             'no_progress':hashlib.sha256(json.dumps(after,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==fingerprint})
                        candidate['review_audit']['review_flags'].append({'flag_id':'PR:'+data['book_id']+':'+ch,
                            'book_id':data['book_id'],'chapter':ch,'category':'管线语义黄标',
                            'fact_keys':sorted({r['key'] for r in after if r.get('key')}),'plan_keys':[],
                            'paragraph_ids':[],'reason':'一次重写后仍有逐字证据或引号问题，待独立复核',
                            'conservative_text':None,'original_gap_keys':[]})
            assemble(result,candidate)
            receipt['completed_chapters'].append(ch)
            dump(output/f'ch{ch}_result.json',candidate)
            dump(output/'prediction.json',result)
            dump(output/'run_receipt.json',receipt)
            print('本章已落盘',args.book,ch,'费用',sum(float(c.get('cost',0)) for c in receipt['calls']),flush=True)
        except Exception as exc:
            receipt['partial']=True
            receipt['error']='本章未完成：'+str(exc)
            result['unresolved'].append({'book_id':data['book_id'],'chapter':ch,'keys':[],'reason':receipt['error']})
            break
    if args.prepare_only:
        dump(output/'prepare_receipt.json',receipt)
        print('离线准备完成',args.book,args.chapters)
        return 0
    receipt['usage']={k:sum(float(c.get(k,0)) for c in receipt['calls']) for k in ('prompt_tokens','completion_tokens','cost')}
    dump(output/'prediction.json',result)
    dump(output/'run_receipt.json',receipt)
    return 1 if receipt['partial'] else 0


def main():
    parser=argparse.ArgumentParser(description='R06 代用基线，只许三本与白名单模型；代码不保存小说材料')
    sub=parser.add_subparsers(dest='command',required=True)
    probe=sub.add_parser('probe',help='从网关查官方参数并用虚构文本验证四模型');probe.add_argument('--out',required=True)
    run=sub.add_parser('run',help='逐章抽取与有限修正')
    run.add_argument('--book',choices=BOOKS,required=True);run.add_argument('--model',choices=MODELS,required=True)
    run.add_argument('--out',required=True);run.add_argument('--round',type=int,default=0)
    run.add_argument('--chapters',type=int,choices=range(1,9),default=8)
    run.add_argument('--policy',default=str(OUT/'probe/reasoning_policy.json'))
    run.add_argument('--guard',choices=['none','quotes'],default='none');run.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.command=='probe':
        configure_probe(Client(),external(args.out));return 0
    if not 0<=args.round<=6:parser.error('最多六轮')
    return run_book(args)


if __name__=='__main__':
    raise SystemExit(main())
