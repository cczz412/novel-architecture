# 执行身份：Codex
"""Offline integrity, reserve and wire proof. No orchestrator main is invoked."""
import ast, copy, hashlib, json, os, sys, tempfile, types
from pathlib import Path
from unittest.mock import patch
J=Path(__file__).resolve().parent;W=Path('/workspace/codex-work/work/R04_pr-cleanup/novel-architecture')
sys.path.insert(0,str(W/'tools'))
from pipeline_common import c_viewpoint as v
from pipeline_budget25 import Budget, Halt, MODELS, c_text_reserve
from pipeline_source25 import write_json, read_json, digest
from pipeline_output28 import OUTPUT_POLICY
import pipeline_text105 as t
cases=[];details={}
def check(name,fn):
 try:fn();cases.append(dict(id=name,passed=True))
 except Exception as e:cases.append(dict(id=name,passed=False,error=repr(e)))
def req(x):assert x
def mat(texts,ch='01'):
 return dict(book_id='fictional123',chapter=ch,paragraphs=[dict(paragraph_id=f'p{i:03}',full_id=f'fictional123:ch{ch}:p{i:03}',text=x) for i,x in enumerate(texts,1)])
def entrypoints():
 source=W/'tools/gb_orchestrate_r04.py'
 main=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
 start=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='files' for t in n.targets))
 end=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='materials' for t in n.targets))
 segment=compile(ast.Module(body=main.body[start:end],type_ignores=[]),'<integrity-only>','exec')
 for old,new in [('legacy','evidence'),('evidence','legacy')]:
  d=Path(tempfile.mkdtemp(prefix='identity_',dir=J));archive=d/'synthetic.json';write_json(archive,{'fictional':True})
  budget=d/'budget.json';write_json(budget,{'input_pkg_sha':digest(archive),'gateway_job_id':'synthetic'})
  code=[W/'tools/pipeline_common/c_viewpoint.py'];out=d/'budget';out.mkdir()
  target=d/'orchestrator';target.mkdir()
  ns={'run_pipeline':types.SimpleNamespace(CODE_FILES=code),'TOOLS':W/'tools','Path':Path,'__file__':str(source),'sha':digest,'J':target,'read':read_json,'save':write_json}
  with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE=old,PIPELINE_A_MODE='legacy',PIPELINE_A_INCLUDE_BRIEF='true'):
   b=Budget(budget,out,archive,code);exec(segment,ns);exec(segment,ns)
   with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE=new):
    try:Budget(budget,out,archive,code)
    except Halt:pass
    else:raise AssertionError('budget resume allowed')
    try:b.guard()
    except Halt as e:req('C 视角' in str(e))
    else:raise AssertionError('runtime switch allowed')
    try:exec(segment,ns)
    except ValueError as e:req('C 视角' in str(e))
    else:raise AssertionError('orchestrator resume allowed')
 req('require_c_checkpoint(c_identity, c_checkpoint_identity())' in ast.unparse(main))
 # Frozen source inventory includes the new prompt module.
 tree=ast.parse((W/'tools/run_pipeline.py').read_text())
 assign=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='CODE_FILES' for x in n.targets))
 req('pipeline_common/c_viewpoint.py' in ast.unparse(assign))
check('both_entrypoints_deny_switch_both_directions_and_freeze_new_code',entrypoints)
def body_builder(path):
 tree=ast.parse(path.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
 call=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='call')
 nodes=copy.deepcopy(call.body[:2]);req(isinstance(nodes[0],ast.Assign) and isinstance(nodes[1],ast.If))
 fn=ast.parse('def body(role,messages,review):\n pass').body[0];fn.body=nodes+[ast.Return(value=ast.Name(id='body',ctx=ast.Load()))]
 module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));ns={'MODELS':MODELS,'OUTPUT_POLICY':OUTPUT_POLICY}
 exec(compile(module,'<pure-request-builder>','exec'),ns)
 return ns['body'],ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
def wires():
 old,oa=body_builder(J/'base/gb_orchestrate_r04.py');new,na=body_builder(W/'tools/gb_orchestrate_r04.py');req(oa==na)
 result=json.loads((J/'selftest_v123_v123.json').read_text());req(len(result['wire_proofs'])==8)
 for role in ('A','B','J2','C'):
  for review in (False,True):
   messages=[dict(role='user',content='虚构原文霁棠')]
   req(json.dumps(old(role,messages,review),ensure_ascii=False).encode()==json.dumps(new(role,messages,review),ensure_ascii=False).encode())
 details['production_body_ast_unchanged']=True;details['end_to_end_wire_proofs']=result['wire_proofs']
check('production_body_constructor_and_all_layer_byte_proofs',wires)
def legacy_source():
 old=ast.parse((J/'base/pipeline_text105.py').read_text());new=ast.parse((W/'tools/pipeline_text105.py').read_text())
 funcs=lambda tree:{n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
 oldf,newf=funcs(old),funcs(new)
 for name in oldf:
  if name in ('run','c_text','c_text_messages'):continue
  req(ast.dump(oldf[name],include_attributes=False)==ast.dump(newf[name],include_attributes=False))
 for name in ('c_text','c_text_messages'):
  n=copy.deepcopy(newf[name]);n.body=[x for x in n.body if not (isinstance(x,ast.If) and 'c_viewpoint.settings' in ast.unparse(x.test))]
  req(ast.dump(n,include_attributes=False)==ast.dump(oldf[name],include_attributes=False))
 oc={x.targets[0].id:ast.literal_eval(x.value) for x in old.body if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and x.targets[0].id.endswith('PROMPT')}
 for x in new.body:
  if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and x.targets[0].id in oc:req(ast.literal_eval(x.value)==oc[x.targets[0].id])
 details['legacy_function_bodies_and_prompts_unchanged']=True
check('legacy_function_bodies_and_original_prompts_unchanged',legacy_source)
def fallback():
 base=types.ModuleType('base_text105');exec((J/'base/pipeline_text105.py').read_text(),base.__dict__)
 m=mat(['霁棠推门。','闻澜转身。'])
 for kind in ('bad_reply','rejected','unanswered'):
  def one(module):
   calls=[]
   def call(*args):
    calls.append(args)
    if len(calls)==1:return {'_upstream_rejected':True} if kind=='rejected' else {'_upstream_unanswered':True} if kind=='unanswered' else {}
    return dict(paragraphs=[dict(p=p['paragraph_id'],main_tag='叙述带过',secondary_tag=None,viewpoint='全知',quote=p['text']) for p in m['paragraphs'] if p['paragraph_id'] in args[2][-1]['content']],scenes=[])
   with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='legacy'):result=module.c_text(m,call,lambda *args:None)
   return result,json.dumps(calls,ensure_ascii=False).encode()
  req(one(base)==one(t))
check('legacy_split_rejection_and_unanswered_bytes_outputs',fallback)
def reserve():
 a=mat(['我叫霁棠。']);b=mat(['我摸到木门。','我侧耳听了听。'],'02')
 actual=[];planned=[]
 def spy(msg,*args):planned.append(msg);return 1
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='evidence'),patch('pipeline_budget25.reserve',spy):
  r=c_text_reserve([a,b])
  bm=v.with_prior_context(b,[a,b])
  def call(*args):actual.append(args[2]);return {}
  t.c_text(bm,call,lambda *args:None)
 req(planned[1:]==actual and r['max_requests']==4)
 details['reserve_matches_split_requests']=True
check('reserve_uses_same_cross_chapter_evidence_as_runtime',reserve)
def blocked_b_and_context():
 a=mat(['我叫霁棠。']);b=mat(['我关上门。'],'02');seen=[]
 def call(role,ch,messages,review,stage):
  if role=='B':return {'_upstream_unanswered':True}
  req(role=='C');payload=json.loads(messages[-1]['content'].rsplit('\n',1)[-1]);seen.append(payload)
  return dict(paragraphs=[dict(p=p,main_tag='叙述带过',secondary_tag=None,viewpoint='霁棠',quote=text,viewpoint_basis=dict(kind='first_person',evidence=[dict(p=p,q=text)],narrator_confirmed=True)) for p,text in payload['paragraphs']],scenes=[])
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='evidence'):
  result=t.run([a,b],call,lambda *args:None)
 req(len(seen)==2 and seen[1]['viewpoint_context']['candidates'][0]['name']=='霁棠')
 req(result['chapters']['02']['C']['paragraphs'][0]['viewpoint']=='霁棠')
check('whole_pipeline_C_receives_prior_context_even_when_B_is_blocked',blocked_b_and_context)
def bounds():
 sources=[mat([f'我叫霁{chr(0x68e0+i)}。'],str(i)) for i in range(10)]
 target=mat(['我推门。'],'last');ctx=v.narrator_context(v.with_prior_context(target,[*sources,target]))
 req(ctx['status']=='conflict' and ctx['truncated'] and len(ctx['candidates'])==8)
 req(v.narrator_context(mat(['他喊道：','“我叫霁棠。']))['candidates']==[])
 req(v.narrator_context(mat(['我叫了两声。']))['status']=='missing')
 req(v.narrator_context(mat(['闻澜读信：“', '我叫霁棠。', '信结束了。”']))['status']=='missing')
 # This lexical ambiguity is deliberately NOT auto-approved: model confirmation + yellow still required.
 details['lexical_limit']='只提取显式自报姓名形式；句法相似或没有引号的嵌套叙述仍须模型判断，不能当成语义确认。'
check('context_bound_and_documented_lexical_ambiguity',bounds)
report=dict(execution_identity='Codex',real_requests=0,cases=cases,passed=sum(x['passed'] for x in cases),total=len(cases),details=details)
dest=J/('selftest_v123_extra_'+sys.argv[1]+'.json');assert not dest.exists();dest.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(int(report['passed']!=report['total']))

