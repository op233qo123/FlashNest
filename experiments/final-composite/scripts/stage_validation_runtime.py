#!/usr/bin/env python3
"""Fetch exactly pinned GitHub Actions artifact; strip auth before storage redirect."""
import hashlib,json,os,urllib.request,urllib.error,zipfile,io,stat,shutil
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def read_limited(response,cap):
 out=bytearray()
 while True:
  part=response.read(min(1048576,cap+1-len(out)))
  if not part:break
  out.extend(part);require(len(out)<=cap,'Download exceeds pinned bound')
 return bytes(out)
def api(path):
 token=os.environ.get('GH_TOKEN');require(bool(token),'Missing existing Actions read credential')
 request=urllib.request.Request('https://api.github.com/repos/op233qo123/FlashNest/'+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 return urllib.request.build_opener(NoRedirect).open(request,timeout=60)
def fetch(e):
 with api('actions/artifacts/'+str(e['artifactID'])) as response:meta=json.loads(read_limited(response,1048576))
 require(meta.get('expired') is False and meta.get('workflow_run',{}).get('id')==e['runID'] and meta['workflow_run'].get('head_sha')==e['sourceCommit'],'Artifact run/source identity differs')
 try:
  with api('actions/artifacts/'+str(e['artifactID'])+'/zip') as response:data=read_limited(response,e['bytes'])
 except urllib.error.HTTPError as err:
  require(err.code in (301,302,303,307,308),'Artifact download failed')
  url=err.headers.get('Location','');from urllib.parse import urlparse
  u=urlparse(url);require(u.scheme=='https' and u.hostname and not u.username and not u.password,'Unsafe artifact redirect')
  # A new request deliberately carries NO GitHub Authorization header.
  with urllib.request.urlopen(urllib.request.Request(url),timeout=180) as response:data=read_limited(response,e['bytes'])
 require(len(data)==e['bytes'] and sha(data)==e['sha256'],'Artifact archive bytes/hash differ')
 return data

def main():
 lock=json.loads((ROOT/'validation-lock.json').read_text());require(lock.get('dispatchAllowed') is True,'Unapproved validation binding');e=lock['engine'];out=ROOT/'staged-engine'
 require(not out.exists(),'Existing staging requires inspection, not overwrite')
 data=fetch(e)
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  rows=z.infolist();require(len(rows)<=5000 and sum(i.file_size for i in rows)<=402653184,'Oversized artifact')
  names=set()
  for i in rows:
   p=PurePosixPath(i.filename);require(i.filename not in names and not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and ':' not in i.filename and p.as_posix()==i.filename,'Unsafe/duplicate artifact path');names.add(i.filename)
   require(stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG) and i.file_size<=67108864,'Linked/nonregular artifact member')
  required='final-composite-engine/'
  raw=z.read(required+'provenance.json');require(sha(raw)==e['provenanceSHA256'],'Provenance differs');receipt=json.loads(raw)
  require(receipt['run']['GITHUB_SHA']==e['sourceCommit'] and receipt['run']['GITHUB_RUN_ID']==str(e['runID']) and receipt['sourceSetSHA256']==e['sourceSetSHA256'],'Receipt source/run differs')
  invraw=z.read(required+'runtime-files.json');require(sha(invraw)==e['runtimeInventorySHA256']==receipt['runtimeInventorySHA256'],'Runtime inventory differs');inv=json.loads(invraw)
  require({n[len(required+'runtime/'):] for n in names if n.startswith(required+'runtime/')}==set(inv),'Extra/missing runtime')
  for rel,row in inv.items():
   b=z.read(required+'runtime/'+rel);require(len(b)==row['bytes'] and sha(b)==row['sha256'],'Runtime bytes differ')
  require(sorted(row['sha256'] for rel,row in inv.items() if rel.endswith('.wasm'))==sorted(e['wasmSHA256']),'WASM branch inventory differs')
  # Full correspondence and its pre/post source inventory are independently pinned
  # by the reviewed entire archive, plus the engine receipt; no code is executed here.
  require(z.read(required+'full-source-before.json')==z.read(required+'full-source-after.json'),'Engine source changed during build')
  require(sha(z.read(required+'full-source-before.json'))==receipt['fullSourceManifestSHA256'],'Full source manifest differs')
  corr=receipt['correspondence'];prefix=required+'source-correspondence/'
  require({n[len(prefix):] for n in names if n.startswith(prefix)}==set(corr),'Correspondence file set differs')
  for rel,row in corr.items():
   b=z.read(prefix+rel);require(len(b)==row['bytes'] and sha(b)==row['sha256'],'Correspondence bytes differ')
  archive=ROOT/'staged-engine-archive.zip';require(not archive.exists(),'Existing archive staging must be inspected');archive.write_bytes(data)
  out.mkdir()
  for name in sorted(names):
   if name.startswith(required):
    target=out/name[len(required):];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 (ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence/engine-staging.json').write_text(json.dumps({'verified':True,'engine':e},indent=2)+'\n')
 print('Verified exact final engine archive, run, source and runtime correspondence')
if __name__=='__main__':main()
