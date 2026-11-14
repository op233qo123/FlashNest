#!/usr/bin/env python3
"""Restore a pinned archival ZIP; never disguise an expired Actions artifact as live.

The original immutable archive/source/runtime/core validator is executed unchanged.
Only transport provenance differs from reuse_engine.py: an explicit backup descriptor
replaces the unavailable live artifact metadata gate. No new engine/core pass is claimed.
"""
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

def descriptor_for_backup():
 """Reference descriptor, not fabricated GitHub API metadata."""
 return {'schema':'flashnest-archival-engine-restore-v1',
         'transport':'reviewed-byte-identical-backup',
         'originalArtifact':dict(PIN),
         'originalArtifactName':'FlashNest-unload-candidate-engine-not-IPA',
         'originalArtifactAvailability':'unavailable',
         'backupProvenance':'retained-local-copy-of-original-artifact-zip',
         'engineBuildExecutedThisRun':False,'coreTestsExecutedThisRun':False}

def validate_descriptor(value):
 need(json.dumps(value,sort_keys=True)==json.dumps(descriptor_for_backup(),sort_keys=True),'Explicit backup descriptor mismatch')
 return value

def reuse(archive,descriptor,original,output,lock_output,receipt,consumer_head,consumer_run,restoration_receipt=None):
 archive=Path(archive);original=Path(original);descriptor=Path(descriptor)
 need(not archive.is_symlink() and archive.is_file(),'Regular archive required')
 need(not descriptor.is_symlink() and descriptor.is_file(),'Regular descriptor required')
 data=archive.read_bytes();need(len(data)==PIN['archiveBytes'] and sha(data)==PIN['archiveSHA256'],'Pinned engine archive bytes/hash mismatch')
 descriptor_raw=descriptor.read_bytes()
 declaration=validate_descriptor(json.loads(descriptor_raw))
 restoration_receipt=Path(restoration_receipt) if restoration_receipt else Path(str(receipt)+'.restoration.json')
 need(not restoration_receipt.exists() and not restoration_receipt.is_symlink(),'Restoration receipt must be fresh')
 need(not Path(receipt).exists() and not Path(lock_output).exists(),'Reuse outputs must be fresh')
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
 restoration={'schema':'flashnest-archival-engine-restoration-receipt-v1',
              'descriptor':declaration,'descriptorSHA256':sha(descriptor_raw),
              'archiveSHA256':sha(data),'archiveBytes':len(data),
              'originalCheckerSHA256':CHECKER_SHA,
              'restoreHelperSHA256':sha(Path(__file__).read_bytes()),
              'consumerHead':consumer_head,'consumerRunID':consumer_run,
              'liveArtifactDownloadPerformed':False,
              'engineBuildExecutedThisRun':False,'coreTestsExecutedThisRun':False,
              'applicationPass':False,'physicalDeviceCertified':False}
 restoration_receipt.write_text(json.dumps(restoration,sort_keys=True,indent=2)+'\n')
 result['archivalRestoration']={'schema':restoration['schema'],'receiptSHA256':sha(restoration_receipt.read_bytes()),'descriptorSHA256':sha(descriptor_raw),'originalArtifactAvailability':'unavailable'}
 Path(receipt).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['archive','descriptor','original','output','lock-output','receipt']:p.add_argument('--'+n,required=True)
 a=p.parse_args();reuse(a.archive,a.descriptor,a.original,a.output,a.lock_output,a.receipt,os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'])
 print('PASS exact archived engine/core reuse; no live artifact download or new engine/core execution')
