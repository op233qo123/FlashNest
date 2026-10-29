#!/usr/bin/env python3
"""Run one reviewed native DAG role; leaf completion is not native acceptance."""
import json,os,shutil,signal,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 role=os.environ.get('NATIVE_JOB_ROLE');assert role in ('dpr2','dpr3','functional'),'Exact native role required'
 subprocess.run([sys.executable,ROOT/'scripts/validate_binding.py','native'],check=True)
 lock=json.loads((ROOT/'validation-lock.json').read_text());assert lock.get('dispatchAllowed') is True and lock.get('diagnosticOnly') is not True
 cfg=lock['lanes']['native'];assert cfg.get('executionTopology')=='isolated-dpr-v4','Reviewed multi-job topology required'
 expected=[['validation-venv/bin/python','scripts/stage_validation_runtime.py'],['validation-venv/bin/python','scripts/stage_validation_inputs.py'],['validation-venv/bin/python','scripts/validate_final_app.py','--app','validation-app'],['validation-venv/bin/python','scripts/run_native_validation.py']]
 assert cfg['commands']==expected,'Exact staging pipeline required'
 for command in cfg['commands'][:-1]:subprocess.run(command,cwd=ROOT,check=True,timeout=cfg.get('perCommandTimeoutSeconds',1200))
 out=ROOT/'native-execution/results';final=ROOT/'evidence/native'
 assert not out.exists() and not final.exists(),'Inspect uncertain existing run before retry'
 command=[sys.executable,str(ROOT/'validation-harness/native-composite-runner/run.py'),'--app',str(ROOT/'validation-app'),'--candidate-engine',str(ROOT/'staged-engine'),'--baseline',str(ROOT/'baseline-bundle'),'--binding',str(ROOT/'validation-bindings/native-binding.json'),'--output',str(out),'--role',role]
 if role=='functional':
  import job_evidence
  incoming=ROOT/'sampling-job-input';job_evidence.fetch_leaves(incoming);command+=['--sampling-input',str(incoming)]
 code=None;primary=None;secondary=None
 try:
  process=subprocess.Popen(command,cwd=ROOT,start_new_session=True)
  try:code=process.wait(timeout=7800)
  except BaseException:
   if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
   raise
  if code!=0:raise RuntimeError('Native job command failed exit='+str(code))
 except BaseException as error:
  primary=error
  if out.is_dir():(out/'wrapper-primary-error.json').write_text(json.dumps({'errorType':type(error).__name__,'error':str(error),'nativeAcceptance':False},indent=2)+'\n')
 # Budget/copy failures must never erase the original timeout/command failure.
 try:
  if out.is_dir():
   subprocess.run([sys.executable,ROOT/'scripts/evidence_budget.py',out],check=True)
   final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
 except BaseException as error:
  secondary=error
  if out.is_dir():(out/'wrapper-evidence-error.json').write_text(json.dumps({'errorType':type(error).__name__,'error':str(error),'primaryError':str(primary) if primary else None,'nativeAcceptance':False},indent=2)+'\n')
  print('FAIL bounded evidence collection; original command error='+str(primary),flush=True)
 if primary is not None:raise primary
 if secondary is not None:raise secondary
 if role=='functional':
  receipt=final/'native-acceptance.json';assert receipt.is_file(),'Missing full native acceptance'
  shutil.copyfile(receipt,ROOT/'evidence/native-acceptance.json')
  subprocess.run(cfg['verifier'],cwd=ROOT,check=True,timeout=cfg.get('perCommandTimeoutSeconds',1200))
  report=json.loads((ROOT/'evidence/native-acceptance.json').read_text());assert report.get('passed') is True and report.get('skipped')==0 and report.get('nativeMethods')==198
  assert report.get('engineSHA256')==lock['engine']['sha256'] and report.get('selectedWasmSHA256') in lock['engine']['wasmSHA256'],'Runtime acceptance identity differs'
  assert report.get('evidenceKind')=='iOS simulator' and report.get('physicalDeviceCertified') is False
  policies=report.get('shippingPoliciesWithAllReductions',[])
  assert report.get('shippingReductionRequirementMet') is True and policies and all(p in ('automatic','webgl') for p in policies)
  assert report.get('shippingDefaultAppliesAllTiers') is ('automatic' in policies)
 else:
  receipt=json.loads((final/'sampling-job-receipt.json').read_text());assert receipt['samplingJobPassed'] is True and receipt['nativeAcceptance'] is False
 print('DONE native role '+role+'; no IPA',flush=True)
if __name__=='__main__':main()
