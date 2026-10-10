# 执行身份：Codex
# 执行身份：Grok Bot 作业外 v111——作业外整线编排（由 job_R04_v110/orchestrate_v110.py 收编入库）
"""Grok Bot 作业外整线编排：经本地网关逐条投递生产 text.run 的请求，挂起题原样重投一次。

v111 第2处：网关已结、入口报 HTTP 400 的回成 _upstream_rejected，交生产代码对半拆投。
v112：回包解析失败与上游未回答分开——解析失败先原样重投一次（计入总量闸）；重投仍解析失败回 _response_corrupt，
交生产代码按上游拒收同一路径对半拆投，仍不行标“回包损坏”待核。
v111 第3处：任何新投（含挂起重投）之前都先核“成功回答总数上限”，上限按 --cap-root 下各本 run/result.json 合计；
到上限就不投，阶段记 budget_cap_unsent，不再出现重投绕过总量闸的情况。
用法：python3 tools/gb_orchestrate_r04.py --job-dir DIR --source ZIP --book BOOK --chapters 01,02 --prefix r04_v111gb_x_ \
      --cap 80 --cap-root DIR_OF_BOOKS [--old-jobs result.json ...] [--allow-new A:,B:,J2:,C:]
本脚本不被生产代码导入；网关与回包目录仍是本机作业路径（见 ROOT 常量）。
"""
import argparse,datetime,hashlib,importlib.util,json,os,sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode=True
TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS))
from pipeline_common.local_paths import external_path
ROOT=external_path('GB_R04_ROOT')
V5=ROOT/'job_R04_v105';G=ROOT/'gateway'
GATEWAY_CODE=external_path('GB_GATEWAY_CODE')
LEDGER_BASE={'requests':686,'ok':677,'failed':9};LEDGER_COST=0.00624921  # v108 起作业外各轮之前的网关累计
OWN_PREFIXES=('r04_v108gb_','r04_v109gb_','r04_v110gb_','r04_v111gb_','r04_v112gb_')

def now():return datetime.datetime.now(datetime.timezone.utc)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())

def ok_count(result):
 return sum(x.get('gateway_result',{}).get('usage',{}).get('ok',0) for x in result['gateway_jobs'])

def used_successes(cap_root, own_dir, own_result):
 """总量闸：本本当前结果 + 同一上限组里其他各本已落盘结果的成功回答数。"""
 total=ok_count(own_result)
 if cap_root:
  for q in sorted(Path(cap_root).glob('*/run/result.json')):
   if q.parent.resolve()!=Path(own_dir).resolve():total+=ok_count(read(q))
 return total

def http_rejected(job_id):
 """网关已结、无回包且入口报 HTTP 400：上游拒收（内容审核等），区别于挂起与其他失败。"""
 log=G/'outbox'/job_id/'stderr.log'
 return log.exists() and 'HTTP Error 400' in log.read_text(errors='replace')

class NextRequest(Exception):
 def __init__(self,data):self.data=data

def main(argv=None):
 ap=argparse.ArgumentParser()
 ap.add_argument('--job-dir',required=True);ap.add_argument('--source',required=True);ap.add_argument('--book',required=True)
 ap.add_argument('--chapters',required=True);ap.add_argument('--prefix',required=True);ap.add_argument('--cap',type=int,required=True)
 ap.add_argument('--cap-root');ap.add_argument('--old-jobs',nargs='*',default=[]);ap.add_argument('--allow-new',default='A:,B:,J2:,C:')
 ap.add_argument('--resp-dirs',nargs='*',default=[]);ap.add_argument('--prepare-only',action='store_true')
 a=ap.parse_args(argv)
 import pipeline_text105 as text
 from pipeline_source25 import read_sources,write_json
 from pipeline_output28 import OUTPUT_POLICY
 from pipeline_budget25 import MODELS,parse_response
 import run_pipeline
 J=Path(a.job_dir);J.mkdir(parents=True,exist_ok=True)
 RESP_DIRS=[V5/'responses']+[Path(x) for x in a.resp_dirs]
 ALLOW_NEW=tuple(x for x in a.allow_new.split(',') if x)
 OLD=[x for p in a.old_jobs for x in read(p)['gateway_jobs'] if not x.get('reused_from_v105')]
 def save(p,x):write_json(p,x)
 def note(s):
  with (J/'progress_notes.md').open('a') as f:f.write('\n- '+datetime.datetime.now().astimezone().isoformat()+' Grok Bot：'+s+'\n')
  print(now().isoformat(),s,flush=True)
 def checkpoint(name,value):save(J/'pipeline'/(name.replace(':','_')+'.json'),value)
 files=list(run_pipeline.CODE_FILES)+[TOOLS/'pr_v105_run_r04.py',Path(__file__).resolve()]
 code={str(p):sha(p) for p in files}
 manifest=J/'runtime_integrity.json'
 if manifest.exists():assert read(manifest)['files']==code,'代码版本不同，停止续跑'
 else:save(manifest,{'files':code,'purpose':'本轮入口与生产函数投前投后完整性核对'})
 materials=read_sources(a.source,a.book,a.chapters.split(','))
 save(J/'public_materials.json',{'materials':materials,'archive_sha256':sha(a.source)})
 spec=importlib.util.spec_from_file_location('gateway_normalize_only',GATEWAY_CODE)
 gw=importlib.util.module_from_spec(spec);spec.loader.exec_module(gw)
 normalizer=SimpleNamespace(max_tokens=18000)
 result=read(J/'result.json') if (J/'result.json').exists() else {'execution_identity':'Grok Bot 作业外','gateway_jobs':[],'status':'running'}
 stages={x['stage_id']:x for x in result['gateway_jobs']}
 CAPPED=[];NOT_SENT=[];PARSE_FAILED=[]
 def capped(stage):
  if used_successes(a.cap_root,J,result)>=a.cap:
   CAPPED.append(stage);return True
  return False
 def call(role,ch,messages,review,stage):
  body={'model':MODELS['review'] if review else MODELS[role],'messages':messages,
        'max_tokens':OUTPUT_POLICY['review' if review else role]['max_tokens'],'temperature':0,'response_format':{'type':'json_object'}}
  if body['model']=='glm-5.3-flash':body['reasoning_effort']='low'
  else:body['thinking']={'type':'disabled'}
  assert 'execution_identity' not in json.dumps(body,ensure_ascii=False)
  clean,reservation=gw.Gateway.normalize_request(normalizer,body)
  assert clean['max_tokens']==body['max_tokens'] and reservation<=60000,(stage,reservation)
  if role=='A':assert len(json.dumps(messages,ensure_ascii=False).encode())<=8192
  digest=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
  fresh=lambda:{'stage_id':stage,'job_id':a.prefix+str(len(result['gateway_jobs'])+1).zfill(2),'body':body,'body_sha256':digest,
                'code_sha256':code,'reserved_tokens':reservation,'role':role,'review':review,'chapter':ch}
  if stage in stages:
   row=stages[stage]
   assert row['body_sha256']==digest,'同编号材料已改变'
   p=next((d/row['job_id']/'response.json' for d in RESP_DIRS if (d/row['job_id']/'response.json').exists()),None)
   if p:
    response=read(p)['response']
    try:return parse_response(response)
    except Exception as e:
     checkpoint(stage+':parse_failure',{'response':response,'error':str(e),'job_id':row['job_id']})
     return parse_failed(stage,row,str(e),fresh)
   if row.get('upstream_hung') and not row.get('retry_of'):
    if capped(stage):return {'_upstream_unanswered':True}  # v111：重投同样受总量闸
    retry={k:v for k,v in row.items() if k not in ('upstream_hung','settled','answer','job','submitted_at','wall_deadline')}
    retry.update(job_id=a.prefix+str(len(result['gateway_jobs'])+1).zfill(2),retry_of=row['job_id'],retry_reason='挂起题原样重投一次')
    raise NextRequest(retry)
   if row.get('settled') and http_rejected(row['job_id']):
    return {'_upstream_unanswered':True,'_upstream_rejected':True,'_upstream_reason':'HTTP 400 Bad Request'}  # v111 第2处：上游拒收交生产代码对半拆投
   if row.get('settled') or row.get('upstream_hung'):return {'_upstream_unanswered':True}
   raise NextRequest(row)
  old=[x for x in OLD if x['stage_id']==stage and x['body_sha256']==digest and x.get('settled') and any((d/x['job_id']/'response.json').exists() for d in RESP_DIRS)]
  if old:
   row={'stage_id':stage,'job_id':old[-1]['job_id'],'body_sha256':digest,'settled':True,'reused_from_v105':True,'note':'请求体 sha256 与已答同阶段逐字节一致，复用回包，未新发'}
   stages[stage]=row;result['gateway_jobs'].append(row);save(J/'result.json',result)
   response=read(next(d/row['job_id']/'response.json' for d in RESP_DIRS if (d/row['job_id']/'response.json').exists()))['response']
   try:return parse_response(response)
   except Exception as e:  # 复用回包与本轮回包同样处理：解析失败（含输出截断）先原样重投一次，不中止整线
    checkpoint(stage+':parse_failure',{'response':response,'error':str(e),'job_id':row['job_id']})
    return parse_failed(stage,row,str(e),fresh)
  if not ALLOW_NEW or not stage.startswith(ALLOW_NEW):
   NOT_SENT.append(stage);return {'_upstream_unanswered':True}
  if capped(stage):return {'_upstream_unanswered':True}
  raise NextRequest(fresh())
 def parse_failed(stage,row,error,fresh):
  """v112：回包到了但解析不了（坏 JSON、截断等）≠ 上游没回答。第一次原样重投；已是重投的回 _response_corrupt。"""
  if row.get('retry_of'):
   PARSE_FAILED.append({'stage':stage,'job_id':row['job_id'],'after_retry':True,'error':error})
   return {'_upstream_unanswered':True,'_response_corrupt':True,
           '_upstream_reason':'原样重投后仍解析失败：'+error[:160]}
  PARSE_FAILED.append({'stage':stage,'job_id':row['job_id'],'after_retry':False,'error':error})
  if capped(stage):  # 重投同样受总量闸；投不了就按回包损坏交生产代码，子包同样受闸
   return {'_upstream_unanswered':True,'_response_corrupt':True,
           '_upstream_reason':'解析失败且已到成功回答上限未重投：'+error[:160]}
  retry=fresh();retry.update(retry_of=row['job_id'],retry_reason='回包解析失败原样重投一次')
  raise NextRequest(retry)
 def gateway_check():
  t0=time.time()
  while read(G/'pending.json') and time.time()-t0<900:time.sleep(10)  # v111：等网关自行超时清掉在途（最长 15 分钟），不手改
  ledger=read(G/'ledger.json');win=read(G/'window.json');pending=read(G/'pending.json')
  expected=dict(LEDGER_BASE)
  for jid,row in ledger['jobs'].items():
   if jid.startswith(OWN_PREFIXES):
    for k in expected:expected[k]+=row.get(k,0)
  assert all(ledger['total'][k]==v for k,v in expected.items()),('网关对账不符',expected,ledger['total'])
  assert abs(ledger['total']['cost_usd']-LEDGER_COST)<1e-9
  assert not pending,'存在在途请求，停止新投'
  assert not win.get('soft') and not win.get('blocked'),'窗口停止'
  other=[p.stem for p in (G/'inbox').glob('*.json') if not (G/'outbox'/p.stem/'result.json').exists() and not p.stem.startswith(OWN_PREFIXES)]
  assert not other,('存在其他未结作业',other)
 def update_usage():
  usages=[x.get('gateway_result',{}).get('usage',{}) for x in result['gateway_jobs']]
  result['usage']={'requests':sum(x.get('requests',0) for x in usages),'success':sum(x.get('ok',0) for x in usages),
   'failed':sum(x.get('failed',0) for x in usages),'prompt_tokens':sum(x.get('prompt_tokens',0) for x in usages),
   'completion_tokens':sum(x.get('completion_tokens',0) for x in usages),'cost_usd':sum(x.get('cost_usd',0) for x in usages),
   'openrouter_requests':0,'openrouter_cost_usd':0}
  save(J/'result.json',result)
 try:
  while True:
   try:
    final=text.run(materials,call,checkpoint)
    save(J/'prediction.json',final['prediction']);save(J/'author_store.json',final['author_store'])
    result.update(not_sent_stages=NOT_SENT,budget_cap_unsent_stages=CAPPED,parse_failures=PARSE_FAILED,status='pipeline_finished',pipeline_complete=final['complete'])
    update_usage();note(a.book+' 整线装配结束，完整状态：'+str(final['complete']));return 0
   except NextRequest as nr:
    row=nr.data
    if a.prepare_only:
     save(J/'preflight_next_request.json',row);return 0
    if row['stage_id'] not in stages or row.get('retry_of'):
     gateway_check()
     assert all(sha(p)==v for p,v in code.items()),'投前代码变化'
     assert used_successes(a.cap_root,J,result)<a.cap,'总量闸：已到成功回答上限'
     row['submitted_at']=now().isoformat();row['wall_deadline']=(now()+datetime.timedelta(minutes=10)).isoformat()
     request_path=V5/'requests'/(row['job_id']+'.json');save(request_path,row)
     job={'job_id':row['job_id'],'argv':['tools/pr_v105_run_r04.py',str(request_path)],'max_requests':4,'max_tokens':row['reserved_tokens'],
          'timeout_s':600,'note':'执行身份：Grok Bot 作业外；'+row['stage_id']+('；重投 '+row['retry_of'] if row.get('retry_of') else ''),
          'max_cost_usd':0,'route':'ark'}
     row['job']=job;stages[row['stage_id']]=row;result['gateway_jobs'].append(row);update_usage()
     tmp=J/(row['job_id']+'.submission.tmp');tmp.write_text(json.dumps(job,ensure_ascii=False,indent=2)+'\n')
     os.link(tmp,G/'inbox'/(row['job_id']+'.json'))
     note('已投 '+row['job_id']+'，阶段 '+row['stage_id']+'，预留 '+str(row['reserved_tokens'])+'，截止 '+row['wall_deadline'])
    receipt=G/'outbox'/row['job_id']/'result.json'
    while not receipt.exists() and now()<datetime.datetime.fromisoformat(row['wall_deadline']):time.sleep(15)
    if receipt.exists():
     row['gateway_result']=read(receipt);row['settled']=True;row['settled_at']=now().isoformat()
     update_usage();note(row['job_id']+' 已回包：'+str(row['gateway_result'].get('usage')))
    else:
     row.update(upstream_hung=True,settled=False,answer=None);update_usage();note(row['job_id']+' 超过 10 分钟墙钟，记挂起、答案为空')
 except Exception as e:
  result.update(status='stopped',error={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})
  update_usage();note('停止：'+repr(e));raise

if __name__=='__main__':sys.exit(main())
