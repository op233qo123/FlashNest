#!/usr/bin/env python3
"""Execute reviewed native runner; publish only its bounded synthetic evidence."""
import json,os,signal,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 lock=json.loads((ROOT/'validation-lock.json').read_text());assert lock.get('dispatchAllowed') is True
 assert lock.get('diagnosticOnly') is not True,'Only bounded policy diagnostic is authorized; full native v3 not frozen'
 out=ROOT/'native-execution/results';final=ROOT/'evidence/native'
 assert not out.exists() and not final.exists(),'Inspect existing uncertain run before retry'
 command=[sys.executable,str(ROOT/'validation-harness/native-composite-runner/run.py'),'--app',str(ROOT/'validation-app'),'--candidate-engine',str(ROOT/'staged-engine'),'--baseline',str(ROOT/'baseline-bundle'),'--binding',str(ROOT/'validation-bindings/native-binding.json'),'--output',str(out)]
 result=None
 try:
  process=subprocess.Popen(command,cwd=ROOT,start_new_session=True)
  try:code=process.wait(timeout=7800)
  except BaseException:
   if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
   raise
  result=subprocess.CompletedProcess(command,code)
 finally:
  if out.is_dir():
   subprocess.run([sys.executable,str(ROOT/'scripts/evidence_budget.py'),str(out)],check=True)
   final.parent.mkdir(exist_ok=True);shutil.copytree(out,final)
 if result is None or result.returncode:raise SystemExit('Native execution failed; see complete bounded evidence')
 receipt=final/'native-acceptance.json';assert receipt.is_file(),'Missing independent native acceptance'
 shutil.copyfile(receipt,ROOT/'evidence/native-acceptance.json')
 print('Native adapter completed; receipt still checked by independent lane binding')
if __name__=='__main__':main()
