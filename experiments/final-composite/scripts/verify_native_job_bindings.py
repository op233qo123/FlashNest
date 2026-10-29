"""Strict offline cross-job receipt binding; never substitutes for Actions job success."""
import hashlib,json,re
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def inventory(root):
 result={}
 for p in root.rglob('*'):
  assert not p.is_symlink()
  if p.is_file(): result[p.relative_to(root).as_posix()]=sha(p)
  else: assert p.is_dir()
 return result

def verify_generated(base,name,project_sha):
 record=read(base/(name+'-generated-app-files.json'))
 expected='b71b74d803b9a68e58a77e1043cbdcb07888606b513fecb8000651d73990085f'
 assert record['files']=={'App/Info.plist':expected}
 assert record['artifact']==name+'-generated-Info.plist'
 assert sha(base/record['artifact'])==expected
 assert record['projectSpecificationPath']=='project.yml' and record['projectSpecificationSHA256']==project_sha
 assert record['toolReceiptSHA256']==sha(base/'tool-receipt.json')
 return record

def verify_jobs(root,report,selection,lock):
 evidence=root/'evidence/native';functional=report['job']
 assert functional['role']=='functional' and functional['jobName']=='native-functional'
 assert functional['GITHUB_REPOSITORY']=='op233qo123/FlashNest'
 assert re.fullmatch('[0-9a-f]{40}',functional['GITHUB_SHA'])
 assert functional['GITHUB_RUN_ID'].isdigit() and functional['GITHUB_RUN_ATTEMPT'].isdigit()
 assert type(functional['jobID']) is int and functional['jobID']>0
 entries=report['samplingJobReceipts'];assert set(entries)=={'dpr2','dpr3'}
 binding_path=root/'validation-bindings/native-binding.json';binding=read(binding_path)
 helper=root/'validation-harness/native-composite-runner/helper-lock.json'
 method=root/'validation-harness/native-sampling-validation/method-map-v4.json'
 selection_path=root/'validation-harness/native-composite-runner/selection-contract-v4.json'
 seen_jobs={functional['jobID']};seen_artifacts=set();identities=None
 download=read(evidence/'sampling-job-download-receipt.json');assert set(download)==set(entries)
 for role,entry in entries.items():
  prefix='sampling-jobs/'+role;assert entry['evidencePrefix']==prefix
  assert {k:v for k,v in entry.items() if k!='evidencePrefix'}==download[role]
  job=entry['job'];assert job['role']==role and job['jobName']=='native-sampling-'+role
  for key in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','GITHUB_REPOSITORY'): assert job[key]==functional[key]
  assert type(job['jobID']) is int and job['jobID']>0 and job['jobID'] not in seen_jobs;seen_jobs.add(job['jobID'])
  assert type(entry['artifactID']) is int and entry['artifactID']>0 and entry['artifactID'] not in seen_artifacts;seen_artifacts.add(entry['artifactID'])
  assert entry['artifactName']=='FlashNest-native-sampling-'+role+'-attempt-'+functional['GITHUB_RUN_ATTEMPT']
  assert re.fullmatch('[0-9a-f]{64}',entry['archiveSHA256']) and type(entry['archiveBytes']) is int and 0<entry['archiveBytes']<=128*1024*1024
  base=evidence/prefix;manifest_path=base/'sampling-job-manifest.json';receipt_path=base/'sampling-job-receipt.json'
  assert sha(manifest_path)==entry['manifestSHA256'] and sha(receipt_path)==entry['receiptSHA256']
  manifest=read(manifest_path);assert manifest['schema']==1 and manifest['job']==job and manifest['nativeAcceptance'] is False
  files=inventory(base);del files['sampling-job-manifest.json'];assert files==manifest['files']
  receipt=read(receipt_path)
  assert receipt['schema']==1 and receipt['samplingJobPassed'] is True and receipt['nativeAcceptance'] is False and receipt['fullGeometryPending'] is True
  assert receipt['job']==job and type(receipt['dpr']) is int and receipt['dpr']==int(role[-1])
  for key,path in [('bindingSHA256',binding_path),('helperLockSHA256',helper),('selectionContractSHA256',selection_path),('methodMapSHA256',method)]: assert receipt[key]==sha(path)
  assert sha(base/'binding.json')==receipt['bindingSHA256']
  assert receipt['engineSHA256']==lock['engine']['sha256'] and receipt['appFiles']==binding['appFiles']==lock['appSourceManifest']['files']
  expected={r['runName']:r for r in selection['runs'] if r['runName'] in ('sampling-baseline-'+role,'sampling-candidate-'+role,'enhanced-boundary-'+role)}
  assert len(receipt['results'])==3 and {r['runName'] for r in receipt['results']}==set(expected)
  assert sum(r['tests'] for r in receipt['results'])==26
  for result in receipt['results']:
   assert 'evidencePrefix' not in result
   run=expected[result['runName']]
   assert result['tests']==run['expectedCount'] and result['lane']==run['lane'] and result['semanticResultValid'] is True
   final=[r for r in report['results'] if r['runName']==result['runName']];assert final==[{**result,'evidencePrefix':prefix}]
  ip=base/'sampling-expected-identities.json';assert sha(ip)==receipt['expectedIdentitiesSHA256']
  current=read(ip)
  if identities is None: identities=current
  else: assert current==identities
 assert read(evidence/'sampling-expected-identities.json')==identities
 functional_results=[r for r in report['results'] if r['lane'] not in ('sampling-baseline','sampling-candidate','sampling-enhanced-boundary')]
 assert all('evidencePrefix' not in r for r in functional_results)
 assert sum(r['tests'] for r in functional_results)==146
