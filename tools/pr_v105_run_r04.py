# 执行身份：Codex
"""One request per authorized file-protocol job, using production parameters."""
import sys
sys.dont_write_bytecode=True
import datetime,hashlib,json,os
from pathlib import Path
import urllib.request,urllib.parse

ROOT=Path('/workspace/codex-work/out/管线修复_R04/job_R04_v105')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p)
 if not p.resolve().is_relative_to(ROOT):raise RuntimeError('本轮输出目录不符')
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({'execution_identity':'Codex',**x},ensure_ascii=False,indent=2)+'\n')
def main(path):
 p=Path(path)
 if not p.resolve().is_relative_to(ROOT/'requests'):raise RuntimeError('请求路径不符')
 data=json.loads(p.read_text());jid=data['job_id'];body=data['body']
 for file,digest in data['code_sha256'].items():
  if sha(file)!=digest:raise RuntimeError('投递后代码改变')
 if data['body_sha256']!=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest():raise RuntimeError('请求正文改变')
 if os.environ.get('PR_JOB_ID')!=jid:raise RuntimeError('作业身份不符')
 base=os.environ['PR_LLM_BASE_URL'].rstrip('/');u=urllib.parse.urlparse(base)
 if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path!='/v1' or not u.port or u.username or u.query or u.fragment:raise RuntimeError('必须走注入网关')
 if 'execution_identity' in body:raise RuntimeError('请求不能带执行身份')
 folder=ROOT/'responses'/jid
 if (folder/'started.json').exists():raise RuntimeError('入口只准发送一次')
 save(folder/'started.json',{'job_id':jid,'at':datetime.datetime.now().astimezone().isoformat(),'entry_http_attempts':1})
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):return None
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 req=urllib.request.Request(base+'/chat/completions',data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','X-PR-Job-ID':jid})
 try:
  with opener.open(req,timeout=580) as r:response=json.load(r)
  save(folder/'response.json',{'response':response,'job_id':jid,'received_at':datetime.datetime.now().astimezone().isoformat()})
 except Exception as e:
  save(folder/'failure.json',{'job_id':jid,'error_type':type(e).__name__,'error':str(e),'entry_retries':0})
  raise
if __name__=='__main__':main(sys.argv[1])
