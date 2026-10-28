#!/usr/bin/env python3
"""Bound reviewed browser harness to staged final engine and delivered baseline. No dispatch."""
import argparse,hashlib,importlib.util,json,os,pathlib,shutil,signal,subprocess,sys,time
P=pathlib.Path
CAP=128*1024*1024

def need(ok,why):
 if not ok:raise ValueError(why)
def sha(path):
 h=hashlib.sha256()
 with P(path).open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def dump(path,obj):P(path).parent.mkdir(parents=True,exist_ok=True);P(path).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def verify_harness(root,expected):
 root=P(root);manifest=root/'manifest.json';need(sha(manifest)==expected,'Reviewed browser harness manifest differs')
 files=json.loads(manifest.read_text())['files'];need(len(files)==51,'Corrected full51-file harness required')
 for rel,row in files.items():
  p=root/rel;need(not p.is_symlink() and p.is_file() and p.resolve().is_relative_to(root.resolve()),'Unsafe harness member')
  need(sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],'Harness bytes changed: '+rel)
 return files

def selected_flavors(rows,engine):
 candidate=[r for r in rows if r['arm']=='candidate'];need(len(candidate)==232,'Incomplete candidate rows')
 hashes={r['fetchedWasm'][0]['sha256'] for r in candidate}
 need(len(hashes)==1,'This290-row invocation proves exactly one real default loader path')
 chosen=next(iter(hashes));need(chosen in engine['wasmSHA256'],'Observed WASM not in final engine')
 mapping=engine.get('wasmFlavorBySHA256');need(isinstance(mapping,dict),'Reviewed engine WASM flavor correspondence absent')
 need(set(mapping)==set(engine['wasmSHA256']) and set(mapping.values())=={'extensions','mvp'},'Both actual flavor identities must be independently mapped')
 flavor=mapping[chosen];return chosen,[flavor]

def receipt_from_result(result,verified,engine,contract_sha):
 need(result.get('passed') is True and result.get('selection')=='unmodified-shipping-default','Actual shipping matrix absent')
 need(result['runtimeBindingSHA256']==contract_sha,'Runtime binding differs')
 need(verified['rows']==290 and verified['phases']==870 and verified['trustedClicks']==4350,'Matrix verifier incomplete')
 selected,paths=selected_flavors(result['rows'],engine)
 return {'passed':True,'skipped':0,'engineSHA256':engine['sha256'],'selectedWasmSHA256':selected,
 'realLoaderPaths':paths,'rows':290,'shippingSelectionExecuted':True,
 'mvpSelectionStatus':'executed-shipping-default' if 'mvp' in paths else 'not-executed-no-supported-route',
 'runtimeBindingSHA256':contract_sha,'browserVersion':result['browserVersion'],'preflightSHA256':result['preflightSHA256'],
 'verification':verified,'evidenceKind':'sandboxed desktop browser / SwiftShader','physicalDeviceCertified':False,
 'scope':'Actual default loader only. Dual flavors built; unexecuted fallback selection is not runtime-tested.'}

class Runner:
 def __init__(self,composite,harness):
  self.root=P(composite).resolve();self.harness=P(harness).resolve();self.lock=json.loads((self.root/'validation-lock.json').read_text())
  self.cfg=self.lock['lanes']['browser'];self.out=self.root/'evidence/browser';self.stage=self.root/'browser-validation-staging'
  need(not self.out.exists() and not self.stage.exists() and not (self.root/'evidence/browser-acceptance.json').exists() and not (self.root/'evidence/browser-failure.json').exists(),'Fresh browser evidence/staging required; inspect uncertain earlier run')
  self.out.mkdir(parents=True);self.stage.mkdir();self.work=self.stage/'harness';self.binding=self.out/'runtime-binding.json'
 def budget(self):need(sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())<=CAP,'Browser evidence cap exceeded')
 def command(self,argv,name,timeout):
  log=self.out/(name+'.log');start=time.monotonic()
  with log.open('xb') as f:
   process=subprocess.Popen([str(x) for x in argv],stdout=f,stderr=subprocess.STDOUT,cwd=self.work,start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
   try:
    while process.poll() is None:
     need(time.monotonic()-start<=timeout,'Command deadline exceeded: '+name)
     need(log.stat().st_size<=16*1024*1024,'Complete log limit exceeded: '+name)
     self.budget();time.sleep(.5)
    code=process.returncode
   except BaseException:
    if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
    raise
  self.budget();need(code==0,'Command failed '+name+' exit='+str(code));return log
 def prepare(self):
  need(self.lock.get('dispatchAllowed') is True,'Final validation binding not approved')
  e=self.lock['engine'];candidate=self.root/'staged-engine';baseline=self.root/'baseline-bundle/sampling/runtime'
  need(sha(self.root/'staged-engine-archive.zip')==e['sha256'],'Staged engine archive differs')
  staging=json.loads((self.root/'evidence/engine-staging.json').read_text());need(staging.get('verified') is True and staging['engine']==e,'Engine staging receipt differs')
  need(sha(candidate/'provenance.json')==e['provenanceSHA256'],'Engine provenance differs')
  need(sha(candidate/'runtime-files.json')==e['runtimeInventorySHA256'],'Engine runtime inventory differs')
  prov=json.loads((candidate/'provenance.json').read_text())
  need(prov['run']['GITHUB_SHA']==e['sourceCommit'] and prov['run']['GITHUB_RUN_ID']==str(e['runID']),'Final engine run/source differs')
  need(prov['sourceSetSHA256']==e['sourceSetSHA256'],'Final engine source set differs')
  files=verify_harness(self.harness,self.cfg['harnessManifestSHA256'])
  self.work.mkdir()
  for rel in ['manifest.json',*files]:
   target=self.work/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.harness/rel,target)
  (self.work/'evidence').mkdir()
  self.command([sys.executable,'scripts/prepare_contract.py','--candidate-artifact',candidate,'--baseline',baseline,
   '--baseline-identity','provenance/delivered-155-runtime.json','--expected-provenance-sha256',e['provenanceSHA256'],
   '--expected-baseline-identity-sha256','4f6c0ce66c2287ecaf64246e92b9b72b4e5d354fdaafdbe2b4c48243eaf5d3b4','--out',self.binding],'bind-runtime',120)
  need(self.cfg['expectedRowsPerExecutedPath']==290,'Wrong expected matrix coverage')
  # Require a reviewed map before spending any browser time, never infer by size.
  mapping=e.get('wasmFlavorBySHA256');need(isinstance(mapping,dict) and set(mapping)==set(e['wasmSHA256']) and set(mapping.values())=={'extensions','mvp'},'WASM source-to-flavor map absent')
 def collect(self):
  src=self.work/'evidence'
  if not src.is_dir():return
  dest=self.out/'matrix'
  need(not dest.exists(),'Evidence copy already exists; no blind overwrite')
  files=list(src.rglob('*'));need(all(not p.is_symlink() for p in files),'Linked evidence forbidden')
  need(sum(p.stat().st_size for p in files if p.is_file())<=CAP,'Matrix evidence exceeds cap')
  for p in files:
   if not p.is_file():continue
   need(p.suffix in ['.json','.png','.log'],'Unexpected evidence type')
   q=dest/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
  self.budget()
 def execute(self):
  try:
   self.prepare()
   self.command([sys.executable,'scripts/browser_preflight.py'],'browser-preflight',90)
   self.command([sys.executable,'scripts/browser_matrix.py','--candidate',self.root/'staged-engine/runtime',
    '--baseline',self.root/'baseline-bundle/sampling/runtime','--contract',self.binding],'browser-matrix',2100)
   verified_log=self.command([sys.executable,'scripts/verify_results.py','evidence/result.json',self.binding],'browser-independent-verifier',180)
   self.command([sys.executable,'scripts/evidence_budget.py'],'browser-evidence-budget',30)
   verified=json.loads(verified_log.read_text());result=json.loads((self.work/'evidence/result.json').read_text())
   report=receipt_from_result(result,verified,self.lock['engine'],sha(self.binding))
   verify_harness(self.work,self.cfg['harnessManifestSHA256']);verify_harness(self.harness,self.cfg['harnessManifestSHA256'])
   self.collect();report['matrixResultSHA256']=sha(self.out/'matrix/result.json')
   report['independentVerifierSHA256']=sha(verified_log);report['harnessManifestSHA256']=self.cfg['harnessManifestSHA256']
   dump(self.root/'evidence/browser-acceptance.json',report);print('PASS exact290-row real shipping browser path; no native or IPA claim')
  except BaseException as exc:
   try:
    if not (self.out/'matrix').exists():self.collect()
   finally:dump(self.root/'evidence/browser-failure.json',{'passed':False,'error':str(exc),'engineSHA256':(self.lock.get('engine') or {}).get('sha256'),'acceptanceWritten':False})
   raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--composite-root',type=P,required=True);p.add_argument('--harness',type=P,required=True);a=p.parse_args();Runner(a.composite_root,a.harness).execute()
