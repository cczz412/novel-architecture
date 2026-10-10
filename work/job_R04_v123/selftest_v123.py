# 执行身份：Codex
"""Fictional text and handwritten model callbacks; transport is never invoked."""
import copy, hashlib, json, os, sys, types
from pathlib import Path
from unittest.mock import patch
J=Path(__file__).resolve().parent
W=Path('/workspace/codex-work/work/R04_pr-cleanup/novel-architecture')
sys.path.insert(0,str(W/'tools'))
import pipeline_text105 as t
from pipeline_author25 import build_views
from pipeline_budget25 import MODELS
from pipeline_output28 import OUTPUT_POLICY
base=types.ModuleType('base_text105');exec((J/'base/pipeline_text105.py').read_text(),base.__dict__)
try:
 from pipeline_common import c_viewpoint as v
except ImportError:
 v=None
TAG=sys.argv[1];cases=[];proofs=[];examples={}
def check(name,fn,requires_new=False):
 if requires_new and v is None:
  cases.append(dict(id=name,status='skipped',reason='修前没有新开关'));return
 try:fn();cases.append(dict(id=name,status='passed'))
 except Exception as exc:cases.append(dict(id=name,status='failed',error=repr(exc)))
def req(value):assert value
def material(texts,ch='01',book='fictional123'):
 return dict(book_id=book,chapter=ch,paragraphs=[dict(paragraph_id=f'p{i:03}',full_id=f'{book}:ch{ch}:p{i:03}',text=s) for i,s in enumerate(texts,1)])
def reply(m,view,kind='limited',confirm=False,evidence=None):
 return dict(paragraphs=[dict(p=p['paragraph_id'],main_tag='叙述带过',secondary_tag=None,viewpoint=view,quote=p['text'],
  viewpoint_basis=dict(kind=kind,evidence=evidence if evidence is not None else [dict(p=p['paragraph_id'],q=p['text'])],narrator_confirmed=confirm)) for p in m['paragraphs']],scenes=[])
def run_c(m,raw,mode='evidence',module=t):
 calls=[];saved={}
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE=mode):
  result,pending=module.c_text(m,lambda *args:(calls.append(args) or copy.deepcopy(raw)),lambda k,z:saved.update({k:copy.deepcopy(z)}))
 return result,pending,calls,saved
def body(role,msg,review):
 b={'model':MODELS['review'] if review else MODELS[role],'messages':msg,
    'max_tokens':OUTPUT_POLICY['review' if review else role]['max_tokens'],'temperature':0,'response_format':{'type':'json_object'}}
 if b['model']=='glm-5.3-flash':b['reasoning_effort']='low'
 else:b['thinking']={'type':'disabled'}
 return b
def whole(module,mode=None):
 m=material(['霁棠决定明天修桥。','我叫霁棠。']);calls=[]
 def call(role,ch,msg,review,stage):
  calls.append(dict(role=role,review=review,stage=stage,body=body(role,msg,review)))
  p=json.loads(msg[1]['content'].rsplit('\n',1)[-1])
  if role=='C':return reply(m,'霁棠','first_person',True)
  if role=='B':
   if not review:return dict(rows=[dict(text=x['text'],subject='霁棠',kind='事件',mentions=['霁棠'],layer='现场',ev=[dict(p=x['paragraph_id'],q=x['text'])]) for x in m['paragraphs']])
   return dict(verdicts=[dict(id=x['_id'],accept=True,reason='手写通过') for x in p['rows']],patches=[])
  if role=='A':
   if review:return dict(verdicts=[dict(id=x['_id'],accept=True,reason='手写通过') for x in p['rows']],patches=[])
   key=p['facts'][0]['local_key']
   return dict(rows=[dict(key=None,subject='霁棠',content='明天修桥',status='未执行',deadline=None,condition=None,source=key,fulfilled=None,condition_ref=None,basis=[key],reason='手写候选',ev=[dict(p='p001',q=m['paragraphs'][0]['text'])])])
  if not review:return dict(rows=[dict(id=x['id'],section='people',row={**x['original'],'aspect':'事项'}) for x in p['items']])
  return dict(verdicts=[dict(id=x['id'],accept=True,reason='手写通过',section=x['section'] or 'people',row={**x['candidate'],'aspect':x['candidate'].get('aspect','事项')},speaker=None) for x in p['items']])
 with patch.dict(os.environ,PIPELINE_A_MODE='legacy'):
  os.environ.pop('PIPELINE_C_VIEWPOINT_MODE',None)
  if mode is not None:os.environ['PIPELINE_C_VIEWPOINT_MODE']=mode
  try:result=module.run([m],call,lambda *args:None)
  finally:os.environ.pop('PIPELINE_C_VIEWPOINT_MODE',None)
 return result,calls
def legacy_wire(mode):
 old,oc=whole(base);new,nc=whole(t,mode)
 req(old==new)
 for role in ('A','B','J2','C'):
  left=[x for x in oc if x['role']==role];right=[x for x in nc if x['role']==role]
  req(left and right)
  a=json.dumps(left,ensure_ascii=False).encode();b=json.dumps(right,ensure_ascii=False).encode();req(a==b)
  proofs.append(dict(case='unset' if mode is None else mode,role=role,identical=True,requests=len(left),sha256=hashlib.sha256(a).hexdigest()))
check('legacy_unset_all_layers_wire_and_output',lambda:legacy_wire(None))
check('legacy_explicit_all_layers_wire_and_output',lambda:legacy_wire('legacy'))
def legacy_problem():
 m=material(['我推开门，只听见自己的脚步声。'])
 r=run_c(m,reply(m,'第一人称','first_person'),mode='legacy')[0]
 req(r['paragraphs'][0]['viewpoint']=='第一人称');examples['before_first_person']=r
 m=material(['霁棠只看见木门。门外如何，他并不知道。'])
 r=run_c(m,reply(m,'全知','omniscient'),mode='legacy')[0]
 req(r['paragraphs'][0]['viewpoint']=='全知');examples['before_limited_as_omni']=r
check('legacy_known_failure_types_are_not_corrected',legacy_problem)
def candidate():
 m=material(['我叫霁棠。屋外的脚步声使我停住。']);c=v.narrator_context(m)
 req(c['status']=='candidate' and [x['name'] for x in c['candidates']]==['霁棠'])
 req(c['candidates'][0]['evidence'][0]['q']=='我叫霁棠。')
check('first_person_program_candidate',candidate,True)
def perspective(view,kind,text,confirm=False):
 m=material([text]);r,p,c,_=run_c(m,reply(m,view,kind,confirm))
 req(r['paragraphs'][0]['viewpoint']==view and len(c)==1)
 req(r['paragraphs'][0]['viewpoint_status']=='待核' and r['paragraphs'][0]['viewpoint_card_color']=='yellow');examples[kind]=r
check('limited_person_not_forced_to_omniscient',lambda:perspective('霁棠','limited','霁棠只看见木门。门外如何，他并不知道。'),True)
check('first_person_resolves_name_after_model_confirmation',lambda:perspective('霁棠','first_person','我叫霁棠。我只听见门外的脚步。',True),True)
check('true_omniscient_keeps_omniscient',lambda:perspective('全知','omniscient','霁棠心里盼雨，另一座城里的闻澜暗自怕雨；两人都不知道对方的心事。'),True)
def unknown(kind):
 texts={'missing':['我推开门。'],'conflict':['我叫霁棠。','我叫闻澜。'],'unconfirmed':['我叫霁棠。'],'generic_label':['我叫霁棠。']}
 m=material(texts[kind]);raw=reply(m,'第一人称' if kind=='generic_label' else '霁棠','first_person',kind!='unconfirmed')
 r=run_c(m,raw)[0];req(all(x['viewpoint']=='未定' for x in r['paragraphs']));examples[kind]=r
for k in ('missing','conflict','unconfirmed','generic_label'):check('candidate_'+k+'_stays_pending',lambda k=k:unknown(k),True)
def reject_quote_intro():
 m=material(['闻澜说：“我叫霁棠。”她说完就离开了。']);req(v.narrator_context(m)['candidates']==[])
check('dialogue_self_introduction_not_narrator_proof',reject_quote_intro,True)
def prior_and_switch():
 a=material(['我叫霁棠。'],'01');b=material(['闻澜看着关紧的门，只能猜霁棠去了哪里。'],'02')
 bm=v.with_prior_context(b,[a,b]);req(v.narrator_context(bm)['candidates'][0]['name']=='霁棠')
 r=run_c(bm,reply(bm,'闻澜','limited'))[0]
 req(r['paragraphs'][0]['viewpoint']=='闻澜');req(r['paragraphs'][0]['viewpoint_context_departure']);examples['chapter_departure']=r
check('chapter_departs_from_prior_narrator_reference',prior_and_switch,True)
def prior_resolution():
 a=material(['我叫霁棠。'],'01');b=material(['我关上门，四周一片漆黑。'],'02');c=material(['我叫闻澜。'],'03')
 bm=v.with_prior_context(b,[a,b,c]);ctx=v.narrator_context(bm);req([x['name'] for x in ctx['candidates']]==['霁棠'])
 req(run_c(bm,reply(bm,'霁棠','first_person',True))[0]['paragraphs'][0]['viewpoint']=='霁棠')
 other=material(['我叫闻澜。'],'00','otherbook');req(v.narrator_context(v.with_prior_context(b,[other,b]))['candidates']==[])
check('prior_only_same_book_no_future_contamination',prior_resolution,True)
def split_context():
 m=material(['我叫霁棠。','我摸到门闩。']);calls=[]
 def call(role,ch,msg,rev,stage):
  calls.append(json.loads(msg[-1]['content'].rsplit('\n',1)[-1]))
  if len(calls)==1:return {}
  packet=dict(m,paragraphs=[p for p in m['paragraphs'] if p['paragraph_id'] in [x[0] for x in calls[-1]['paragraphs']]])
  return reply(packet,'霁棠','first_person',True)
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='evidence'):r,p=t.c_text(m,call,lambda *args:None)
 req(len(calls)==3 and len(r['paragraphs'])==2 and all(x['viewpoint']=='霁棠' for x in r['paragraphs']))
 req(calls[-1]['viewpoint_context']['candidates'][0]['name']=='霁棠')
check('split_retains_whole_chapter_candidate',split_context,True)
def invalid_basis(kind):
 m=material(['霁棠看见木门。']);raw=reply(m,'霁棠');b=raw['paragraphs'][0]['viewpoint_basis']
 if kind=='false_quote':b['evidence']=[dict(p='p001',q='不存在的文字')]
 if kind=='wrong_p':b['evidence']=[dict(p='p999',q='霁棠')]
 if kind=='missing':raw['paragraphs'][0].pop('viewpoint_basis')
 if kind=='bad_type':raw['paragraphs'][0]['viewpoint_basis']=[]
 if kind=='omni_with_name':b['kind']='omniscient'
 if kind=='person_with_omni':raw['paragraphs'][0]['viewpoint']='全知'
 if kind=='label_only':raw['paragraphs'][0]['viewpoint']='第三人称'
 req(run_c(m,raw)[0]['paragraphs'][0]['viewpoint']=='未定')
for k in ('false_quote','wrong_p','missing','bad_type','omni_with_name','person_with_omni','label_only'):check('invalid_basis_'+k,lambda k=k:invalid_basis(k),True)
def identity():
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='legacy'):req(v.checkpoint_identity()=={})
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='evidence'):new=v.checkpoint_identity();req(new['c_viewpoint_settings']['mode']=='evidence')
 try:v.require_checkpoint({},new)
 except ValueError:pass
 else:raise AssertionError('mode change accepted')
 with patch.dict(os.environ,PIPELINE_C_VIEWPOINT_MODE='bogus'):
  try:t.c_text_messages(material(['霁棠开门。']))
  except ValueError:pass
  else:raise AssertionError('invalid mode accepted')
check('switch_default_checkpoint_and_invalid_mode',identity,True)
def non_c_unchanged():
 _,lc=whole(t,'legacy');_,ec=whole(t,'evidence')
 req([x for x in lc if x['role']!='C']==[x for x in ec if x['role']!='C']);req(len(lc)==len(ec))
check('evidence_mode_no_extra_requests_ABJ2_unchanged',non_c_unchanged,True)
def author_yellow():
 m=material(['我叫霁棠。']);r=run_c(m,reply(m,'霁棠','first_person',True))[0]
 a=build_views([m],{'01':dict(C=r,J2_status='blocked_upstream')});row=a['views']['写法视角表'][0]
 req(row['viewpoint']=='霁棠' and row['viewpoint_status']=='待核' and not row.get('default_usable',True));req('候选' in row['viewpoint_notice'])
check('author_preserves_name_and_explains_pending',author_yellow,True)
report=dict(execution_identity='Codex',tag=TAG,real_requests=0,handwritten_responses=True,cases=cases,passed=sum(x['status']=='passed' for x in cases),skipped=sum(x['status']=='skipped' for x in cases),total=len(cases),wire_proofs=proofs,examples=examples)
path=J/('selftest_v123_'+TAG+'.json');assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('examples','wire_proofs')},ensure_ascii=False,indent=2));sys.exit(int(any(x['status']=='failed' for x in cases)))

