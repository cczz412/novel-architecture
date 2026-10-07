# 执行身份：Codex
import pathlib,json,sys,zipfile,hashlib
sys.dont_write_bytecode=True
import argparse
parser=argparse.ArgumentParser(description='按已登记背景语料复跑全文检测，不读取盲词表')
parser.add_argument('output_dir')
parser.add_argument('--release-table',default='/workspace/codex-work/out/管线修复_R04/审读/71_背景串放行表.json')
args=parser.parse_args()
R=pathlib.Path(args.output_dir);R.mkdir(parents=True,exist_ok=True)
W=pathlib.Path(__file__).resolve().parents[1]
import pipeline_audit25 as audit
from pipeline_source25 import read_json,write_json,digest
p=W/'tools/pipeline_background25.json'
terms=W/'tools/pipeline_terms25.json'
records=read_json(p)['books']; corpora={}; receipts=[]
for record in records:
 blocks=[];used=[]
 with zipfile.ZipFile(record['archive']) as package:
  for n in range(1,record['chapter_count']+1):
   chapter=str(n).zfill(2);member='books/'+record['book_id']+'/sources/'+chapter+'_paragraphs.json'
   try:raw=package.read(member)
   except KeyError:continue
   data=json.loads(raw); rows=data.get('paragraphs') if isinstance(data,dict) else data
   blocks.extend(r['text'] for r in rows)
   used.append(dict(member=member,sha256=hashlib.sha256(raw).hexdigest(),paragraph_count=len(rows)))
 corpora[record['code']]='\n'.join(blocks)
 receipts.append(dict(**record,members=used,text_length=len(corpora[record['code']]),pipeline_steps=0))
entities={code:set() for code in corpora}
for record in records:
 for item in record.get('entity_records', []):
  obj=read_json(item['path'])
  if item.get('views'):
   obj={key:obj['views'].get(key,[]) for key in item['views']}
  if item.get('chapter_book'):
   obj=[row for row in obj['chapters'] if row.get('book')==item['chapter_book']]
  entities[record['code']].update(audit.collect_entities(obj))
configs=[W/'tools/pipeline_terms25.json',W/'tools/pipeline_background25.json']
files,errors=audit.local_closure(W/'tools/run_pipeline.py',[],configs)
struct=audit.structural_checks(files);scans=audit.string_scan(files,corpora,entities,read_json(terms)['words'])
if pathlib.Path(args.release_table).exists():scans=audit.apply_background_releases(scans,files,args.release_table)
write_json(R/'closure_candidate_v25.json',dict(execution_identity='Codex',files=[dict(path=str(p),sha256=digest(p)) for p in files],dynamic_errors=errors))
write_json(R/'string_detection_v25.json',dict(execution_identity='Codex',reports=scans,whitelist_sha256=digest(terms),background_sha256=digest(W/'tools/pipeline_background25.json'),corpus_receipts=receipts,entities={k:sorted(v) for k,v in entities.items()},known_exposure={'provider':'审读侧持表代跑','words_read':False,'self_populated':False},hard_passed=all(scans[k]['hit_count']==0 for k in ['qishi','dixian'])))
write_json(R/'structural_checks_v25.json',dict(execution_identity='Codex',**struct))
print('closure',len(files),'dynamic errors',errors,'structural',struct['passed'])
for code,scan in scans.items():
 print(code,'chars',len(corpora[code]),'entities',scan['entity_count'],'candidates',scan['candidate_count'],'hits',scan['hit_count'],'six+',scan['six_plus_passed'])
 for file,rows in scan['by_file'].items():
  if rows['count']:print(pathlib.Path(file).name,rows['hits'][:35])
if struct['errors']:print(struct['errors'])
