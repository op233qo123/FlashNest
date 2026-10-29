#!/usr/bin/env python3
"""Same-run, read-only sampling evidence transport; never accepts another run/attempt."""
import hashlib, importlib.util, io, json, os, re, stat, zipfile
from pathlib import Path, PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
REPO='op233qo123/FlashNest'
CAP=128*1024*1024

def require(ok,why):
 if not ok:raise ValueError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inventory(root):
 out={}
 for p in sorted(Path(root).rglob('*')):
  require(not p.is_symlink(),'Linked evidence forbidden')
  if p.is_file():out[p.relative_to(root).as_posix()]=sha(p)
  else:require(p.is_dir(),'Nonregular evidence forbidden')
 return out
def dump(p,value):Path(p).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def transport():
 spec=importlib.util.spec_from_file_location('pinned_transport',ROOT/'scripts/stage_validation_runtime.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def context():
 require(os.environ.get('GITHUB_REPOSITORY')==REPO,'Exact repository required')
 result={k:os.environ.get(k,'') for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_REPOSITORY')}
 require(result['GITHUB_RUN_ID'].isdigit() and result['GITHUB_RUN_ATTEMPT'].isdigit() and re.fullmatch('[0-9a-f]{40}',result['GITHUB_SHA']),'Actual Actions identity required')
 return result
def jobs():
 t=transport();c=context()
 with t.api('actions/runs/'+c['GITHUB_RUN_ID']+'/attempts/'+c['GITHUB_RUN_ATTEMPT']+'/jobs?per_page=100') as response:doc=json.loads(t.read_limited(response,4*1024*1024))
 require(doc['total_count']==len(doc['jobs']) and len(doc['jobs'])<=10,'Ambiguous/incomplete workflow job list')
 return doc['jobs']
def job_identity(role,rows=None,completed=False):
 c=context();name='native-sampling-'+role if role in ('dpr2','dpr3') else 'native-functional'
 rows=jobs() if rows is None else rows
 hits=[r for r in rows if r['name']==name]
 require(len(hits)==1,'Exact job name missing/ambiguous')
 # Attempt is authenticated by jobs()' exact /attempts/N endpoint. Some API
 # responses omit optional run_attempt; if supplied it must still match.
 row=hits[0];require(str(row['run_id'])==c['GITHUB_RUN_ID'] and row['head_sha']==c['GITHUB_SHA'] and ('run_attempt' not in row or str(row['run_attempt'])==c['GITHUB_RUN_ATTEMPT']),'Job belongs to another run/head/attempt')
 if completed:require(row['status']=='completed' and row['conclusion']=='success','Sampling dependency not successful')
 else:require(row['status']=='in_progress','Current job not executing')
 return {**c,'jobID':row['id'],'jobName':name,'role':role}
def freeze_leaf(out,receipt):
 out=Path(out);require(receipt['nativeAcceptance'] is False and receipt['samplingJobPassed'] is True,'Leaf must not claim native acceptance')
 dump(out/'sampling-job-receipt.json',receipt)
 files=inventory(out);require('sampling-job-manifest.json' not in files,'Existing manifest rejected')
 dump(out/'sampling-job-manifest.json',{'schema':1,'job':receipt['job'],'files':files,'nativeAcceptance':False})
def verify_leaf(folder,expected_job):
 folder=Path(folder);manifest=json.loads((folder/'sampling-job-manifest.json').read_text())
 require(manifest.get('schema')==1 and manifest.get('nativeAcceptance') is False and manifest['job']==expected_job,'Leaf manifest identity differs')
 files=inventory(folder);files.pop('sampling-job-manifest.json',None)
 require(files==manifest['files'],'Leaf complete file map differs')
 receipt=json.loads((folder/'sampling-job-receipt.json').read_text())
 require(receipt.get('schema')==1 and receipt.get('fullGeometryPending') is True and receipt['job']==expected_job and receipt['samplingJobPassed'] is True and receipt['nativeAcceptance'] is False,'Invalid leaf receipt')
 return receipt

def fetch_leaves(destination):
 destination=Path(destination);require(not destination.exists(),'Fresh leaf download required');destination.mkdir(parents=True)
 t=transport();c=context();rows=jobs()
 with t.api('actions/runs/'+c['GITHUB_RUN_ID']+'/artifacts?per_page=100') as response:doc=json.loads(t.read_limited(response,4*1024*1024))
 require(doc['total_count']==len(doc['artifacts']) and len(doc['artifacts'])<=20,'Incomplete artifact listing')
 index={}
 for role in ('dpr2','dpr3'):
  job=job_identity(role,rows,True);name='FlashNest-native-sampling-'+role+'-attempt-'+c['GITHUB_RUN_ATTEMPT']
  matches=[a for a in doc['artifacts'] if a['name']==name and not a['expired']]
  require(len(matches)==1,'Missing/duplicate same-attempt sampling artifact')
  a=matches[0];digest=a.get('digest','');require(re.fullmatch('sha256:[0-9a-f]{64}',digest),'Artifact server digest required')
  require(0<a['size_in_bytes']<=CAP,'Artifact compressed budget exceeded')
  # Existing transport revalidates artifact run/head and strips token on storage redirect.
  raw=t.fetch({'artifactID':a['id'],'runID':int(c['GITHUB_RUN_ID']),'sourceCommit':c['GITHUB_SHA'],'bytes':a['size_in_bytes'],'sha256':digest[7:]})
  out=destination/role;out.mkdir()
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   infos=z.infolist();require(0<len(infos)<=10000 and sum(i.file_size for i in infos)<=CAP,'Expanded evidence bound exceeded');seen=set()
   for i in infos:
    p=PurePosixPath(i.filename)
    require(i.filename not in seen and p.as_posix()==i.filename and not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and ':' not in i.filename,'Unsafe/duplicate evidence path');seen.add(i.filename)
    require(stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG) and i.file_size<=16*1024*1024,'Linked/nonregular/oversized member')
    target=out/i.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(i))
  receipt=verify_leaf(out,job)
  index[role]={'job':job,'artifactID':a['id'],'artifactName':name,'archiveSHA256':digest[7:],'archiveBytes':len(raw),'manifestSHA256':sha(out/'sampling-job-manifest.json'),'receiptSHA256':sha(out/'sampling-job-receipt.json')}
 dump(destination/'download-receipt.json',index)
 return index
