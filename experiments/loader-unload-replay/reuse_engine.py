#!/usr/bin/env python3
"""Replay browsers against an immutable prior engine; never re-label build/core execution."""
import argparse,hashlib,importlib.util,json,os,re,zipfile
from pathlib import Path
PIN={'artifactID':13089357368,'runID':41318527222,'head':'3b0ab52a334336e6e6474e840e9c487e3f666f1d','archiveSHA256':'dac0c326e29d2cfd354eb418000ac049fa7bdcfaa56b7693132f5799661d52c2','archiveBytes':15260480}
CHECKER_SHA='d767c5c93a3f87c29ef813e8a9074e1f2f6d69ebd10bfa69e9502b9a640fdf31'
BUILD={'build.sh','check_upload.py','core_tests.py','job.yml','receipt.py','stage.py'}
DELTA={'DESIGN.md','source-lock.json','unload-lifecycle.patch'}
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,msg):
 if not ok:raise ValueError(msg)
def files(root):
 result={}
 for p in root.rglob('*'):
  if '__pycache__' in p.parts:continue
  need(not p.is_symlink(),'Source symlink forbidden')
  if p.is_file():result[p.relative_to(root).as_posix()]=p.read_bytes()
 return result

def reuse(archive,metadata,original,output,lock_output,receipt,consumer_head,consumer_run):
 archive=Path(archive);original=Path(original)
 need(not archive.is_symlink() and archive.is_file(),'Regular archive required')
 data=archive.read_bytes();need(len(data)==PIN['archiveBytes'] and sha(data)==PIN['archiveSHA256'],'Pinned engine archive bytes/hash mismatch')
 meta=json.loads(Path(metadata).read_text());need(meta['id']==PIN['artifactID'] and meta['expired'] is False,'Wrong/expired artifact')
 need(meta['size_in_bytes']==PIN['archiveBytes'],'Artifact metadata size mismatch')
 need(meta['name']=='FlashNest-unload-candidate-engine-not-IPA','Unexpected engine artifact name')
 need(meta['workflow_run']['id']==PIN['runID'] and meta['workflow_run']['head_sha']==PIN['head'],'Artifact producer identity mismatch')
 if meta.get('digest'):need(meta['digest']=='sha256:'+PIN['archiveSHA256'],'Artifact API digest mismatch')
 need(bool(re.fullmatch('[0-9a-f]{40}',consumer_head)) and consumer_run.isdigit(),'Consumer CI identity required')
 checker=original/'integration/stage_candidate.py';need(sha(checker.read_bytes())==CHECKER_SHA,'Original validator changed')
 current_build=files(original/'build');current_delta=files(original/'engine')
 need(set(current_build)==BUILD and set(current_delta)==DELTA,'Unexpected engine/build source file set')
 with zipfile.ZipFile(archive) as z:
  for prefix,current in [('source-correspondence/candidate-build/',current_build),('source-correspondence/candidate-delta/',current_delta)]:
   packaged={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix)}
   need(packaged==current,'Current source differs from executed engine: '+prefix)
  manifest=json.loads(z.read('source-correspondence/staging/candidate-source.json'))
  base=json.loads(z.read('source-correspondence/staging/accepted-source.json'))
  delta=json.loads(current_delta['source-lock.json'])
  need(set(manifest)==set(base),'Source file set changed')
  need({p for p in base if base[p]!=manifest[p]}==set(delta['modifiedSourceFiles']),'Unexpected source delta')
  for p,m in delta['modifiedSourceFiles'].items():need(base[p]==m['before'] and manifest[p]==m['after'],'Delta source identity mismatch')
 spec=importlib.util.spec_from_file_location('immutable_stage_candidate',checker);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 result=module.stage(archive,output,lock_output,receipt,original/'engine/source-lock.json',PIN['head'],str(PIN['runID']))
 # Original source/run and core receipt remain untouched; consumer identity is separate.
 result.update({'reuseSchema':1,'engineReference':PIN,'engineBuildExecutedThisRun':False,'coreTestExecutionReused':True,'coreTestsExecutedThisRun':False,'consumerHead':consumer_head,'consumerRunID':consumer_run,'sourceBinding':{'originalCheckerSHA256':CHECKER_SHA,'buildFiles':{n:sha(b) for n,b in current_build.items()},'engineFiles':{n:sha(b) for n,b in current_delta.items()}},'browserResultsReused':False})
 Path(receipt).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['archive','metadata','original','output','lock-output','receipt']:p.add_argument('--'+n,required=True)
 a=p.parse_args();reuse(a.archive,a.metadata,a.original,a.output,a.lock_output,a.receipt,os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'])
 print('PASS exact prior engine/core reuse, current browser execution remains pending')
